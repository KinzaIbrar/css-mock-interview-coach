"""Copy all user data from one database to another (e.g. local SQLite -> Supabase PostgreSQL).

    cd backend
    .venv\Scripts\python -m scripts.copy_database --source sqlite:///./app.db --target "postgresql://..."

Safe by design: the SOURCE is only read; the TARGET is migrated to the latest schema first and the copy is
refused if the target already contains users (it never overwrites or deletes anything). The question bank is
copied with its ids (answers reference them); startup re-seeding then matches by source_id. Prints row counts only, never passwords or URLs.
"""

import argparse
import sys

from sqlalchemy import create_engine, func, select, text

from app.core.config import Settings
from app.database.migrate import run_migrations
import app.models  # noqa: F401
from app.database.session import Base

# Parents before children (foreign keys). `questions` goes first because answers/interviews reference it by id;
# the startup seeder is an idempotent upsert by source_id, so the copied rows are simply kept.
ORDER = ["questions", "users", "interviews", "answers", "evaluations", "follow_ups", "feedback", "progress"]


def normalise(url: str) -> str:
    return Settings(database_url=url).database_url


def copy(source_url: str, target_url: str) -> dict[str, int]:
    source_url, target_url = normalise(source_url), normalise(target_url)
    run_migrations(target_url)
    src, dst = create_engine(source_url), create_engine(target_url)
    tables = {t.name: t for t in Base.metadata.sorted_tables}
    unknown = [n for n in ORDER if n not in tables]
    if unknown:
        raise SystemExit(f"Unexpected schema, missing tables: {unknown}")
    copied: dict[str, int] = {}
    with src.connect() as s, dst.begin() as d:
        if d.execute(select(func.count()).select_from(tables["users"])).scalar_one():
            raise SystemExit("Target already contains users; refusing to copy over existing data.")
        for name in ORDER:
            rows = [dict(r._mapping) for r in s.execute(select(tables[name]))]
            if name == "questions":
                existing = {r.id: r.source_id for r in d.execute(select(tables[name].c.id, tables[name].c.source_id))}
                if existing:  # the app already seeded the target: keep it, but only if ids line up with the source
                    if existing != {r["id"]: r["source_id"] for r in rows}:
                        raise SystemExit("Target question ids differ from the source; refusing to copy (answers would point at the wrong questions).")
                    copied[name] = len(rows)
                    continue
            if rows:
                d.execute(tables[name].insert(), rows)
            copied[name] = len(rows)
        if dst.dialect.name == "postgresql":  # keep auto-increment ids ahead of the copied ones
            for name in ORDER:
                d.execute(text(f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), COALESCE((SELECT MAX(id) FROM {name}), 1))"))
        # Verify inside the same transaction: counts must match the source exactly.
        for name in ORDER:
            n = d.execute(select(func.count()).select_from(tables[name])).scalar_one()
            if n != copied[name]:
                raise SystemExit(f"Verification failed for {name}: copied {copied[name]}, target has {n}")
    src.dispose(); dst.dispose()
    return copied


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True)
    ap.add_argument("--target", required=True)
    a = ap.parse_args()
    for table, n in copy(a.source, a.target).items():
        print(f"{table}: {n} row(s) copied")
    sys.exit(0)
