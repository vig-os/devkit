#!/usr/bin/env python3
"""
CHANGELOG.md management tool.

Provides commands for managing CHANGELOG.md during the release workflow.
"""

import argparse
import os
import re
import sys
from pathlib import Path

# Standard CHANGELOG subsections in order
STANDARD_SECTIONS = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]


def _parse_subsections(body_text):
    """
    Extract standard subsections that carry bullet content from a section body.

    Returns dict: {section_name: content_lines}
    """
    sections = {}
    for section in STANDARD_SECTIONS:
        # Anchor heading markers to line starts so inline ## in content
        # (e.g. backtick-quoted `##`) is not treated as a heading boundary.
        pattern = rf"^### {section}\s*\n(.*?)(?=^### |^## |\Z)"
        match = re.search(pattern, body_text, re.MULTILINE | re.DOTALL)
        if match:
            section_content = match.group(1).strip()
            # Only keep if it has actual bullet points (lines starting with -)
            if section_content:
                lines_with_content = [
                    line
                    for line in section_content.split("\n")
                    if line.strip() and line.strip().startswith("-")
                ]
                if lines_with_content:
                    sections[section] = section_content
    return sections


def _merge_sections(primary, secondary):
    """
    Merge two {section: content} dicts, keeping bullets from ``primary`` first.

    Exact-duplicate bullet lines are dropped so re-preparing a version does not
    repeat content already folded into its section (#612).
    """
    merged = {}
    for section in STANDARD_SECTIONS:
        parts = []
        seen = set()
        for src in (primary, secondary):
            if section in src:
                for line in src[section].split("\n"):
                    key = line.strip()
                    if key and key not in seen:
                        seen.add(key)
                        parts.append(line)
        if parts:
            merged[section] = "\n".join(parts)
    return merged


def _pop_version_section(content, version):
    """
    Remove an existing ``## [version]`` section from ``content``.

    Matches the heading whether it is ``- TBD`` or already dated/linked. Returns
    ``(new_content, sections)`` where ``sections`` holds the removed section's
    bullet content (empty dict and unchanged content when no such heading exists).
    """
    heading = re.search(
        rf"^## \[{re.escape(version)}\](?:\([^)]*\))? - .+$",
        content,
        re.MULTILINE,
    )
    if not heading:
        return content, {}

    next_heading = re.search(r"^## ", content[heading.end() :], re.MULTILINE)
    block_end = heading.end() + next_heading.start() if next_heading else len(content)
    block_body = content[heading.end() : block_end]
    sections = _parse_subsections(block_body)
    new_content = content[: heading.start()] + content[block_end:]
    return new_content, sections


def extract_unreleased_content(content):
    """
    Extract content from Unreleased section.

    Returns dict: {section_name: content_lines}
    """
    # Find Unreleased section
    unreleased_match = re.search(
        r"## Unreleased\s*\n(.*?)(?=\n## \[|\Z)", content, re.DOTALL
    )

    if not unreleased_match:
        raise ValueError("No '## Unreleased' section found in CHANGELOG")

    return _parse_subsections(unreleased_match.group(1))


def create_new_changelog(version, old_sections, rest_of_changelog):
    """
    Create new CHANGELOG structure.

    Args:
        version: Version string (e.g., "1.0.0")
        old_sections: Dict of sections with content from old Unreleased
        rest_of_changelog: Everything after the old Unreleased section
    """
    lines = []

    # Header (keep existing if present, or add minimal)
    lines.append("# Changelog\n")
    lines.append("\n")
    lines.append(
        "All notable changes to this project will be documented in this file.\n"
    )
    lines.append("\n")
    lines.append(
        "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),\n"
    )
    lines.append(
        "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n"
    )
    lines.append("\n")

    # New empty Unreleased section (always include all standard sections for consistency)
    lines.append("## Unreleased\n")
    lines.append("\n")
    for section in STANDARD_SECTIONS:
        lines.append(f"### {section}\n")
        lines.append("\n")

    # Version section with TBD date
    lines.append(f"## [{version}] - TBD\n")
    lines.append("\n")

    # Add sections that have content
    if old_sections:
        for section in STANDARD_SECTIONS:
            if section in old_sections:
                lines.append(f"### {section}\n")
                lines.append("\n")
                lines.append(old_sections[section])
                lines.append("\n")
                lines.append("\n")

    # Add rest of changelog
    lines.append(rest_of_changelog)

    return "".join(lines)


