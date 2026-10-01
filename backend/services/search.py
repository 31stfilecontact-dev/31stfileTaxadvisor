"""Kanoon authority retrieval with per-request call limits and DB caching."""

from __future__ import annotations

from datetime import date, datetime, timezone
from html.parser import HTMLParser
import logging
import re
import time
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import (
    Act,
    Analysis,
    CaseDocument,
    Circular,
    Issue,
    Section,
    SectionMap,
)
from backend.presenters import case_out, circular_out
from backend.schemas import SearchInput, SearchResult

logger = logging.getLogger("tax_advisor.kanoon")
logger.setLevel(logging.INFO)
DOCTYPE_QUERY_FILTERS = {
    "supremecourt": "supremecourt",
    "highcourt": "highcourts",
    "itat": "itat",
}
DOCTYPE_ORDER = tuple(DOCTYPE_QUERY_FILTERS)


class HtmlTextExtractor(HTMLParser):
    """Extract readable text from the HTML body returned by Kanoon."""

    BLOCK_TAGS = {"br", "div", "p", "li", "tr", "h1", "h2", "h3"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.skip_depth += 1
        elif self.skip_depth == 0 and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1
        elif self.skip_depth == 0 and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth == 0:
            self.parts.append(data)


class CallBudget:
    def __init__(self, maximum: int):
        self.maximum = maximum
        self.count = 0

    def consume(self) -> None:
        if self.count >= self.maximum:
            raise HTTPException(
                status_code=429,
                detail=(
                    "The configured per-request Kanoon API call limit has been "
                    "reached. Increase KANOON_MAX_API_CALLS_PER_REQUEST only if needed."
                ),
            )
        self.count += 1


def _safe_phrase(value: str) -> str:
    cleaned = " ".join(value.strip().replace('"', "").split())
    return f'"{cleaned}"'


def _build_query(keywords: list[str], section_numbers: list[str], doctype: str) -> str:
    keyword_terms = " ORR ".join(_safe_phrase(item) for item in keywords if item.strip())
    section_terms = " ORR ".join(
        _safe_phrase(f"section {number}") for number in section_numbers if number.strip()
    )
    if not keyword_terms or not section_terms:
        raise HTTPException(
            status_code=400,
            detail="The selected issue and section must have searchable keywords and section numbers.",
        )
    filter_doctype = DOCTYPE_QUERY_FILTERS[doctype]
    return f"({keyword_terms}) ANDD ({section_terms}) doctypes:{filter_doctype}"


def _plain_text(document: Any) -> str:
    if not isinstance(document, str):
        return ""
    parser = HtmlTextExtractor()
    try:
        parser.feed(document)
        parser.close()
    except Exception:
        return document
    return re.sub(r"[ \t]+\n", "\n", "".join(parser.parts)).strip()


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    for parser in (
        lambda text: date.fromisoformat(text[:10]),
        lambda text: datetime.strptime(text, "%d-%m-%Y").date(),
    ):
        try:
            return parser(normalized)
        except ValueError:
            continue
    return None


def _find_cited_sections(full_text: str, sections: list[Section]) -> list[str]:
    cited: set[str] = set()
    for section in sections:
        number = re.escape(section.number.strip())
        if not number:
            continue
        citation = re.compile(
            rf"(?i)(?:section|sec\.?|s\.)\s*{number}(?![\w(])"
        )
        if citation.search(full_text):
            cited.add(section.number)
    return sorted(cited)


def _call_kanoon(
    client: httpx.Client,
    budget: CallBudget,
    path: str,
    *,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    budget.consume()
    started = time.monotonic()
    status_code: int | None = None
    try:
        response = client.get(
            f"{settings.kanoon_api_base_url}{path}",
            params=params,
            headers={
                "Authorization": f"Token {settings.kanoon_api_token}",
                "Accept": "application/json",
            },
        )
        status_code = response.status_code
        logger.info(
            "Kanoon API call",
            extra={
                "method": "GET",
                "path": path,
                "status_code": status_code,
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )
        if status_code == 401:
            raise HTTPException(
                status_code=401,
                detail="Kanoon rejected the configured API token (HTTP 401).",
            )
        if status_code == 403:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Kanoon denied access (HTTP 403). Confirm the token and account "
                    "permissions for search and document retrieval."
                ),
            )
        if status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="Kanoon rate limit reached. Wait before submitting another search.",
            )
        if status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Kanoon request failed with HTTP {status_code}.",
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=502, detail="Kanoon returned an unreadable response."
            ) from exc
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=502, detail="Kanoon returned an unexpected response format."
            )
        return payload
    except HTTPException:
        raise
    except httpx.TimeoutException as exc:
        logger.warning(
            "Kanoon API call timed out",
            extra={"method": "GET", "path": path, "status_code": status_code},
        )
        raise HTTPException(
            status_code=502, detail="Kanoon did not respond before the request timed out."
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning(
            "Kanoon API call failed",
            extra={"method": "GET", "path": path, "status_code": status_code},
        )
        raise HTTPException(
            status_code=502, detail="Kanoon could not be reached for this search."
        ) from exc


def _candidate_doc_id(candidate: dict[str, Any]) -> str | None:
    value = candidate.get("tid") or candidate.get("docid") or candidate.get("doc_id")
    return str(value) if value is not None else None


def _relevant_circulars(
    db: Session, section_ids: list[str], issue_id: str | None
) -> list[Circular]:
    conditions = []
    if section_ids:
        conditions.append(Circular.section_id.in_(section_ids))
    if issue_id:
        conditions.append(Circular.issue_id == issue_id)
    if not conditions:
        return []
    return (
        db.query(Circular)
        .filter(or_(*conditions))
        .order_by(Circular.date.desc().nullslast(), Circular.id)
        .all()
    )


def search_authorities(db: Session, request: SearchInput) -> SearchResult:
    if not settings.kanoon_api_token:
        raise HTTPException(
            status_code=503,
            detail="Kanoon search is not configured. Set KANOON_API_TOKEN in the environment.",
        )

    selected_section = db.get(Section, request.section_id)
    if not selected_section:
        raise HTTPException(status_code=404, detail="The selected section was not found.")

    if request.manual_override:
        section_ids = set(request.manual_section_ids)
        section_ids.add(selected_section.id)
        sections = db.query(Section).filter(Section.id.in_(section_ids)).all()
        if len(sections) != len(section_ids):
            raise HTTPException(
                status_code=400, detail="A manually selected section does not exist."
            )
    else:
        mappings = (
            db.query(SectionMap)
            .filter(
                or_(
                    SectionMap.old_section_id == selected_section.id,
                    SectionMap.new_section_id == selected_section.id,
                )
            )
            .all()
        )
        section_ids = {selected_section.id}
        for mapping in mappings:
            if mapping.old_section_id:
                section_ids.add(mapping.old_section_id)
            if mapping.new_section_id:
                section_ids.add(mapping.new_section_id)
        sections = db.query(Section).filter(Section.id.in_(section_ids)).all()

    sections.sort(key=lambda item: (item.act.year, item.number))
    section_numbers = list(dict.fromkeys(section.number for section in sections))
    if not section_numbers:
        raise HTTPException(
            status_code=400, detail="No section numbers are available for the search."
        )

    issue: Issue | None = None
    keywords: list[str] = []
    if request.issue_id:
        issue = db.get(Issue, request.issue_id)
        if not issue or issue.status != "approved":
            raise HTTPException(
                status_code=400, detail="Select an approved issue or describe another issue."
            )
        keywords.extend(issue.kanoon_keywords or [])
    if request.other_issue and request.other_issue.strip():
        keywords.append(request.other_issue.strip())
    if not keywords:
        raise HTTPException(
            status_code=400, detail="Select an issue with search keywords or describe an issue."
        )

    warnings: list[str] = []
    if len(section_numbers) == 1:
        mappings = (
            db.query(SectionMap)
            .filter(
                or_(
                    SectionMap.old_section_id == selected_section.id,
                    SectionMap.new_section_id == selected_section.id,
                )
            )
            .all()
        )
        if not mappings or all(
            mapping.old_section_id is None or mapping.new_section_id is None
            for mapping in mappings
        ):
            warnings.append("No corresponding section is available in the other Act.")
    if request.manual_override:
        warnings.append("Section mapping was manually overridden for this search.")

    query_displays: list[str] = []
    budget = CallBudget(settings.kanoon_max_api_calls_per_request)
    candidates: list[tuple[str, dict[str, Any]]] = []

    with httpx.Client(timeout=httpx.Timeout(35.0, connect=10.0)) as client:
        for doctype in DOCTYPE_ORDER:
            query = _build_query(keywords, section_numbers, doctype)
            query_displays.append(f"{doctype}: {query}")
            payload = _call_kanoon(
                client,
                budget,
                "/search/",
                params={"formInput": query, "pagenum": "0"},
            )
            documents = payload.get("docs", [])
            if not isinstance(documents, list):
                raise HTTPException(
                    status_code=502,
                    detail=f"Kanoon returned an invalid {doctype} search result.",
                )
            for document in documents[:10]:
                if isinstance(document, dict):
                    candidates.append((doctype, document))

        unique_candidates: list[tuple[str, dict[str, Any], str]] = []
        seen: set[str] = set()
        for doctype, candidate in candidates:
            doc_id = _candidate_doc_id(candidate)
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                unique_candidates.append((doctype, candidate, doc_id))
        if len(seen) > settings.kanoon_max_docs_per_request:
            warnings.append(
                f"Results were capped at {settings.kanoon_max_docs_per_request} unique documents."
            )
        unique_candidates = unique_candidates[: settings.kanoon_max_docs_per_request]

        doc_ids = [doc_id for _, _, doc_id in unique_candidates]
        cached_records = (
            db.query(CaseDocument).filter(CaseDocument.doc_id.in_(doc_ids)).all()
            if doc_ids
            else []
        )
        cached_by_id = {record.doc_id: record for record in cached_records}
        all_sections = db.query(Section).all()
        resolved: list[tuple[str, CaseDocument]] = []

        for doctype, candidate, doc_id in unique_candidates:
            cached = cached_by_id.get(doc_id)
            if cached:
                resolved.append((doctype, cached))
                continue

            if budget.count >= budget.maximum:
                warnings.append(
                    "Some uncached documents were not opened because the configured "
                    "Kanoon API call limit was reached."
                )
                break

            detail = _call_kanoon(client, budget, f"/doc/{quote(doc_id, safe='')}/")
            html = detail.get("doc", "")
            full_text = _plain_text(html)
            title = str(candidate.get("title") or "").strip()
            if not title:
                title = str(detail.get("title") or "").strip()
            if not title:
                title = f"Document {doc_id}"
            court = candidate.get("docsource") or detail.get("docsource")
            bench = candidate.get("bench") or detail.get("bench")
            date_value = (
                candidate.get("date")
                or candidate.get("docdate")
                or detail.get("date")
                or detail.get("docdate")
            )
            case = CaseDocument(
                doc_id=doc_id,
                title=title,
                court=str(court).strip() if court else None,
                bench=str(bench).strip() if bench else None,
                date=_parse_date(date_value),
                full_text=full_text,
                cited_sections=_find_cited_sections(full_text, all_sections),
                # Treatment is intentionally unverified; no status is inferred.
                status=None,
                source_url=f"https://indiankanoon.org/doc/{quote(doc_id, safe='')}/",
                fetched_at=datetime.now(timezone.utc),
            )
            db.merge(case)
            resolved.append((doctype, case))

    circular_rows = _relevant_circulars(db, sorted(section_ids), issue.id if issue else None)
    result = SearchResult(
        cases=[case_out(case, doctype) for doctype, case in resolved],
        circulars=[circular_out(row) for row in circular_rows],
        query_displays=query_displays,
        warnings=warnings,
        kanoon_calls=budget.count,
    )

    old_section_id = selected_section.id if selected_section.act.year == 1961 else None
    new_section_id = selected_section.id if selected_section.act.year == 2025 else None
    for section in sections:
        if section.act.year == 1961 and old_section_id is None:
            old_section_id = section.id
        if section.act.year == 2025 and new_section_id is None:
            new_section_id = section.id
    stored_result = result.model_dump(mode="json")
    db.add(
        Analysis(
            old_section_id=old_section_id,
            new_section_id=new_section_id,
            issue_id=issue.id if issue else None,
            facts=request.facts,
            result_json=stored_result,
        )
    )
    db.commit()
    return result