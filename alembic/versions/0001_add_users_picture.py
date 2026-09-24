"""add users.picture for profile photos

Adds the nullable TEXT "picture" column to the existing users table so that
stored profile-picture references (e.g. /profiles/...) can be persisted
without resetting or losing existing user records.  Idempotent — safe to run
against databases that already have the column.

Revision ID: 0001_users_picture
Revises:
Create Date: 2026-09-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_users_picture"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the picture column if it does not already exist (PostgreSQL)."""
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS picture TEXT")


def downgrade() -> None:
    """Drop the picture column, ignoring it when it never existed."""
    op.execute("ALTER TABLE users DROP COLUMN IF NOT EXISTS picture")