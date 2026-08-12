"""Workflow-shape tests: DEVKIT_TAG_PREFIX threading in the scaffold release set.

Issue #1044: an Action-publishing consumer declares ``DEVKIT_TAG_PREFIX`` in
``.vig-os``; ``resolve-toolchain`` reads it and emits a ``tag-prefix`` output,
which ``release.yml`` threads into the reusable ``release-core.yml`` /
``release-publish.yml`` children as a ``tag_prefix`` ``workflow_call`` input.

These assertions pin the wiring (the composition itself lives in bash ``run:``
blocks, covered by prepare_changelog unit tests and not shape-testable here).

Refs: #1044
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import WORKFLOWS
from tests.workflow_scaffold import load_workflow as _load

if TYPE_CHECKING:
    from pathlib import Path


def test_release_orchestrator_threads_tag_prefix() -> None:
    """release.yml passes tag_prefix into the tag-emitting children."""
    workflow = _load(WORKFLOWS / "release.yml")
    resolve_out = workflow["jobs"]["resolve-toolchain"]["outputs"]
    assert "tag-prefix" in resolve_out
    for job in ("core", "publish"):
        assert "tag_prefix" in workflow["jobs"][job]["with"]


def test_reusable_children_declare_tag_prefix_input() -> None:
    """release-core.yml and release-publish.yml accept the tag_prefix input."""
    for name in ("release-core.yml", "release-publish.yml"):
        workflow = _load(WORKFLOWS / name)
        # PyYAML parses the bare ``on`` key as the boolean True.
        call_inputs = workflow[True]["workflow_call"]["inputs"]
        assert "tag_prefix" in call_inputs


# ── Release-notes extraction must read the heading finalize wrote (#1355) ─────

EXTRACT_STEP_NAME = "Extract release notes from CHANGELOG"

# The literal sink the extraction step writes; the test redirects it into
# ``tmp_path`` so the awk logic stays verbatim without touching a shared path.
NOTES_PATH = "/tmp/release-notes.md"

RELEASED_ENTRY = "- **Released thing** ([#1](https://example.invalid/issues/1))"
OLDER_ENTRY = "- **Older thing** ([#0](https://example.invalid/issues/0))"


def _extract_step_run() -> str:
    workflow = _load(WORKFLOWS / "release-publish.yml")
    (job,) = workflow["jobs"].values()
    step = next(s for s in job["steps"] if s.get("name") == EXTRACT_STEP_NAME)
    return step["run"]


def _changelog(tag_prefix: str, *, finalized: bool) -> str:
    """The CHANGELOG the publish job checks out, in either writer state.

    ``finalized=True`` is what ``prepare-changelog finalize --tag-prefix`` writes
    for a *final* release: the prefix composed into both the displayed version
    and the release link. ``finalized=False`` is the *candidate* state — publish
    runs before the finalize step (which is gated on ``release_kind == 'final'``),
    so the heading is still the bare ``## [X.Y.Z] - TBD`` ``prepare`` wrote, with
    no prefix in it even in a prefixed repo.
    """

    def heading(version: str, date: str) -> str:
        if not finalized:
            return f"## [{version}] - TBD"
        tag = f"{tag_prefix}{version}"
        return f"## [{tag}](https://example.invalid/releases/tag/{tag}) - {date}"

    return "\n".join(
        [
            "# Changelog",
            "",
            "## Unreleased",
            "",
            heading("1.0.0", "2026-08-06"),
            "",
            "### Fixed",
            "",
            RELEASED_ENTRY,
            "",
            heading("0.9.0", "2026-07-01"),
            "",
            "### Added",
            "",
            OLDER_ENTRY,
            "",
        ]
    )


@pytest.mark.parametrize("tag_prefix", ["", "v"])
@pytest.mark.parametrize("finalized", [True, False], ids=["final", "candidate"])
def test_release_notes_extraction_reads_the_heading_on_disk(
    tmp_path: Path, tag_prefix: str, finalized: bool
) -> None:
    """The publish step must find the section whichever writer state it meets.

    ``prepare-changelog finalize`` composes ``DEVKIT_TAG_PREFIX`` into the
    heading (``## [v1.0.0](…)``) while ``inputs.version`` stays bare, so an
    extraction matching ``## [1.0.0]`` never matched in a prefixed repo and the
    release was published with the ``No changelog notes found`` fallback body —
    a soft failure that leaves the release green and empty (#1355).

    A candidate publishes before finalize runs, so its heading is the bare
    ``## [1.0.0] - TBD`` regardless of the prefix: matching only the composed tag
    would move the empty-notes bug onto the candidate path instead of fixing it.

    Refs: #1355
    """
    script = _extract_step_run()
    assert NOTES_PATH in script, f"extraction step no longer writes {NOTES_PATH}"
    notes = tmp_path / "release-notes.md"
    script = script.replace(NOTES_PATH, str(notes))

    (tmp_path / "CHANGELOG.md").write_text(
        _changelog(tag_prefix, finalized=finalized), encoding="utf-8"
    )

    proc = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        env={
            **os.environ,
            "VERSION": "1.0.0",
            "TAG_PREFIX": tag_prefix,
        },
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"

    body = notes.read_text(encoding="utf-8")
    assert "No changelog notes found" not in body, (
        f"fallback body published instead of the release notes:\n{body}"
    )
    assert RELEASED_ENTRY in body, f"released section missing from notes:\n{body}"
    assert OLDER_ENTRY not in body, (
        f"extraction ran past the next version heading:\n{body}"
    )
