"""Phase 5: add evaluation_criteria, tags and explanation to questions.

Existing rows are preserved; new columns get empty defaults and are filled the next time the
dataset is loaded (startup seeding upserts by source_id).

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("questions") as batch:
        batch.add_column(sa.Column("evaluation_criteria", sa.JSON, nullable=False, server_default="[]"))
        batch.add_column(sa.Column("tags", sa.JSON, nullable=False, server_default="[]"))
        batch.add_column(sa.Column("explanation", sa.Text, nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("questions") as batch:
        batch.drop_column("explanation")
        batch.drop_column("tags")
        batch.drop_column("evaluation_criteria")
