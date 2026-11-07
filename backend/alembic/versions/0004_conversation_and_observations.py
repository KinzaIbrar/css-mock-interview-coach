"""Phase 6: conversational interview support.

- interviews.intro_required / introduction: optional "Tell me about yourself" opening turn
- interviews.observations: AGGREGATE non-verbal metrics reported by the browser (never raw video or frames)
- follow_ups.{overall,evaluation,source,is_ai_generated,model}: each follow-up reply is evaluated separately

Existing rows are untouched (all new columns are nullable or default to false).

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("interviews") as batch:
        batch.add_column(sa.Column("intro_required", sa.Boolean, nullable=False, server_default="0"))
        batch.add_column(sa.Column("introduction", sa.Text, nullable=True))
        batch.add_column(sa.Column("observations", sa.JSON, nullable=True))
    with op.batch_alter_table("follow_ups") as batch:
        batch.add_column(sa.Column("overall", sa.Float, nullable=True))
        batch.add_column(sa.Column("evaluation", sa.JSON, nullable=True))
        batch.add_column(sa.Column("source", sa.String(32), nullable=True))
        batch.add_column(sa.Column("is_ai_generated", sa.Boolean, nullable=False, server_default="0"))
        batch.add_column(sa.Column("model", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("follow_ups") as batch:
        for col in ("model", "is_ai_generated", "source", "evaluation", "overall"):
            batch.drop_column(col)
    with op.batch_alter_table("interviews") as batch:
        for col in ("observations", "introduction", "intro_required"):
            batch.drop_column(col)
