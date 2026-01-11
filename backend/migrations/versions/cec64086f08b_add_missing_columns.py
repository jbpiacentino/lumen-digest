"""add missing columns

Revision ID: cec64086f08b
Revises: a48ee4a97b3f
Create Date: 2026-01-10 17:44:20.300221

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cec64086f08b'
down_revision: Union[str, Sequence[str], None] = 'a48ee4a97b3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
