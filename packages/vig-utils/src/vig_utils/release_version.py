#!/usr/bin/env python3
"""Compute the release train's publish version from a pre-release format (#1746).

The train used to hard-code candidates as ``X.Y.Z-rc{N}``. A repo now selects a
pre-release *format* (``release.yml`` input ``pre-release-format`` >
``.vig-os`` ``DEVKIT_PRERELEASE_FORMAT`` > ``rc{N}``) built from literal SemVer
characters plus two placeholders:

- ``{N}``        — optional counter, auto-incremented from existing tags of the
                   same format (pinnable with ``--number``); at most once
- ``{YYYYMMDD}`` — UTC date stamp; at most once. A counter in a dated format
                   restarts every day.

Existing tags are read from stdin, one per line (the ``git ls-remote`` output of
``<prefix>X.Y.Z`` / ``<prefix>X.Y.Z-*``). Results are printed as
``$GITHUB_OUTPUT`` lines::

    publish_version=1.2.3-alpha.2
    next_n=2

Monotonicity gate: tags of the *current* format rank by their counter (``rc9``
before ``rc10`` — SemVer would rank them lexically the other way round), but a
pre-release tag of any *other* format must not sort above the new version under
SemVer precedence. That refuses a label switch such as ``rc{N}`` ->
``alpha.{N}`` after ``X.Y.Z-rc21`` shipped. An existing final ``X.Y.Z`` tag only
warns: after a failed final run the tag stays (forward-fix policy) and a new
candidate of the same version is the documented recovery.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

DEFAULT_FORMAT = "rc{N}"
COUNTER = "{N}"
DATE = "{YYYYMMDD}"
KINDS = ("candidate", "final")

_PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")
_LITERAL_RE = re.compile(r"^[0-9A-Za-z.-]*$")
_VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$", re.ASCII)
_IDENT = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
_PRERELEASE_RE = re.compile(rf"^{_IDENT}(?:\.{_IDENT})*$", re.ASCII)
_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-("
    + _PRERELEASE_RE.pattern[1:-1]
    + r"))?$",
    re.ASCII,
)
# {N} directly after/before a digit or the date placeholder yields one run of
# digits (`{YYYYMMDD}{N}` -> 202601011 < 2026010110 for a later day), so the
# counter can neither be parsed back nor ordered.
_AMBIGUOUS_COUNTER_RE = re.compile(
    r"(?:[0-9]|\{YYYYMMDD\})\{N\}|\{N\}(?:[0-9]|\{YYYYMMDD\})"
)
_POSITIVE_INT_RE = re.compile(r"^[1-9]\d*$", re.ASCII)
_DATE_RE = re.compile(r"^\d{8}$", re.ASCII)


class ReleaseVersionError(ValueError):
    """The requested publish version is invalid or would break ordering."""


@dataclass(frozen=True)
class PublishVersion:
    publish_version: str
    next_n: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreReleaseFormat:
    """A validated pre-release format string."""

    raw: str

    @classmethod
    def parse(cls, raw: str) -> PreReleaseFormat:
        fmt = raw.strip()
        for token in _PLACEHOLDER_RE.findall(fmt):
            if token not in (COUNTER, DATE):
                raise ReleaseVersionError(
                    f"Invalid pre-release format '{fmt}': unknown placeholder "
                    f"{token} (supported: {COUNTER}, {DATE})"
                )
        for token in (COUNTER, DATE):
            if fmt.count(token) > 1:
                raise ReleaseVersionError(
                    f"Invalid pre-release format '{fmt}': {token} may appear at most once"
                )
        literal = fmt.replace(COUNTER, "").replace(DATE, "")
        if not _LITERAL_RE.match(literal):
            raise ReleaseVersionError(
                f"Invalid pre-release format '{fmt}': literal text may only use "
                "[0-9A-Za-z.-] (SemVer pre-release characters)"
            )
        if _AMBIGUOUS_COUNTER_RE.search(fmt):
            raise ReleaseVersionError(
                f"Invalid pre-release format '{fmt}': {COUNTER} must not touch a digit "
                f"or {DATE} (e.g. `rc1{COUNTER}` or `{DATE}{COUNTER}` run the counter "
                "into another number, so versions stop sorting); separate them with "
                "a letter, `-` or `.`"
            )
        parsed = cls(fmt)
        sample = parsed.expand(1, "20260101")
        if not _PRERELEASE_RE.match(sample):
            raise ReleaseVersionError(
                f"Invalid pre-release format '{fmt}': expands to '{sample}', which is "
                "not a valid SemVer pre-release (dot-separated, non-empty "
                "identifiers; numeric identifiers without leading zeros)"
            )
        return parsed

    @property
    def has_counter(self) -> bool:
        return COUNTER in self.raw

    def expand(self, n: int | None, date: str) -> str:
        return self.raw.replace(COUNTER, "" if n is None else str(n)).replace(
            DATE, date
        )

    def _pattern_body(self, counter_group: str, date_pattern: str) -> str:
        """The format's body as a regex fragment (no anchors, no prefix/version).

        Shared by ``_regex`` (internal matching, needs the counter back via a
        named group) and ``list_pattern`` (handed to external tools, which
        must get a plain group instead -- see ``list_pattern``).
        """
        pattern = re.escape(self.raw)
        pattern = pattern.replace(re.escape(COUNTER), counter_group)
        pattern = pattern.replace(re.escape(DATE), date_pattern)
        return pattern

    def _regex(self, date_pattern: str) -> re.Pattern[str]:
        body = self._pattern_body(r"(?P<n>0|[1-9]\d*)", date_pattern)
        return re.compile(rf"^{body}$", re.ASCII)

    def list_pattern(self, tag_prefix: str, version: str) -> str:
        """Anchored regex (as a string) matching this format's tags of ``version``.

        Built on the same ``re.escape``/placeholder-substitution machinery as
        ``_regex`` -- no second parser -- but restricted to plain POSIX ERE:
        the pattern is meant for external consumers (jq's ``test()``, a
        ``grep -E`` filter), and only one of those speaks PCRE. A plain
        ``(...)`` group replaces ``_regex``'s named ``(?P<n>...)`` (GNU
        ``grep -E`` warns on ``(?:...)`` and silently mis-parses it), and
        ``[0-9]`` replaces ``\\d`` (GNU ``grep -E`` does not expand it --
        verified directly against both tools, not assumed). ``{YYYYMMDD}``
        matches any 8-digit date. Used by the promote-release cleanup job
        (#1749) to find candidate tags of the CONFIGURED format only -- a tag
        from a previously configured format is intentionally not matched.
        """
        base = re.escape(f"{tag_prefix}{version}") + "-"
        body = self._pattern_body(r"(0|[1-9][0-9]*)", r"[0-9]{8}")
        return rf"^{base}{body}$"

    def matches_any_date(self, pre: str) -> bool:
        """``pre`` is a well-formed instance of this format (any date)."""
        return bool(self._regex(r"\d{8}").match(pre))

    def counter_on(self, pre: str, date: str) -> int | None:
        """The counter of ``pre`` when it is this format on ``date``."""
        m = self._regex(re.escape(date)).match(pre)
        return int(m.group("n")) if m and self.has_counter else None

    def in_namespace(self, pre: str) -> bool:
        """``pre`` looks like it belongs to this format (placeholders as ``*``)."""
        glob = self.raw.replace(COUNTER, "*").replace(DATE, "*")
        return fnmatch.fnmatchcase(pre, glob)


def semver_key(version: str) -> tuple:
    """SemVer 2.0.0 precedence key for ``X.Y.Z[-pre]`` (build metadata unsupported)."""
    m = _SEMVER_RE.match(version)
    if not m:
        raise ReleaseVersionError(f"Not a SemVer version: '{version}'")
    major, minor, patch, pre = m.groups()
    if pre is None:
        pre_key: tuple = (1,)
    else:
        idents = tuple(
            (0, int(ident), "") if ident.isdigit() else (1, 0, ident)
            for ident in pre.split(".")
        )
        pre_key = (0, idents)
    return (int(major), int(minor), int(patch), pre_key)


def _validate_version(version: str) -> None:
    if not _VERSION_RE.match(version):
        raise ReleaseVersionError(
            f"Invalid version format '{version}': version must follow semantic "
            "versioning MAJOR.MINOR.PATCH (e.g., 1.2.3)"
        )


def _validate_inputs(version: str, kind: str) -> None:
    _validate_version(version)
    if kind not in KINDS:
        raise ReleaseVersionError(
            f"Invalid release kind '{kind}': kind must be one of: {', '.join(KINDS)}"
        )


def _prereleases_of(
    existing_tags: Iterable[str], base_tag: str
) -> list[tuple[str, str | None]]:
    """``(tag, pre-release or None)`` for every tag of exactly ``base_tag``."""
    found: list[tuple[str, str | None]] = []
    for tag in existing_tags:
        if tag == base_tag:
            found.append((tag, None))
        elif tag.startswith(f"{base_tag}-"):
            found.append((tag, tag[len(base_tag) + 1 :]))
    return found


def _resolve_counter(
    fmt: PreReleaseFormat,
    number: str | None,
    tags: list[tuple[str, str | None]],
    base_tag: str,
    date: str,
) -> int | None:
    if number:
        if not _POSITIVE_INT_RE.match(number):
            raise ReleaseVersionError(
                f"Pre-release number must be a positive integer (got '{number}')"
            )
        if not fmt.has_counter:
            raise ReleaseVersionError(
                f"A pre-release number was given, but format '{fmt.raw}' has no "
                f"{COUNTER} placeholder to pin"
            )
        return int(number)
    if not fmt.has_counter:
        return None
    highest = 0
    for tag, pre in tags:
        if pre is None or not fmt.in_namespace(pre):
            continue
        if not fmt.matches_any_date(pre):
            raise ReleaseVersionError(
                f"Malformed candidate tag detected: {tag}\n"
                f"Expected format: {base_tag}-{fmt.raw}"
            )
        n = fmt.counter_on(pre, date)
        if n is not None and n > highest:
            highest = n
    return highest + 1


def _check_monotonic(
    fmt: PreReleaseFormat,
    kind: str,
    publish_version: str,
    tags: list[tuple[str, str | None]],
    tag_prefix: str,
) -> tuple[str, ...]:
    """Refuse a lowering label switch; return warnings for non-blocking cases."""
    new_key = semver_key(publish_version)
    blockers = []
    warnings: list[str] = []
    for tag, pre in tags:
        if pre is None:
            if kind == "candidate":
                warnings.append(
                    f"Final tag {tag} already exists, so {tag_prefix}{publish_version} "
                    "sorts below a released version (fine when recovering from a "
                    "failed final run; a legacy tag will block the final release)."
                )
            continue
        if kind == "candidate" and fmt.matches_any_date(pre):
            continue  # same series: ordered by its counter, not lexically
        bare = tag[len(tag_prefix) :]
        if not _SEMVER_RE.match(bare):
            continue
        if semver_key(bare) > new_key:
            blockers.append((semver_key(bare), tag))
    if blockers:
        _, highest = max(blockers)
        raise ReleaseVersionError(
            f"Refusing to publish {tag_prefix}{publish_version}: existing tag "
            f"{highest} sorts above it, so format '{fmt.raw}' would publish a lower "
            "version for the same X.Y.Z. Keep the previous pre-release format for "
            "this version, or release the next X.Y.Z with the new one."
        )
    return tuple(warnings)


def compute_publish_version(
    *,
    version: str,
    kind: str,
    fmt: str,
    existing_tags: Iterable[str],
    tag_prefix: str = "",
    number: str | None = None,
    date: str | None = None,
) -> PublishVersion:
    """Resolve the bare publish version for a release run."""
    _validate_inputs(version, kind)
    parsed = PreReleaseFormat.parse(fmt)
    date = date or datetime.now(UTC).strftime("%Y%m%d")
    if not _DATE_RE.match(date):
        raise ReleaseVersionError(f"Invalid date '{date}': expected YYYYMMDD")

    base_tag = f"{tag_prefix}{version}"
    tags = _prereleases_of(existing_tags, base_tag)

    if kind == "final":
        publish, next_n = version, ""
    else:
        n = _resolve_counter(parsed, number, tags, base_tag, date)
        publish = f"{version}-{parsed.expand(n, date)}"
        next_n = "" if n is None else str(n)
        if not number and any(tag == f"{tag_prefix}{publish}" for tag, _ in tags):
            raise ReleaseVersionError(
                f"Candidate tag {tag_prefix}{publish} already exists: format "
                f"'{parsed.raw}' yields one candidate per version (per day for a "
                f"dated format). Add {COUNTER} to the format to cut further candidates."
            )

    warnings = _check_monotonic(parsed, kind, publish, tags, tag_prefix)
    return PublishVersion(publish_version=publish, next_n=next_n, warnings=warnings)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="release-version",
        description=(
            "Compute the release train's bare publish version. Existing tags are "
            "read from stdin, one per line; results print as $GITHUB_OUTPUT lines."
        ),
    )
    parser.add_argument("--version", required=True, help="Release version X.Y.Z")
    parser.add_argument(
        "--kind", default="", help="candidate | final (required unless --list-pattern)"
    )
    parser.add_argument(
        "--format",
        default="",
        help=f"Pre-release format ({COUNTER}, {DATE}); empty => {DEFAULT_FORMAT}",
    )
    parser.add_argument(
        "--number", default="", help=f"Pin the {COUNTER} counter (candidates only)"
    )
    parser.add_argument("--tag-prefix", default="", help="DEVKIT_TAG_PREFIX")
    parser.add_argument("--date", default="", help="UTC date YYYYMMDD (default: today)")
    parser.add_argument(
        "--list-pattern",
        action="store_true",
        help=(
            "Print the anchored regex matching --format's tags of --version "
            "(with --tag-prefix) and exit; reads no stdin, needs no --kind"
        ),
    )
    return parser


def _list_pattern(args: argparse.Namespace) -> int:
    try:
        _validate_version(args.version)
        fmt = PreReleaseFormat.parse(args.format.strip() or DEFAULT_FORMAT)
    except ReleaseVersionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(fmt.list_pattern(args.tag_prefix, args.version))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.list_pattern:
        return _list_pattern(args)

    if not args.kind:
        parser.error("--kind is required unless --list-pattern is given")

    tags = [line.strip() for line in sys.stdin if line.strip()]
    try:
        result = compute_publish_version(
            version=args.version,
            kind=args.kind,
            fmt=args.format.strip() or DEFAULT_FORMAT,
            existing_tags=tags,
            tag_prefix=args.tag_prefix,
            number=args.number or None,
            date=args.date or None,
        )
    except ReleaseVersionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    for warning in result.warnings:
        print(f"::warning::{warning}", file=sys.stderr)
    print(f"publish_version={result.publish_version}")
    print(f"next_n={result.next_n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
