from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import Act, Circular, Issue, Section, SectionMap
from backend.presenters import circular_out, issue_out, mapping_out, section_out
from backend.schemas import (
    CircularOut,
    IssueOut,
    SearchInput,
    SearchResult,
    SectionMappingOut,
    SectionOut,
)
from backend.services.search import search_authorities

router = APIRouter(prefix="/api", tags=["research"])


@router.get("/sections", response_model=list[SectionOut])
def list_sections(
    act: Literal[1961, 2025] = Query(...),
    db: Session = Depends(get_db),
) -> list[SectionOut]:
    act_row = db.query(Act).filter(Act.year == act).first()
    if not act_row:
        return []
    rows = (
        db.query(Section)
        .filter(Section.act_id == act_row.id)
        .order_by(Section.chapter.nullsfirst(), Section.number)
        .all()
    )
    return [section_out(row, act_row) for row in rows]


@router.get("/mapping", response_model=list[SectionMappingOut])
def get_section_mappings(
    section_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> list[SectionMappingOut]:
    rows = (
        db.query(SectionMap)
        .filter(
            (SectionMap.old_section_id == section_id)
            | (SectionMap.new_section_id == section_id)
        )
        .order_by(SectionMap.id)
        .all()
    )
    return [mapping_out(row) for row in rows]


@router.get("/issues", response_model=list[IssueOut])
def list_issues(
    section_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> list[IssueOut]:
    if not db.get(Section, section_id):
        raise HTTPException(status_code=404, detail="The selected section was not found.")
    rows = (
        db.query(Issue)
        .filter(Issue.status == "approved", Issue.sections.any(Section.id == section_id))
        .order_by(Issue.name)
        .all()
    )
    return [issue_out(row) for row in rows]


@router.get("/circulars", response_model=list[CircularOut])
def list_circulars(
    section_id: str | None = Query(default=None),
    issue_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[CircularOut]:
    query = db.query(Circular)
    filters = []
    if section_id:
        filters.append(Circular.section_id == section_id)
    if issue_id:
        filters.append(Circular.issue_id == issue_id)
    if filters:
        from sqlalchemy import or_

        query = query.filter(or_(*filters))
    else:
        return []
    rows = query.order_by(Circular.date.desc().nullslast(), Circular.id).all()
    return [circular_out(row) for row in rows]


@router.post("/search", response_model=SearchResult)
def search(
    payload: SearchInput,
    db: Session = Depends(get_db),
) -> SearchResult:
    return search_authorities(db, payload)