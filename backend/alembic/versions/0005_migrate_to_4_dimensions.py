"""Migrate evaluation criteria from 6 to 4 CSS-specific dimensions.

Historical evaluations (scored on the old 6-criteria rubric: relevance, subject_knowledge,
accuracy, reasoning, structure, clarity) are archived into a new `legacy_scores` JSON column
rather than discarded, so no data is silently lost. The new 4 dimension columns
(constitutional_understanding, analytical_depth, subject_expertise, policy_awareness) are left
NULL on existing rows - we never fabricate a score for a rubric the row was not actually
evaluated against. `overall`, `strengths`, `weaknesses`, `missing_info`, `source`,
`is_ai_generated` and `model` are untouched. New evaluations created after this migration
always populate the 4 new columns and leave `legacy_scores` NULL.

Revision ID: 0005
Revises: 0004
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

OLD_CRITERIA = ["relevance", "subject_knowledge", "accuracy", "reasoning", "structure", "clarity"]
NEW_DIMENSIONS = ["constitutional_understanding", "analytical_depth", "subject_expertise", "policy_awareness"]


def upgrade() -> None:
    bind = op.get_context().bind

    op.add_column("evaluations", sa.Column("legacy_scores", sa.JSON, nullable=True))
    for dim in NEW_DIMENSIONS:
        op.add_column("evaluations", sa.Column(dim, sa.Float, nullable=True))

    # Archive each existing row's old 6-criteria scores before dropping those columns.
    rows = bind.execute(sa.text(f"SELECT id, {', '.join(OLD_CRITERIA)} FROM evaluations")).mappings().all()
    for row in rows:
        legacy = {c: row[c] for c in OLD_CRITERIA}
        bind.execute(
            sa.text("UPDATE evaluations SET legacy_scores = :legacy WHERE id = :id"),
            {"legacy": json.dumps(legacy), "id": row["id"]},
        )

    for c in OLD_CRITERIA:
        op.drop_column("evaluations", c)


def downgrade() -> None:
    bind = op.get_context().bind

    for c in OLD_CRITERIA:
        op.add_column("evaluations", sa.Column(c, sa.Float, nullable=True))

    # Restore old scores from the archive where we have it; rows created after the upgrade
    # (genuinely new 4-dimension evaluations) have no legacy archive, so they get NULL, not a
    # fabricated number.
    rows = bind.execute(sa.text("SELECT id, legacy_scores FROM evaluations")).mappings().all()
    for row in rows:
        if not row["legacy_scores"]:
            continue
        legacy = json.loads(row["legacy_scores"])
        bind.execute(
            sa.text(
                "UPDATE evaluations SET relevance=:relevance, subject_knowledge=:subject_knowledge, "
                "accuracy=:accuracy, reasoning=:reasoning, structure=:structure, clarity=:clarity WHERE id=:id"
            ),
            {**legacy, "id": row["id"]},
        )

    for dim in NEW_DIMENSIONS:
        op.drop_column("evaluations", dim)
    op.drop_column("evaluations", "legacy_scores")
