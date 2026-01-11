"""add auto_id and freshrss_id

Revision ID: dd887efa8901
Revises: cec64086f08b
Create Date: 2026-01-10 17:58:22.016574

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd887efa8901'
down_revision: Union[str, Sequence[str], None] = 'cec64086f08b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