def validate_changelog(filepath="CHANGELOG.md"):
    """
    Validate that CHANGELOG has Unreleased section with content.

    Returns: (has_section, has_content)
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CHANGELOG not found: {filepath}")

    content = path.read_text()

    # Check for Unreleased section
    has_section = bool(re.search(r"## Unreleased", content))

    # Check for content in Unreleased section
    has_content = False
    if has_section:
        unreleased_match = re.search(
            r"## Unreleased\s*\n(.*?)(?=\n## \[|\Z)", content, re.DOTALL
        )
        if unreleased_match:
            unreleased_text = unreleased_match.group(1)
            # Check if any line starts with '-' (bullet point)
            has_content = bool(re.search(r"^\s*-", unreleased_text, re.MULTILINE))

    return has_section, has_content


def reset_unreleased(filepath="CHANGELOG.md"):
    """
    Create fresh Unreleased section after merging a release back to dev.

    This should only be called when there is NO Unreleased section (i.e., after
    the release has been merged to main and back to dev, removing the Unreleased section).

    Raises an error if Unreleased section already exists.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CHANGELOG not found: {filepath}")

    content = path.read_text()

    # Error if Unreleased already exists - this indicates wrong timing
    if re.search(r"## Unreleased", content):
        raise ValueError(
            "Unreleased section already exists in CHANGELOG.\n"
            "The reset action should only be used after merging a release to dev,\n"
            "when the Unreleased section has been removed."
        )

    # Insert fresh Unreleased at the top (after header)
    # Find end of header (after the last line before first ## heading)
    header_match = re.search(r"(.*?\n\n)(?=## \[)", content, re.DOTALL)
    if header_match:
        header = header_match.group(1)
        rest = content[header_match.end() :]

        # Build fresh Unreleased section
        unreleased = "## Unreleased\n\n"
        for section in STANDARD_SECTIONS:
            unreleased += f"### {section}\n\n"

        new_content = header + unreleased + rest
        path.write_text(new_content)
    else:
        raise ValueError("Could not find appropriate location for Unreleased section")


