"""Phase 4: follow-up questions and AI model metadata.

- new table `follow_ups` (one optional follow-up per answer)
- `evaluations.model` and `feedback.model`: which LLM produced an AI-generated record (NULL otherwise)

Existing rows are untouched (their `source` already says 'dev_heuristic' / 'dev_rules').

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evaluations") as batch:
        batch.add_column(sa.Column("model", sa.String(64), nullable=True))
    with op.batch_alter_table("feedback") as batch:
        batch.add_column(sa.Column("model", sa.String(64), nullable=True))
    op.create_table(
        "follow_ups",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("answer_id", sa.Integer, sa.ForeignKey("answers.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("question_text", sa.Text, nullable=False),
        sa.Column("answer_text", sa.Text, nullable=True),
        sa.Column("time_taken_seconds", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("follow_ups")
    with op.batch_alter_table("feedback") as batch:
        batch.drop_column("model")
    with op.batch_alter_table("evaluations") as batch:
        batch.drop_column("model")
