"""add article review fields

Revision ID: 9b3f4c2f8d1a
Revises: 2c7a76296e9d
Create Date: 2026-01-20 17:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9b3f4c2f8d1a'
down_revision: Union[str, Sequence[str], None] = '2c7a76296e9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('articles', sa.Column('review_status', sa.Text(), nullable=True))
    op.add_column('articles', sa.Column('override_category_id', sa.Text(), nullable=True))
    op.add_column('articles', sa.Column('review_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('articles', sa.Column('review_note', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('articles', 'review_note')
    op.drop_column('articles', 'review_flags')
    op.drop_column('articles', 'override_category_id')
    op.drop_column('articles', 'review_status')
