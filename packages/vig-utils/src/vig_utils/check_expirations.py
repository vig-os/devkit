#!/usr/bin/env python3
"""Validate expiration dates in security exception files.

Parses `.trivyignore` and `.github/dependency-review-allow.txt` style files
where each exception entry is preceded by an `Expiration: YYYY-MM-DD`
directive. One expiration line may apply to multiple following entries until
the next expiration directive.

Exit codes:
    0 — All entries are present and unexpired
    1 — Missing file, parse error, or expired entries

Usage:
    check-expirations .trivyignore
    check-expirations .github/dependency-review-allow.txt

Refs: #566
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

EXPIRATION_PATTERN = re.compile(r"^Expiration:\s*(\d{4}-\d{2}-\d{2})\s*$")


def parse_entries(path: Path) -> list[tuple[str, date]]:
    """Parse exception entries and their expiration dates from *path*."""
    entries: list[tuple[str, date]] = []
    current_expiration: date | None = None

    with path.open(encoding="utf-8") as handle:
        for line_num, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            expiration_match = EXPIRATION_PATTERN.match(line)
            if expiration_match:
                try:
                    current_expiration = datetime.strptime(
                        expiration_match.group(1), "%Y-%m-%d"
                    ).date()
                except ValueError as exc:
                    msg = (
                        f"{path}:{line_num}: invalid expiration date "
                        f"{expiration_match.group(1)!r}"
                    )
                    raise ValueError(msg) from exc
                continue

            if current_expiration is None:
                msg = f"{path}:{line_num}: {line} has no Expiration directive"
                raise ValueError(msg)

            entry_id = line.split()[0]
            entries.append((entry_id, current_expiration))

    return entries


def check_file(path: Path, *, today: date | None = None) -> list[str]:
    """Return error messages for expired entries in *path*."""
    review_date = today or date.today()
    entries = parse_entries(path)
    errors: list[str] = []

    for entry_id, expiration in entries:
        if review_date > expiration:
            errors.append(f"{entry_id} (expired {expiration.isoformat()})")

    return errors


def main(today: date | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate expiration dates in security exception files."
    )
    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="Exception files to validate (e.g. .trivyignore)",
    )
    args = parser.parse_args()

    all_errors: list[str] = []
    total_entries = 0

    for path in args.files:
        if not path.is_file():
            print(f"::error::{path} not found", file=sys.stderr)
            return 1

        try:
            entries = parse_entries(path)
        except ValueError as exc:
            print(f"::error::{exc}", file=sys.stderr)
            return 1

        total_entries += len(entries)
        errors = check_file(path, today=today)
        for error in errors:
            all_errors.append(f"{path}: {error}")

    if all_errors:
        print(
            "::error::Expired security exceptions — review and renew or remove:",
            file=sys.stderr,
        )
        for error in all_errors:
            print(f"::error::  - {error}", file=sys.stderr)
        return 1

    print(f"Validated {total_entries} exception(s) across {len(args.files)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
