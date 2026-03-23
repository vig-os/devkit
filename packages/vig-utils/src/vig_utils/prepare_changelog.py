#!/usr/bin/env python3
"""
CHANGELOG.md management tool.

Provides commands for managing CHANGELOG.md during the release workflow.
"""

import argparse
import re
import sys
from pathlib import Path

# Standard CHANGELOG subsections in order
STANDARD_SECTIONS = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]


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

    unreleased_text = unreleased_match.group(1)

    # Extract each subsection
    sections = {}
    for section in STANDARD_SECTIONS:
        # Anchor heading markers to line starts so inline ## in content
        # (e.g. backtick-quoted `##`) is not treated as a heading boundary.
        pattern = rf"^### {section}\s*\n(.*?)(?=^### |^## |\Z)"
        match = re.search(pattern, unreleased_text, re.MULTILINE | re.DOTALL)
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
    """Rename top version section to ## Unreleased (implemented in next commit)."""
    raise NotImplementedError


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


def finalize_release_date(version, release_date, filepath="CHANGELOG.md"):
    """
    Replace TBD date with actual release date for a version.

    Args:
        version: Semantic version (e.g., "1.0.0")
        release_date: Release date in ISO format (YYYY-MM-DD)
        filepath: Path to CHANGELOG.md

    Raises:
        ValueError: If version format is invalid, date format is invalid,
                   or version section with TBD not found
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

    # Check if version with TBD exists
    version_pattern = rf"## \[{re.escape(version)}\] - TBD"
    if not re.search(version_pattern, content):
        raise ValueError(
            f"Version section '## [{version}] - TBD' not found in CHANGELOG"
        )

    # Replace TBD with release date
    replacement = f"## [{version}] - {release_date}"
    new_content = re.sub(version_pattern, replacement, content)

    # Write back
    path.write_text(new_content)


def cmd_finalize(args):
    """Handle finalize command."""
    finalize_release_date(args.version, args.date, args.file)

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

  # Set release date for version 1.0.0
  %(prog)s finalize 1.0.0 2026-02-11

  # Reset Unreleased section after release merge
  %(prog)s reset

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
