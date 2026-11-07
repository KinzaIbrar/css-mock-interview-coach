"""Baseline: the Phase 3 schema (7 tables).

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("preferences", sa.JSON, nullable=False),
        *_ts(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("subject", sa.String(64), nullable=False),
        sa.Column("topic", sa.String(128), nullable=False),
        sa.Column("difficulty", sa.String(16), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("reference_answer", sa.Text, nullable=False),
        sa.Column("keywords", sa.JSON, nullable=False),
        sa.Column("is_sample", sa.Boolean, nullable=False),
        *_ts(),
    )
    op.create_index("ix_questions_source_id", "questions", ["source_id"], unique=True)
    op.create_index("ix_questions_subject", "questions", ["subject"])
    op.create_index("ix_questions_difficulty", "questions", ["difficulty"])

    op.create_table(
        "interviews",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject", sa.String(64), nullable=False),
        sa.Column("difficulty", sa.String(16), nullable=False),
        sa.Column("num_questions", sa.Integer, nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("current_index", sa.Integer, nullable=False),
        sa.Column("question_ids", sa.JSON, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("overall_score", sa.Float, nullable=True),
        *_ts(),
    )
    op.create_index("ix_interviews_user_id", "interviews", ["user_id"])
    op.create_index("ix_interviews_status", "interviews", ["status"])

    op.create_table(
        "answers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("interview_id", sa.Integer, sa.ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("order_index", sa.Integer, nullable=False),
        sa.Column("answer_text", sa.Text, nullable=False),
        sa.Column("time_taken_seconds", sa.Integer, nullable=True),
        *_ts(),
        sa.UniqueConstraint("interview_id", "order_index", name="uq_answer_interview_order"),
    )
    op.create_index("ix_answers_interview_id", "answers", ["interview_id"])

    op.create_table(
        "evaluations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("answer_id", sa.Integer, sa.ForeignKey("answers.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("relevance", sa.Float, nullable=False),
        sa.Column("subject_knowledge", sa.Float, nullable=False),
        sa.Column("accuracy", sa.Float, nullable=False),
        sa.Column("reasoning", sa.Float, nullable=False),
        sa.Column("structure", sa.Float, nullable=False),
        sa.Column("clarity", sa.Float, nullable=False),
        sa.Column("overall", sa.Float, nullable=False),
        sa.Column("strengths", sa.JSON, nullable=False),
        sa.Column("weaknesses", sa.JSON, nullable=False),
        sa.Column("missing_info", sa.JSON, nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("is_ai_generated", sa.Boolean, nullable=False),
        *_ts(),
    )

    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("interview_id", sa.Integer, sa.ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("improvements", sa.JSON, nullable=False),
        sa.Column("model_answers", sa.JSON, nullable=False),
        sa.Column("revision_topics", sa.JSON, nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("is_ai_generated", sa.Boolean, nullable=False),
        *_ts(),
    )

    op.create_table(
        "progress",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject", sa.String(64), nullable=False),
        sa.Column("sessions_count", sa.Integer, nullable=False),
        sa.Column("avg_score", sa.Float, nullable=False),
        sa.Column("best_score", sa.Float, nullable=False),
        sa.Column("last_score", sa.Float, nullable=False),
        sa.Column("last_session_at", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
        sa.UniqueConstraint("user_id", "subject", name="uq_progress_user_subject"),
    )
    op.create_index("ix_progress_user_id", "progress", ["user_id"])


def downgrade() -> None:
    for table in ("progress", "feedback", "evaluations", "answers", "interviews", "questions", "users"):
        op.drop_table(table)
