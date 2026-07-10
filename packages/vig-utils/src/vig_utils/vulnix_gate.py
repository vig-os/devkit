#!/usr/bin/env python3
"""Gate HIGH/CRITICAL vulnix findings against an expiry-validated register.

`vulnix` scans the Nix image's package closure (the flake `devkitImageEnv`
target) and emits JSON findings. This gate fails (exit 1) when any HIGH/CRITICAL
CVE — CVSS v3 base score >= threshold (default 7.0) — is *not* covered by a
non-expired entry in the exception register (`.vulnixignore`, the same
`Expiration: YYYY-MM-DD` format as `.trivyignore`). An *unscored* CVE (no CVSS
v3 base score) is also gated — its unknown severity is failed loud rather than
silently skipped.

Register-entry expiry is enforced separately by `check-expirations` (pre-commit
+ CI); this gate additionally refuses to mask a finding with an already-expired
exception. Only sub-threshold *scored* CVEs are awareness-only and never gate.

This is the objective go/no-go input for the publish-cutover (#637 → #639).

Exit codes:
    0 — No unexcepted HIGH/CRITICAL findings
    1 — Missing/invalid input, or unexcepted HIGH/CRITICAL findings

Usage:
    vulnix-gate vulnix-findings.json
    vulnix-gate vulnix-findings.json --register .vulnixignore --threshold 7.0

Refs: #637
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from vig_utils.check_expirations import parse_entries

DEFAULT_REGISTER = ".vulnixignore"
DEFAULT_THRESHOLD = 7.0  # CVSS v3 HIGH starts at 7.0


def excepted_cves(register: Path, *, today: date | None = None) -> set[str]:
    """Return the CVE IDs that have a non-expired exception in *register*."""
    review_date = today or date.today()
    return {
        entry_id
        for entry_id, expiration in parse_entries(register)
        if review_date <= expiration
    }


def blocking_findings(
    items: list[dict],
    *,
    excepted: set[str],
    threshold: float = DEFAULT_THRESHOLD,
) -> list[dict]:
    """Return the unexcepted blocking findings in vulnix JSON *items*.

    Each returned dict is ``{pname, version, cve, score}`` (``score`` is ``None``
    for unscored CVEs). A CVE blocks when it is not in *excepted* and either its
    CVSS v3 base score is ``>= threshold`` or it is unscored: an unknown severity
    is failed loud rather than silently skipped. Only sub-threshold scored CVEs
    are awareness-only and never gate.
    """
    blocking: list[dict] = []
    for item in items:
        scores = item.get("cvssv3_basescore") or {}
        for cve in item.get("affected_by") or []:
            score = scores.get(cve)
            if score is not None and score < threshold:
                continue  # sub-threshold scored: awareness only
            if cve in excepted:
                continue
            blocking.append(
                {
                    "pname": item.get("pname", "?"),
                    "version": item.get("version", "?"),
                    "cve": cve,
                    "score": score,
                }
            )
    return blocking


def main(today: date | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gate HIGH/CRITICAL vulnix findings against the exception register."
    )
    parser.add_argument(
        "findings",
        type=Path,
        help="vulnix --json output file to gate",
    )
    parser.add_argument(
        "-r",
        "--register",
        type=Path,
        default=Path(DEFAULT_REGISTER),
        help=f"Exception register ({DEFAULT_REGISTER} format). Default: {DEFAULT_REGISTER}",
    )
    parser.add_argument(
        "-t",
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Minimum CVSS v3 base score to gate on. Default: {DEFAULT_THRESHOLD}",
    )
    args = parser.parse_args()

    if not args.findings.is_file():
        print(f"::error::{args.findings} not found", file=sys.stderr)
        return 1

    try:
        items = json.loads(args.findings.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        print(f"::error::failed to read {args.findings}: {exc}", file=sys.stderr)
        return 1

    try:
        excepted = (
            excepted_cves(args.register, today=today)
            if args.register.is_file()
            else set()
        )
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1

    blocking = blocking_findings(items, excepted=excepted, threshold=args.threshold)

    if blocking:
        print(
            f"::error::{len(blocking)} unexcepted HIGH/CRITICAL or unscored vulnix "
            f"finding(s) (CVSS >= {args.threshold} or no score):",
            file=sys.stderr,
        )
        # Unscored findings (score None) sort first: unknown severity is most urgent.
        for finding in sorted(
            blocking,
            key=lambda f: (
                -(f["score"] if f["score"] is not None else float("inf")),
                f["cve"],
            ),
        ):
            score = finding["score"]
            severity = f"CVSS {score}" if score is not None else "unscored"
            print(
                f"::error::  - {finding['cve']} ({severity}) "
                f"in {finding['pname']} {finding['version']}",
                file=sys.stderr,
            )
        return 1

    print(
        f"No unexcepted HIGH/CRITICAL findings (CVSS >= {args.threshold}); "
        f"{len(excepted)} exception(s) applied"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
