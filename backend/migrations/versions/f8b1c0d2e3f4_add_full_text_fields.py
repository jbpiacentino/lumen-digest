"""add full text fields

Revision ID: f8b1c0d2e3f4
Revises: 3e6b3c0f4f21
Create Date: 2026-01-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f8b1c0d2e3f4"
down_revision: Union[str, Sequence[str], None] = "3e6b3c0f4f21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("articles", sa.Column("full_text", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("full_text_source", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("articles", "full_text_source")
    op.drop_column("articles", "full_text")
