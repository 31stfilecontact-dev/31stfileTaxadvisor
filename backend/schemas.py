"""FastAPI request and response models; mirrors the generated OpenAPI contract."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Relation = Literal["one_to_one", "one_to_many", "many_to_one", "merged", "omitted", "new"]
IssueStatus = Literal["curated", "suggested", "approved", "rejected"]
CircularType = Literal["circular", "notification", "instruction", "clarification", "aar", "dtaa"]
CircularEffect = Literal["favourable", "adverse", "neutral"]
CircularStatus = Literal["active", "withdrawn", "superseded", "saved_under_2025"]
CaseStatus = Literal["good", "reversed", "stayed", "overruled"]


class SectionOut(BaseModel):
    id: str
    act_id: str
    act_year: Literal[1961, 2025]
    chapter: str | None
    number: str
    title: str
    text: str | None
    parent_id: str | None


class SectionSummary(BaseModel):
    id: str
    act_id: str
    act_year: Literal[1961, 2025]
    number: str
    title: str


class MappingInput(BaseModel):
    old_section_id: str | None
    new_section_id: str | None
    relation: Relation
    notes: str | None = None
    source_ref: str | None = None

    @model_validator(mode="after")
    def validate_sides(self):
        if not self.old_section_id and not self.new_section_id:
            raise ValueError("A mapping must refer to at least one section.")
        if self.relation == "new" and (self.old_section_id or not self.new_section_id):
            raise ValueError("A new-section mapping must have only a 2025 section.")
        if self.relation == "omitted" and (not self.old_section_id or self.new_section_id):
            raise ValueError("An omitted-section mapping must have only a 1961 section.")
        if self.relation not in {"new", "omitted"} and (
            not self.old_section_id or not self.new_section_id
        ):
            raise ValueError("This mapping relation requires both section IDs.")
        return self


class SectionMappingOut(BaseModel):
    id: str
    old_section_id: str | None
    new_section_id: str | None
    relation: Relation
    notes: str | None
    source_ref: str | None
    old_section: SectionSummary | None
    new_section: SectionSummary | None


class IssueOut(BaseModel):
    id: str
    name: str
    kanoon_keywords: list[str]
    tier: int
    status: IssueStatus
    section_ids: list[str]


class IssueInput(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    kanoon_keywords: list[str] = Field(default_factory=list)
    tier: int = Field(default=1, ge=1, le=5)
    status: IssueStatus = "suggested"
    section_ids: list[str] = Field(default_factory=list)


class CircularOut(BaseModel):
    id: str
    act_year: Literal[1961, 2025]
    type: CircularType
    number: str | None
    date: date | None
    section_id: str | None
    issue_id: str | None
    summary: str
    effect: CircularEffect
    status: CircularStatus
    applicable_from: date | None
    source_url: str | None


class SearchInput(BaseModel):
    section_id: str
    issue_id: str | None = None
    other_issue: str | None = Field(default=None, max_length=240)
    facts: str = Field(min_length=1, max_length=12000)
    assessment_year: str | None = Field(default=None, max_length=20)
    manual_section_ids: list[str] = Field(default_factory=list)
    manual_override: bool = False


class CaseResult(BaseModel):
    doc_id: str
    title: str
    court: str | None
    bench: str | None
    date: date | None
    cited_sections: list[str]
    status: CaseStatus | None
    source_url: str | None
    doctype: str


class SearchResult(BaseModel):
    cases: list[CaseResult]
    circulars: list[CircularOut]
    query_displays: list[str]
    warnings: list[str]
    kanoon_calls: int


class SectionUpdate(BaseModel):
    id: str
    act_id: str
    act_year: Literal[1961, 2025]
    chapter: str | None
    number: str
    title: str
    text: str | None
    parent_id: str | None = None


class AdminLoginInput(BaseModel):
    password: str = Field(min_length=1, max_length=512)


class AdminSessionOut(BaseModel):
    authenticated: bool


class TeamSessionOut(BaseModel):
    authenticated: bool