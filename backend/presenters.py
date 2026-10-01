"""Serialize SQLAlchemy rows into the public API response models."""

from backend.models import Act, CaseDocument, Circular, Issue, Section, SectionMap
from backend.schemas import (
    CaseResult,
    CircularOut,
    IssueOut,
    SectionMappingOut,
    SectionOut,
    SectionSummary,
)


def section_out(section: Section, act: Act | None = None) -> SectionOut:
    act = act or section.act
    return SectionOut(
        id=section.id,
        act_id=section.act_id,
        act_year=act.year,
        chapter=section.chapter,
        number=section.number,
        title=section.title,
        text=section.text,
        parent_id=section.parent_id,
    )


def section_summary(section: Section | None) -> SectionSummary | None:
    if section is None:
        return None
    return SectionSummary(
        id=section.id,
        act_id=section.act_id,
        act_year=section.act.year,
        number=section.number,
        title=section.title,
    )


def mapping_out(mapping: SectionMap) -> SectionMappingOut:
    return SectionMappingOut(
        id=mapping.id,
        old_section_id=mapping.old_section_id,
        new_section_id=mapping.new_section_id,
        relation=mapping.relation,
        notes=mapping.notes,
        source_ref=mapping.source_ref,
        old_section=section_summary(mapping.old_section),
        new_section=section_summary(mapping.new_section),
    )


def issue_out(issue: Issue) -> IssueOut:
    return IssueOut(
        id=issue.id,
        name=issue.name,
        kanoon_keywords=issue.kanoon_keywords or [],
        tier=issue.tier,
        status=issue.status,
        section_ids=sorted(section.id for section in issue.sections),
    )


def circular_out(circular: Circular) -> CircularOut:
    return CircularOut(
        id=circular.id,
        act_year=circular.act.year,
        type=circular.type,
        number=circular.number,
        date=circular.date,
        section_id=circular.section_id,
        issue_id=circular.issue_id,
        summary=circular.summary,
        effect=circular.effect,
        status=circular.status,
        applicable_from=circular.applicable_from,
        source_url=circular.source_url,
    )


def case_out(case: CaseDocument, doctype: str) -> CaseResult:
    return CaseResult(
        doc_id=case.doc_id,
        title=case.title,
        court=case.court,
        bench=case.bench,
        date=case.date,
        cited_sections=case.cited_sections or [],
        status=case.status,
        source_url=case.source_url,
        doctype=doctype,
    )