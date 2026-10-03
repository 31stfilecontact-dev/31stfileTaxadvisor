"""SQLAlchemy tables for tax provisions, authorities, and research records."""

from __future__ import annotations

from datetime import date, datetime
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Column,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


issue_sections = Table(
    "issue_sections",
    Base.metadata,
    Column("issue_id", String, ForeignKey("issues.id", ondelete="CASCADE"), primary_key=True),
    Column("section_id", String, ForeignKey("sections.id", ondelete="CASCADE"), primary_key=True),
)


class Act(Base):
    __tablename__ = "acts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    year: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    in_force_from: Mapped[date | None] = mapped_column(Date)
    in_force_until: Mapped[date | None] = mapped_column(Date)
    sections: Mapped[list["Section"]] = relationship(back_populates="act")


class Section(Base):
    __tablename__ = "sections"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    act_id: Mapped[str] = mapped_column(ForeignKey("acts.id"), nullable=False, index=True)
    chapter: Mapped[str | None] = mapped_column(String(120))
    number: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("sections.id"))
    act: Mapped[Act] = relationship(back_populates="sections")

    __table_args__ = (
        UniqueConstraint("act_id", "number", name="uq_sections_act_number"),
        Index("ix_sections_number", "number"),
    )


class SectionMap(Base):
    __tablename__ = "section_map"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    old_section_id: Mapped[str | None] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), index=True
    )
    new_section_id: Mapped[str | None] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), index=True
    )
    relation: Mapped[str] = mapped_column(String(30), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    source_ref: Mapped[str | None] = mapped_column(Text)
    old_section: Mapped[Section | None] = relationship(
        foreign_keys=[old_section_id], lazy="joined"
    )
    new_section: Mapped[Section | None] = relationship(
        foreign_keys=[new_section_id], lazy="joined"
    )

    __table_args__ = (
        CheckConstraint(
            "(old_section_id IS NOT NULL) OR (new_section_id IS NOT NULL)",
            name="ck_section_map_has_section",
        ),
    )


class Issue(Base):
    __tablename__ = "issues"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    kanoon_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="suggested")
    sections: Mapped[list[Section]] = relationship(secondary=issue_sections, lazy="selectin")

    __table_args__ = (
        CheckConstraint("tier >= 1 AND tier <= 5", name="ck_issues_tier_range"),
        CheckConstraint(
            "status IN ('curated', 'suggested', 'approved', 'rejected')",
            name="ck_issues_status",
        ),
    )


class CaseDocument(Base):
    __tablename__ = "cases"
    doc_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    court: Mapped[str | None] = mapped_column(String(240))
    bench: Mapped[str | None] = mapped_column(String(240))
    date: Mapped[date | None] = mapped_column(Date)
    full_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cited_sections: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str | None] = mapped_column(String(20))
    source_url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IS NULL OR status IN ('good', 'reversed', 'stayed', 'overruled')",
            name="ck_cases_treatment_status",
        ),
    )


class CaseChunk(Base):
    __tablename__ = "case_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(
        ForeignKey("cases.doc_id", ondelete="CASCADE"), nullable=False, index=True
    )
    para_no: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))


class Circular(Base):
    __tablename__ = "circulars"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    act_id: Mapped[str] = mapped_column(ForeignKey("acts.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(24), nullable=False)
    number: Mapped[str | None] = mapped_column(String(120))
    date: Mapped[date | None] = mapped_column(Date)
    section_id: Mapped[str | None] = mapped_column(ForeignKey("sections.id"), index=True)
    issue_id: Mapped[str | None] = mapped_column(ForeignKey("issues.id"), index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    effect: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    applicable_from: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "type IN ('circular', 'notification', 'instruction', 'clarification', 'aar', 'dtaa')",
            name="ck_circulars_type",
        ),
        CheckConstraint(
            "effect IN ('favourable', 'adverse', 'neutral')", name="ck_circulars_effect"
        ),
        CheckConstraint(
            "status IN ('active', 'withdrawn', 'superseded', 'saved_under_2025')",
            name="ck_circulars_status",
        ),
    )


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    old_section_id: Mapped[str | None] = mapped_column(ForeignKey("sections.id"))
    new_section_id: Mapped[str | None] = mapped_column(ForeignKey("sections.id"))
    issue_id: Mapped[str | None] = mapped_column(ForeignKey("issues.id"))
    owner_user_id: Mapped[str | None] = mapped_column(String(255), index=True)
    facts: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    feedback: Mapped[dict | None] = mapped_column(JSONB)