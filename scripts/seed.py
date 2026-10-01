"""Load the supplied official section, mapping, and circular JSON files."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db import get_session_factory  # noqa: E402
from backend.models import Act, Circular, Issue, Section, SectionMap  # noqa: E402

DATA_DIR = ROOT / "data"
NAMESPACE = uuid.UUID("5d0a31ba-32ac-4c4b-93bf-a0e06b3bd8de")
RELATIONS = {
    "one_to_one",
    "one_to_many",
    "many_to_one",
    "merged",
    "omitted",
    "new",
}


def read_rows(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, list):
        raise ValueError(f"{filename} must contain a JSON array.")
    if any(not isinstance(row, dict) for row in value):
        raise ValueError(f"Every row in {filename} must be a JSON object.")
    return value


def parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def section_key(year: int, number: str) -> str:
    safe_number = re.sub(r"[^a-zA-Z0-9]+", "-", number.strip()).strip("-").lower()
    return f"it{year}-{safe_number}"


def deterministic_id(kind: str, value: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{kind}:{value}"))


def load_sections(session, year: int, filename: str, act_id: str) -> dict[str, Section]:
    by_id: dict[str, Section] = {}
    for item in read_rows(filename):
        number = str(item.get("number", "")).strip()
        title = str(item.get("title", "")).strip()
        if not number or not title:
            raise ValueError(f"Each row in {filename} needs number and title.")
        section_id = str(item.get("id") or section_key(year, number))
        row = Section(
            id=section_id,
            act_id=act_id,
            chapter=item.get("chapter"),
            number=number,
            title=title,
            text=item.get("text"),
            parent_id=item.get("parent_id"),
        )
        session.merge(row)
        by_id[section_id] = row
    return by_id


def resolve_section(
    reference: str | None,
    sections_by_id: dict[str, Section],
    sections_by_number: dict[str, Section],
) -> Section | None:
    if not reference:
        return None
    return sections_by_id.get(reference) or sections_by_number.get(reference.strip())


def main() -> None:
    with get_session_factory()() as session:
        act_1961 = Act(id="income-tax-1961", name="Income-tax Act, 1961", year=1961)
        act_2025 = Act(id="income-tax-2025", name="Income-tax Act, 2025", year=2025)
        session.merge(act_1961)
        session.merge(act_2025)
        session.flush()

        old_by_id = load_sections(
            session, 1961, "sections_old.json", act_1961.id
        )
        new_by_id = load_sections(
            session, 2025, "sections_new.json", act_2025.id
        )
        session.flush()
        old_by_number = {section.number: section for section in old_by_id.values()}
        new_by_number = {section.number: section for section in new_by_id.values()}

        map_rows: list[SectionMap] = []
        for item in read_rows("section_map.json"):
            relation = item.get("relation")
            if relation not in RELATIONS:
                raise ValueError(
                    "Each section-map row needs an explicit official relation "
                    "from the supported relation list."
                )
            old_ref = item.get("old_section_id") or item.get("old_section_number")
            new_ref = item.get("new_section_id") or item.get("new_section_number")
            old_section = resolve_section(old_ref, old_by_id, old_by_number)
            new_section = resolve_section(new_ref, new_by_id, new_by_number)
            if old_ref and not old_section:
                raise ValueError(f"Could not resolve old section reference {old_ref!r}.")
            if new_ref and not new_section:
                raise ValueError(f"Could not resolve new section reference {new_ref!r}.")
            if not old_section and not new_section:
                raise ValueError("A mapping row must refer to at least one known section.")
            if relation == "new" and (old_section or not new_section):
                raise ValueError("A relation 'new' row must refer only to a 2025 section.")
            if relation == "omitted" and (not old_section or new_section):
                raise ValueError("A relation 'omitted' row must refer only to a 1961 section.")
            if relation not in {"new", "omitted"} and (not old_section or not new_section):
                raise ValueError(f"Relation {relation!r} requires both section references.")

            old_id = old_section.id if old_section else None
            new_id = new_section.id if new_section else None
            identity = "|".join(
                [old_id or "", new_id or "", relation, str(item.get("source_ref") or "")]
            )
            mapping = SectionMap(
                id=str(item.get("id") or deterministic_id("mapping", identity)),
                old_section_id=old_id,
                new_section_id=new_id,
                relation=relation,
                notes=item.get("notes"),
                source_ref=item.get("source_ref"),
            )
            session.merge(mapping)
            map_rows.append(mapping)
        session.flush()

        seeded_issues = 0
        for item in read_rows("issues_seed.json"):
            old_number = item.get("section_number_old")
            old_section = old_by_number.get(str(old_number)) if old_number else None
            if not old_section:
                print(
                    f"Skipped issue {item.get('name', '(unnamed)')!r}: "
                    f"1961 section {old_number!r} is not in sections_old.json."
                )
                continue
            related_ids = {old_section.id}
            for mapping in map_rows:
                if mapping.old_section_id == old_section.id and mapping.new_section_id:
                    related_ids.add(mapping.new_section_id)
            related_sections = [
                session.get(Section, section_id)
                for section_id in sorted(related_ids)
            ]
            issue_id = str(
                item.get("id")
                or deterministic_id("issue", str(item.get("name", "unnamed")))
            )
            session.merge(
                Issue(
                    id=issue_id,
                    name=str(item["name"]),
                    kanoon_keywords=item.get("kanoon_keywords", []),
                    tier=int(item.get("tier", 1)),
                    status=item.get("status", "approved"),
                )
            )
            session.flush()
            issue = session.get(Issue, issue_id)
            issue.sections = [row for row in related_sections if row is not None]
            seeded_issues += 1

        for item in read_rows("circulars_seed.json"):
            act_year = int(item["act_year"])
            act = session.query(Act).filter(Act.year == act_year).one()
            section_ref = item.get("section_id") or item.get("section_number")
            section = (
                resolve_section(
                    str(section_ref),
                    old_by_id if act_year == 1961 else new_by_id,
                    old_by_number if act_year == 1961 else new_by_number,
                )
                if section_ref
                else None
            )
            if section_ref and not section:
                raise ValueError(f"Could not resolve circular section {section_ref!r}.")
            identity = "|".join(
                [
                    str(act_year),
                    str(item.get("type", "")),
                    str(item.get("number", "")),
                    str(item.get("date", "")),
                    str(item.get("source_url", "")),
                ]
            )
            session.merge(
                Circular(
                    id=str(item.get("id") or deterministic_id("circular", identity)),
                    act_id=act.id,
                    type=item["type"],
                    number=item.get("number"),
                    date=parse_date(item.get("date")),
                    section_id=section.id if section else None,
                    issue_id=item.get("issue_id"),
                    summary=item["summary"],
                    effect=item["effect"],
                    status=item["status"],
                    applicable_from=parse_date(item.get("applicable_from")),
                    source_url=item.get("source_url"),
                )
            )

        session.commit()
        print(
            "Seed complete: "
            f"{len(old_by_id)} old sections, {len(new_by_id)} new sections, "
            f"{len(map_rows)} official mappings, {seeded_issues} issues."
        )


if __name__ == "__main__":
    main()