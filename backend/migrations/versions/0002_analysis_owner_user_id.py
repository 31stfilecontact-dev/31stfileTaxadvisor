"""Associate saved research records with the authenticated firm user."""

from alembic import op
import sqlalchemy as sa

revision = "0002_analysis_owner_user_id"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column("owner_user_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_analyses_owner_user_id",
        "analyses",
        ["owner_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_analyses_owner_user_id", table_name="analyses")
    op.drop_column("analyses", "owner_user_id")