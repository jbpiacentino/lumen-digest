"""add clusters tables

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-01-23 17:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "clusters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="ready"),
        sa.Column("model", sa.String(), nullable=False, server_default="nmf"),
        sa.Column("n_components", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="uncategorized"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_clusters_language", "clusters", ["language"])

    op.create_table(
        "cluster_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
    )
    op.create_index("ix_cluster_members_cluster_id", "cluster_members", ["cluster_id"])
    op.create_index("ix_cluster_members_article_id", "cluster_members", ["article_id"])

    op.create_table(
        "cluster_anchors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("phrase", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
    )
    op.create_index("ix_cluster_anchors_cluster_id", "cluster_anchors", ["cluster_id"])

    op.create_table(
        "cluster_mappings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_cluster_mappings_cluster_id", "cluster_mappings", ["cluster_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_cluster_mappings_cluster_id", table_name="cluster_mappings")
    op.drop_table("cluster_mappings")
    op.drop_index("ix_cluster_anchors_cluster_id", table_name="cluster_anchors")
    op.drop_table("cluster_anchors")
    op.drop_index("ix_cluster_members_article_id", table_name="cluster_members")
    op.drop_index("ix_cluster_members_cluster_id", table_name="cluster_members")
    op.drop_table("cluster_members")
    op.drop_index("ix_clusters_language", table_name="clusters")
    op.drop_table("clusters")
