"""add users table

Revision ID: 9c4d5e6f7a8b
Revises: 8b7d12c4a5f6
Create Date: 2026-01-12 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c4d5e6f7a8b"
down_revision: Union[str, Sequence[str], None] = "8b7d12c4a5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()
    if "users" not in table_names:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)
    else:
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("users")}
        if "ix_users_email" not in existing_indexes:
            op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
