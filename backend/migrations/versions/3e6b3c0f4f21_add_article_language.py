"""add article language

Revision ID: 3e6b3c0f4f21
Revises: 9b3f4c2f8d1a
Create Date: 2026-01-20 18:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e6b3c0f4f21'
down_revision: Union[str, Sequence[str], None] = '9b3f4c2f8d1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('articles', sa.Column('language', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('articles', 'language')
