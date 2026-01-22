"""add full text format

Revision ID: 8b7d12c4a5f6
Revises: f8b1c0d2e3f4
Create Date: 2026-01-12 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8b7d12c4a5f6"
down_revision: Union[str, Sequence[str], None] = "f8b1c0d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("articles", sa.Column("full_text_format", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("articles", "full_text_format")
