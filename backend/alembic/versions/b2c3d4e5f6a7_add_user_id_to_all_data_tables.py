"""add user_id to all data tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-18 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    "emails",
    "invoices",
    "jobs",
    "payables",
    "recurring_bills",
    "notifications",
    "receivable_checks",
    "app_settings",
]


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("user_id", sa.Integer(), nullable=True))
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
        op.create_foreign_key(f"fk_{table}_user_id", table, "users", ["user_id"], ["id"])

    # Assign all existing data to user 1 (markdjerbaka) as a default
    for table in TABLES:
        op.execute(f"UPDATE {table} SET user_id = 1 WHERE user_id IS NULL")

    # For app_settings: drop old unique on key, add composite unique on (key, user_id)
    # The old unique constraint name varies; use IF EXISTS approach
    op.execute("ALTER TABLE app_settings DROP CONSTRAINT IF EXISTS app_settings_key_key")
    op.execute("ALTER TABLE app_settings DROP CONSTRAINT IF EXISTS uq_app_settings_key")
    op.create_unique_constraint("uq_app_settings_key_user", "app_settings", ["key", "user_id"])

    # Now create per-user copies of shared settings for user 2 (santimaw)
    # Copy bank_balance and outstanding_checks for santimaw with default values
    op.execute("""
        INSERT INTO app_settings (key, value, user_id, is_encrypted)
        SELECT key, '0', 2, false
        FROM app_settings
        WHERE user_id = 1 AND key IN ('bank_balance', 'outstanding_checks')
        AND NOT EXISTS (
            SELECT 1 FROM app_settings a2
            WHERE a2.key = app_settings.key AND a2.user_id = 2
        )
    """)


def downgrade() -> None:
    op.drop_constraint("uq_app_settings_key_user", "app_settings", type_="unique")
    op.create_unique_constraint("app_settings_key_key", "app_settings", ["key"])

    for table in TABLES:
        op.drop_constraint(f"fk_{table}_user_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_column(table, "user_id")
