from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from backend.auth import get_current_member
from backend.db import get_db
from backend.models import Act, Issue, Section, SectionMap
from backend.presenters import issue_out, mapping_out, section_out
from backend.schemas import (
    AdminLoginInput,
    AdminSessionOut,
    IssueInput,
    IssueOut,
    MappingInput,
    SectionMappingOut,
    SectionOut,
    SectionUpdate,
)
from backend.security import clear_admin_session, create_admin_session, require_admin

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_member)],
)


@router.post("/login", response_model=AdminSessionOut)
def admin_login(
    payload: AdminLoginInput,
    request: Request,
    response: Response,
) -> AdminSessionOut:
    create_admin_session(payload.password, request, response)
    return AdminSessionOut(authenticated=True)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def admin_logout(request: Request, response: Response) -> Response:
    clear_admin_session(request, response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/session", response_model=AdminSessionOut)
def admin_session(
    _admin: None = Depends(require_admin),
) -> AdminSessionOut:
    return AdminSessionOut(authenticated=True)


def _validate_section_pair(
    db: Session, old_section_id: str | None, new_section_id: str | None
) -> None:
    old_section = db.get(Section, old_section_id) if old_section_id else None
    new_section = db.get(Section, new_section_id) if new_section_id else None
    if old_section_id and (not old_section or old_section.act.year != 1961):
        raise HTTPException(
            status_code=400, detail="The old section must belong to the 1961 Act."
        )
    if new_section_id and (not new_section or new_section.act.year != 2025):
        raise HTTPException(
            status_code=400, detail="The new section must belong to the 2025 Act."
        )
    if not old_section_id and not new_section_id:
        raise HTTPException(status_code=400, detail="A mapping needs at least one section.")


def _update_mapping(mapping: SectionMap, payload: MappingInput) -> None:
    mapping.old_section_id = payload.old_section_id
    mapping.new_section_id = payload.new_section_id
    mapping.relation = payload.relation
    mapping.notes = payload.notes
    mapping.source_ref = payload.source_ref


def _update_issue_sections(db: Session, issue: Issue, ids: list[str]) -> None:
    unique_ids = list(dict.fromkeys(ids))
    sections = db.query(Section).filter(Section.id.in_(unique_ids)).all() if unique_ids else []
    if len(sections) != len(unique_ids):
        raise HTTPException(status_code=400, detail="One or more issue sections do not exist.")
    issue.sections = sections


@router.get("/sections", response_model=list[SectionOut])
def admin_list_sections(
    _admin: None = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[SectionOut]:
    rows = db.query(Section).join(Act).order_by(Act.year, Section.chapter, Section.number).all()
    return [section_out(row) for row in rows]


@router.patch("/sections", response_model=SectionOut)
def admin_update_section(
    payload: SectionUpdate,
    _admin: None = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SectionOut:
    row = db.get(Section, payload.id)
    act = db.get(Act, payload.act_id)
    if not row or not act:
        raise HTTPException(status_code=404, detail="Section or Act was not found.")
    if act.year != payload.act_year:
        raise HTTPException(status_code=400, detail="Act year does not match the selected Act.")
    if payload.parent_id and not db.get(Section, payload.parent_id):
        raise HTTPException(status_code=400, detail="Parent section was not found.")
    row.act_id = payload.act_id
    row.chapter = payload.chapter
    row.number = payload.number
    row.title = payload.title
    row.text = payload.text
    row.parent_id = payload.parent_id
    db.commit()
    db.refresh(row)
    return section_out(row, act)


@router.get("/mappings", response_model=list[SectionMappingOut])
def admin_list_mappings(
    _admin: None = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[SectionMappingOut]:
    return [mapping_out(row) for row in db.query(SectionMap).order_by(SectionMap.id).all()]


@router.post(
    "/mappings", response_model=SectionMappingOut, status_code=status.HTTP_201_CREATED
)
def admin_create_mapping(
    payload: MappingInput,
    _admin: None = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SectionMappingOut:
    _validate_section_pair(db, payload.old_section_id, payload.new_section_id)
    row = SectionMap(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return mapping_out(row)


@router.patch("/mappings/{mapping_id}", response_model=SectionMappingOut)
def admin_update_mapping(
    mapping_id: str,
    payload: MappingInput,
    _admin: None = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SectionMappingOut:
    row = db.get(SectionMap, mapping_id)
    if not row:
        raise HTTPException(status_code=404, detail="Section mapping was not found.")
    _validate_section_pair(db, payload.old_section_id, payload.new_section_id)
    _update_mapping(row, payload)
    db.commit()
    db.refresh(row)
    return mapping_out(row)


@router.delete("/mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_mapping(
    mapping_id: str,
    _admin: None = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    row = db.get(SectionMap, mapping_id)
    if not row:
        raise HTTPException(status_code=404, detail="Section mapping was not found.")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/issues", response_model=list[IssueOut])
def admin_list_issues(
    _admin: None = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[IssueOut]:
    rows = db.query(Issue).order_by(Issue.name).all()
    return [issue_out(row) for row in rows]


@router.post("/issues", response_model=IssueOut, status_code=status.HTTP_201_CREATED)
def admin_create_issue(
    payload: IssueInput,
    _admin: None = Depends(require_admin),
    db: Session = Depends(get_db),
) -> IssueOut:
    row = Issue(
        name=payload.name,
        kanoon_keywords=payload.kanoon_keywords,
        tier=payload.tier,
        status=payload.status,
    )
    _update_issue_sections(db, row, payload.section_ids)
    db.add(row)
    db.commit()
    db.refresh(row)
    return issue_out(row)


@router.patch("/issues/{issue_id}", response_model=IssueOut)
def admin_update_issue(
    issue_id: str,
    payload: IssueInput,
    _admin: None = Depends(require_admin),
    db: Session = Depends(get_db),
) -> IssueOut:
    row = db.get(Issue, issue_id)
    if not row:
        raise HTTPException(status_code=404, detail="Issue was not found.")
    row.name = payload.name
    row.kanoon_keywords = payload.kanoon_keywords
    row.tier = payload.tier
    row.status = payload.status
    _update_issue_sections(db, row, payload.section_ids)
    db.commit()
    db.refresh(row)
    return issue_out(row)


def _set_issue_status(db: Session, issue_id: str, value: str) -> IssueOut:
    row = db.get(Issue, issue_id)
    if not row:
        raise HTTPException(status_code=404, detail="Issue was not found.")
    row.status = value
    db.commit()
    db.refresh(row)
    return issue_out(row)


@router.post("/issues/{issue_id}/approve", response_model=IssueOut)
def admin_approve_issue(
    issue_id: str,
    _admin: None = Depends(require_admin),
    db: Session = Depends(get_db),
) -> IssueOut:
    return _set_issue_status(db, issue_id, "approved")


@router.post("/issues/{issue_id}/reject", response_model=IssueOut)
def admin_reject_issue(
    issue_id: str,
    _admin: None = Depends(require_admin),
    db: Session = Depends(get_db),
) -> IssueOut:
    return _set_issue_status(db, issue_id, "rejected")