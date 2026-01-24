"""add anchors table

Revision ID: a1b2c3d4e5f6
Revises: 9c4d5e6f7a8b
Create Date: 2026-01-23 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9c4d5e6f7a8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "anchors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category_id", sa.String(), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_article_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_anchors_category_id", "anchors", ["category_id"])
    op.create_index("ix_anchors_language", "anchors", ["language"])
    op.create_index("ix_anchors_source_article_id", "anchors", ["source_article_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_anchors_source_article_id", table_name="anchors")
    op.drop_index("ix_anchors_language", table_name="anchors")
    op.drop_index("ix_anchors_category_id", table_name="anchors")
    op.drop_table("anchors")
