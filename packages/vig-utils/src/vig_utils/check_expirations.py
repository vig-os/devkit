#!/usr/bin/env python3
"""Validate expiration dates in security exception files.

Parses `.trivyignore` and `.github/dependency-review-allow.txt` style files
where each exception entry is preceded by an `Expiration: YYYY-MM-DD`
directive. One expiration line may apply to multiple following entries until
the next expiration directive.

This module is the single parser of the `Expiration:` grammar. `--warn-days`
and `--json` exist so a workflow can give advance notice of an upcoming expiry
without re-implementing that grammar (#1552).

Exit codes:
    0 — All entries are present and unexpired
    1 — Missing file, parse error, or expired entries

Note that `--warn-days` never changes the exit code: an entry inside the
warning window is still valid, and an already-expired entry still fails. The
hard gate is unchanged; the warning is a notice ahead of it.

Usage:
    check-expirations .trivyignore
    check-expirations .github/dependency-review-allow.txt
    check-expirations --warn-days 7 .vulnixignore
    check-expirations --warn-days 7 --json .vulnixignore

Refs: #566, #1552
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

EXPIRATION_PATTERN = re.compile(r"^Expiration:\s*(\d{4}-\d{2}-\d{2})\s*$")

# One classified entry: {"id", "file", "expiration", "days_left"}. `days_left`
# is negative for an entry that has already expired.
Record = dict[str, object]


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


def classify_entries(
    entries: list[tuple[str, date]],
    *,
    path: Path,
    today: date,
    warn_days: int | None = None,
) -> tuple[list[Record], list[Record]]:
    """Split *entries* into (expired, expiring) records.

    An entry is expired when `today > expiration` — the rule the hard gate has
    always used. When *warn_days* is given, an unexpired entry falling due
    within that many days (inclusive) is reported as expiring; `warn_days=None`
    means no warning window, so the second list is always empty and the default
    CLI behaviour is unchanged.
    """
    expired: list[Record] = []
    expiring: list[Record] = []

    for entry_id, expiration in entries:
        days_left = (expiration - today).days
        record: Record = {
            "id": entry_id,
            "file": str(path),
            "expiration": expiration.isoformat(),
            "days_left": days_left,
        }
        if days_left < 0:
            expired.append(record)
        elif warn_days is not None and days_left <= warn_days:
            expiring.append(record)

    return expired, expiring


def check_file(path: Path, *, today: date | None = None) -> list[str]:
    """Return error messages for expired entries in *path*."""
    review_date = today or date.today()
    expired, _ = classify_entries(parse_entries(path), path=path, today=review_date)

    return [f"{record['id']} (expired {record['expiration']})" for record in expired]


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
    parser.add_argument(
        "--warn-days",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Emit a ::warning:: annotation for entries expiring within N days "
            "(inclusive). Never changes the exit code."
        ),
    )
    parser.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help=(
            "Print the classification as JSON on stdout instead of the human "
            "summary, so callers never re-parse the register format."
        ),
    )
    args = parser.parse_args()

    review_date = today or date.today()
    all_errors: list[str] = []
    all_expired: list[Record] = []
    all_expiring: list[Record] = []
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
        expired, expiring = classify_entries(
            entries, path=path, today=review_date, warn_days=args.warn_days
        )
        all_expired.extend(expired)
        all_expiring.extend(expiring)
        for record in expired:
            all_errors.append(
                f"{path}: {record['id']} (expired {record['expiration']})"
            )

    # Warnings first: an upcoming expiry is worth surfacing even on a run that
    # is about to fail on an already-expired entry.
    if all_expiring:
        print(
            f"::warning::Security exceptions expiring within {args.warn_days} "
            "day(s) — review before they fail CI:",
            file=sys.stderr,
        )
        for record in all_expiring:
            print(
                f"::warning::  - {record['file']}: {record['id']} "
                f"(expires {record['expiration']}, {record['days_left']} day(s) left)",
                file=sys.stderr,
            )

    if all_errors:
        print(
            "::error::Expired security exceptions — review and renew or remove:",
            file=sys.stderr,
        )
        for error in all_errors:
            print(f"::error::  - {error}", file=sys.stderr)
        # Still emit the payload: a caller that asked for JSON wants the
        # classification even (especially) on the failing run.
        if args.emit_json:
            print(json.dumps({"expired": all_expired, "expiring": all_expiring}))
        return 1

    if args.emit_json:
        print(json.dumps({"expired": all_expired, "expiring": all_expiring}))
    else:
        print(
            f"Validated {total_entries} exception(s) across {len(args.files)} file(s)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