def unprepare_changelog(filepath="CHANGELOG.md"):
    """
    Rename the first top-level version section to ## Unreleased (inverse of prepare).

    Used when the workspace CHANGELOG was replaced by a scaffold but the canonical
    entries live under ``## [X.Y.Z] - …`` (e.g. copied from ``.devcontainer/CHANGELOG.md``).

    - If the first ``## `` heading is already ``## Unreleased``, no-op.
    - If it matches ``## [MAJOR.MINOR.PATCH] - …`` (semver + suffix), replace with
      ``## Unreleased``.
    - Otherwise raises ValueError.

    Args:
        filepath: Path to CHANGELOG.md

    Returns:
        True if the file was modified, False if already ``## Unreleased``.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CHANGELOG not found: {filepath}")

    content = path.read_text()
    match = re.search(r"^## .+$", content, re.MULTILINE)
    if not match:
        raise ValueError("No top-level ## heading found in CHANGELOG")

    line = match.group(0).rstrip("\r\n")
    if line == "## Unreleased":
        return False

    # Match ## [X.Y.Z] - … or ## [X.Y.Z](url) - … (optional release link, same semver rule as prepare)
    version_heading = re.compile(
        r"^## \[(\d+\.\d+\.\d+)\](?:\([^)]+\))? - .+$",
    )
    if not version_heading.match(line):
        raise ValueError(
            f"Unexpected first CHANGELOG section heading: {line!r} "
            "(expected ## Unreleased or ## [semver] - …)"
        )

    new_content = content[: match.start()] + "## Unreleased" + content[match.end() :]
    path.write_text(new_content)
    return True


def prepare_changelog(version, filepath="CHANGELOG.md"):
    """
    Prepare CHANGELOG for release.

    Args:
        version: Semantic version (e.g., "1.0.0")
        filepath: Path to CHANGELOG.md
    """
    # Validate version format
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        raise ValueError(f"Invalid semantic version: {version}")

    # Read current CHANGELOG
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CHANGELOG not found: {filepath}")

    content = path.read_text()

    # Extract Unreleased content
    old_sections = extract_unreleased_content(content)

    # Dedupe (#612): if a section for this version already exists (TBD or dated,
    # e.g. on a reused release branch), fold its bullets back in and drop it so we
    # produce exactly one ## [version] - TBD heading instead of stacking a second.
    content, existing_sections = _pop_version_section(content, version)
    if existing_sections:
        old_sections = _merge_sections(old_sections, existing_sections)

    # Get everything after Unreleased section
    rest_match = re.search(r"## Unreleased\s*\n.*?(?=\n## \[)", content, re.DOTALL)

    if rest_match:
        # Find start of next version section
        next_version_start = content.find("\n## [", rest_match.end())
        if next_version_start != -1:
            rest_of_changelog = content[next_version_start + 1 :]
        else:
            rest_of_changelog = ""
    else:
        rest_of_changelog = ""

    # Create new CHANGELOG
    new_content = create_new_changelog(version, old_sections, rest_of_changelog)

    # Write back
    path.write_text(new_content)

    return old_sections


def cmd_prepare(args):
    """Handle prepare command."""
    sections = prepare_changelog(args.version, args.file)

    print(f"✓ Prepared CHANGELOG for version {args.version}")
    if sections:
        print(
            f"✓ Moved {len(sections)} section(s) with content to [{args.version}] - TBD"
        )
        for section in sections:
            print(f"  - {section}")
    else:
        print("⚠ Warning: No content found in Unreleased section")
    print("✓ Created fresh Unreleased section")


def cmd_validate(args):
    """Handle validate command."""
    has_section, has_content = validate_changelog(args.file)

    if not has_section:
        print("Error: No Unreleased section found in CHANGELOG", file=sys.stderr)
        sys.exit(1)

    if not has_content:
        print(
            "Error: Unreleased section is empty (no changes to release)",
            file=sys.stderr,
        )
        sys.exit(1)

    print("✓ CHANGELOG validation passed")
    print("✓ Unreleased section exists with content")


def cmd_reset(args):
    """Handle reset command."""
    reset_unreleased(args.file)

    print(f"✓ Reset Unreleased section in {args.file}")
    print("✓ Created fresh empty section for next release")


def cmd_unprepare(args):
    """Handle unprepare command."""
    if unprepare_changelog(args.file):
        print(f"✓ Renamed top version section to ## Unreleased in {args.file}")
    else:
        print(f"✓ Top section already ## Unreleased in {args.file} (no changes)")


def _validate_github_repository_slug(raw: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", raw):
        raise ValueError(
            f"Invalid github_repository {raw!r} "
            "(owner and repo must contain only letters, numbers, '_', '.', or '-')"
        )
    return raw


def _resolve_github_repository(github_repository: str | None) -> str:
    """Return owner/repo for release links from an explicit value or GITHUB_REPOSITORY."""
    if github_repository is not None:
        stripped = github_repository.strip()
        if stripped:
            return _validate_github_repository_slug(stripped)
    env = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if env:
        return _validate_github_repository_slug(env)
    raise ValueError(
        "GitHub repository is required to finalize the changelog heading "
        "(set GITHUB_REPOSITORY or pass github_repository='owner/repo', "
        "or use prepare-changelog finalize --github-repository owner/repo)"
    )


def finalize_release_date(
    version,
    release_date,
    filepath="CHANGELOG.md",
    *,
    github_repository: str | None = None,
    tag_prefix: str = "",
):
    """
    Replace TBD date with actual release date for a version.

    The version heading becomes a linked title pointing at the GitHub release tag
    for this repository (``owner/repo`` from ``github_repository`` or the
    ``GITHUB_REPOSITORY`` environment variable).

    ``tag_prefix`` composes the published tag name onto the ``version`` for the
    displayed heading and the release link (e.g. ``v`` → ``## [v0.3.0](…/tag/v0.3.0)``),
    matching ``DEVKIT_TAG_PREFIX`` in the release pipeline (#1044). The ``## [X.Y.Z]
    - TBD`` placeholder matched in the file stays bare; only the emitted tag name
    and URL carry the prefix. An empty prefix reproduces today's output byte-for-byte.

    Args:
        version: Semantic version (e.g., "1.0.0")
        release_date: Release date in ISO format (YYYY-MM-DD)
        filepath: Path to CHANGELOG.md
        github_repository: ``owner/repo`` slug; when omitted, ``GITHUB_REPOSITORY`` is used
        tag_prefix: Optional tag-name prefix (default empty = bare ``X.Y.Z`` tags)

    Raises:
        ValueError: If version format is invalid, date format is invalid,
                   repository slug is missing or invalid, or version section with TBD not found
        FileNotFoundError: If CHANGELOG file doesn't exist
    """
    # Validate version format
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        raise ValueError(f"Invalid semantic version: {version}")

    # Validate date format
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", release_date):
        raise ValueError(f"Invalid date format: {release_date} (expected YYYY-MM-DD)")

    # Read CHANGELOG
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CHANGELOG not found: {filepath}")

    content = path.read_text()

    # Published tag name = prefix + bare version (empty prefix ⇒ bare tag).
    tag = f"{tag_prefix}{version}"

    # Idempotency (#612): a reused release branch can re-run finalize against a
    # heading this tool already dated. Detect the linked-and-dated form finalize
    # itself writes (## [<tag>](…) - YYYY-MM-DD) and treat a re-run as a no-op so
    # candidate→final on one base version stays idempotent. A plain dated heading
    # with no release link (a historical entry) is still rejected below.
    finalized_pattern = rf"## \[{re.escape(tag)}\]\([^)]*\) - \d{{4}}-\d{{2}}-\d{{2}}"
    if re.search(finalized_pattern, content):
        return

    # Check if version with TBD exists (the placeholder heading stays bare).
    version_pattern = rf"## \[{re.escape(version)}\] - TBD"
    if not re.search(version_pattern, content):
        raise ValueError(
            f"Version section '## [{version}] - TBD' not found in CHANGELOG"
        )

    repo_slug = _resolve_github_repository(github_repository)
    tag_url = f"https://github.com/{repo_slug}/releases/tag/{tag}"
    replacement = f"## [{tag}]({tag_url}) - {release_date}"
    new_content = re.sub(version_pattern, replacement, content)

    # Write back
    path.write_text(new_content)


def reset_version_to_tbd(version, filepath="CHANGELOG.md"):
    """
    Revert a dated ``## [version]`` heading back to ``## [version] - TBD``.

    Normalizes any finalized heading for ``version`` — linked
    (``## [X.Y.Z](…) - YYYY-MM-DD``) or plain (``## [X.Y.Z] - YYYY-MM-DD``) — to
    the ``- TBD`` placeholder, dropping the release link. Idempotent: a no-op when
    the heading is already TBD or absent (#612, called at dispatch start so a base
    version released as a candidate can be re-released as final).

    Args:
        version: Semantic version (e.g., "1.0.0")
        filepath: Path to CHANGELOG.md

    Returns:
        True if the file was modified, False otherwise.

    Raises:
        ValueError: If the version format is invalid
        FileNotFoundError: If the CHANGELOG file doesn't exist
    """
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        raise ValueError(f"Invalid semantic version: {version}")

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CHANGELOG not found: {filepath}")

    content = path.read_text()
    # Match the version heading with any non-TBD suffix (optional release link)
    # so we never rewrite an already-TBD heading (keeps the call idempotent).
    pattern = rf"^## \[{re.escape(version)}\](?:\([^)]*\))? - (?!TBD$).+$"
    new_content = re.sub(pattern, f"## [{version}] - TBD", content, flags=re.MULTILINE)
    if new_content == content:
        return False

    path.write_text(new_content)
    return True


def cmd_reset_version(args):
    """Handle reset-version command."""
    if reset_version_to_tbd(args.version, args.file):
        print(f"✓ Reset version {args.version} heading to TBD in {args.file}")
    else:
        print(
            f"✓ Version {args.version} already TBD or absent in {args.file} (no changes)"
        )


def cmd_finalize(args):
    """Handle finalize command."""
    finalize_release_date(
        args.version,
        args.date,
        args.file,
        github_repository=args.github_repository,
        tag_prefix=args.tag_prefix,
    )

    print(f"✓ Set release date for version {args.version}")
    print(f"✓ Date: {args.date}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="CHANGELOG.md management tool for release workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Prepare CHANGELOG for release 1.0.0
  %(prog)s prepare 1.0.0

  # Validate CHANGELOG has unreleased changes
  %(prog)s validate

  # Set release date for version 1.0.0 (uses GITHUB_REPOSITORY if set)
  %(prog)s finalize 1.0.0 2026-02-11
  %(prog)s finalize 1.0.0 2026-02-11 CHANGELOG.md --github-repository my-org/my-repo

  # Reset Unreleased section after release merge
  %(prog)s reset

  # Revert a dated version heading back to TBD (idempotent candidate→final)
  %(prog)s reset-version 1.0.0

  # Rename top ## [version] - … to ## Unreleased (smoke-test deploy sync)
  %(prog)s unprepare
        """,
    )

    subparsers = parser.add_subparsers(
        title="commands",
        description="Available commands",
        dest="command",
        required=True,
    )

    # prepare command
    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Prepare CHANGELOG for release (move Unreleased to version section)",
    )
    prepare_parser.add_argument(
        "version",
        help="Semantic version (e.g., 1.0.0)",
    )
    prepare_parser.add_argument(
        "file",
        nargs="?",
        default="CHANGELOG.md",
        help="Path to CHANGELOG file (default: CHANGELOG.md)",
    )
    prepare_parser.set_defaults(func=cmd_prepare)

    # validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate CHANGELOG has Unreleased section with content",
    )
    validate_parser.add_argument(
        "file",
        nargs="?",
        default="CHANGELOG.md",
        help="Path to CHANGELOG file (default: CHANGELOG.md)",
    )
    validate_parser.set_defaults(func=cmd_validate)

    # reset command
    reset_parser = subparsers.add_parser(
        "reset",
        help="Create fresh Unreleased section (for after release merge to dev)",
    )
    reset_parser.add_argument(
        "file",
        nargs="?",
        default="CHANGELOG.md",
        help="Path to CHANGELOG file (default: CHANGELOG.md)",
    )
    reset_parser.set_defaults(func=cmd_reset)

    # reset-version command
    reset_version_parser = subparsers.add_parser(
        "reset-version",
        help="Revert a dated ## [version] heading back to ## [version] - TBD",
    )
    reset_version_parser.add_argument(
        "version",
        help="Semantic version (e.g., 1.0.0)",
    )
    reset_version_parser.add_argument(
        "file",
        nargs="?",
        default="CHANGELOG.md",
        help="Path to CHANGELOG file (default: CHANGELOG.md)",
    )
    reset_version_parser.set_defaults(func=cmd_reset_version)

    # unprepare command
    unprepare_parser = subparsers.add_parser(
        "unprepare",
        help="Rename first ## [semver] - … heading to ## Unreleased",
    )
    unprepare_parser.add_argument(
        "file",
        nargs="?",
        default="CHANGELOG.md",
        help="Path to CHANGELOG file (default: CHANGELOG.md)",
    )
    unprepare_parser.set_defaults(func=cmd_unprepare)

    # finalize command
    finalize_parser = subparsers.add_parser(
        "finalize",
        help="Set release date (replace TBD with actual date)",
    )
    finalize_parser.add_argument(
        "version",
        help="Semantic version (e.g., 1.0.0)",
    )
    finalize_parser.add_argument(
        "date",
        help="Release date in ISO format (YYYY-MM-DD)",
    )
    finalize_parser.add_argument(
        "file",
        nargs="?",
        default="CHANGELOG.md",
        help="Path to CHANGELOG file (default: CHANGELOG.md)",
    )
    finalize_parser.add_argument(
        "--github-repository",
        dest="github_repository",
        default=None,
        metavar="OWNER/REPO",
        help=(
            "Repository slug for the release tag link "
            "(default: GITHUB_REPOSITORY environment variable)"
        ),
    )
    finalize_parser.add_argument(
        "--tag-prefix",
        dest="tag_prefix",
        default="",
        metavar="PREFIX",
        help=(
            "Tag-name prefix composed onto the release heading and link "
            "(e.g. 'v'; default empty = bare X.Y.Z tags)"
        ),
    )
    finalize_parser.set_defaults(func=cmd_finalize)

    # Parse and execute
    args = parser.parse_args()

    try:
        args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
