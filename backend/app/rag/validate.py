"""Command-line dataset checker.

    cd backend
    .venv\Scripts\python -m app.rag.validate            # validates data/questions/
    .venv\Scripts\python -m app.rag.validate path.json  # a file or directory

Exit code 0 = valid, 1 = invalid.
"""

import sys
from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.rag.dataset import DatasetError, read_raw_items, validate_records


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else settings.questions_path
    try:
        report = validate_records(read_raw_items(path))
    except DatasetError as exc:
        print("\n".join(exc.errors))
        return 1
    print(f"Dataset: {path}")
    print(f"Valid records: {len(report.records)}")
    by_subject = Counter(r.subject for r in report.records)
    for subject, count in sorted(by_subject.items()):
        diffs = Counter(r.difficulty for r in report.records if r.subject == subject)
        print(f"  {subject}: {count}  (easy {diffs['easy']}, medium {diffs['medium']}, hard {diffs['hard']})")
    for w in report.warnings:
        print(f"WARNING: {w}")
    if report.errors:
        print(f"\n{len(report.errors)} ERROR(S):")
        for e in report.errors:
            print(f"  - {e}")
        return 1
    print("\nOK: dataset is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
