"""Guards for the .claude/ single-source-of-truth migration (Refs: #626).

After migrating agent rules and skills from .cursor/ to .claude/, no tracked
file outside the downstream workspace template (assets/workspace/, owned by
#629) may reference the old .cursor/skills/ path, and the root .cursor/
directory must no longer exist.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Append-only archival snapshots of past issues/PRs. They record the historical
# text of issues/PRs verbatim (which legitimately quoted .cursor/ paths at the
# time) and are never rewritten, like dated CHANGELOG entries.
_ARCHIVAL_PREFIXES = (
    "assets/workspace/",  # downstream template, migrated under #629
    "docs/issues/",
    "docs/pull-requests/",
    "docs/plans/",
)

# Released CHANGELOG entries are append-only history (never rewritten) and may
# reference paths that were current at the time of release. This guard module
# itself must contain the search literal to do its job.
_THIS_FILE_REL = "packages/vig-utils/tests/test_claude_ssot.py"
_ARCHIVAL_FILES = ("CHANGELOG.md", _THIS_FILE_REL)


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def test_no_tracked_file_references_cursor_skills() -> None:
    """No tracked file (outside the workspace template) references .cursor/skills/."""
    offenders: list[str] = []
    for rel in _tracked_files():
        if rel.startswith(_ARCHIVAL_PREFIXES) or rel in _ARCHIVAL_FILES:
            continue
        path = REPO_ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError, FileNotFoundError:
            continue
        if ".cursor/skills/" in text:
            offenders.append(rel)
    assert not offenders, f"Files still reference .cursor/skills/: {offenders}"


def test_no_tracked_file_reads_cursor_agent_config() -> None:
    """No tracked file (outside the workspace template) reads a removed .cursor/ config path.

    The .cursor/ → .claude/ migration moved agent-models.toml and the
    branch-naming rule, but callers that *read* those paths (e.g. the worktree
    recipes) must follow them to the .claude/ SSoT (Refs: #627).
    """
    offenders: list[str] = []
    for rel in _tracked_files():
        if rel.startswith(_ARCHIVAL_PREFIXES) or rel in _ARCHIVAL_FILES:
            continue
        path = REPO_ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError, FileNotFoundError:
            continue
        if ".cursor/agent-models.toml" in text or ".cursor/rules/" in text:
            offenders.append(rel)
    assert not offenders, f"Files still read removed .cursor/ config paths: {offenders}"


def test_root_cursor_dir_deleted() -> None:
    """The root .cursor/ directory is removed; .claude/ is the SSoT."""
    assert not (REPO_ROOT / ".cursor").exists(), "root .cursor/ should be deleted"
