"""Floating-ref backwards guard: the promote validate step's real bash.

Issue #1626: ``promote-release.yml`` moves GHCR ``:latest`` (devkit) and the
opt-in git floating tags (scaffold) unconditionally. The validate job now
compares the version being promoted against the highest *published final*
release — the version those floating refs follow — and refuses before the
irreversible publish when it is lower.

These tests execute the step's ``run:`` body with ``gh`` stubbed to answer the
paginated release listing from a fixture, so the ordering, the draft /
pre-release filtering and the tag-prefix handling are exercised for real.

Refs: #1626
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import REPO_ROOT, WORKFLOWS, load_workflow, steps_of_job

if TYPE_CHECKING:
    from pathlib import Path

PROMOTE_COPIES: dict[str, Path] = {
    "devkit": REPO_ROOT / ".github" / "workflows" / "promote-release.yml",
    "scaffold": WORKFLOWS / "promote-release.yml",
}
COPIES = list(PROMOTE_COPIES)

GH_STUB = r"""#!/usr/bin/env bash
# Answers `gh api repos/<repo>/releases --paginate` from GH_STUB_RELEASES.
set -euo pipefail
[[ "$1" == "api" && "$2" == *"/releases" ]] || { echo "gh stub: unsupported $*" >&2; exit 2; }
printf '%s' "$GH_STUB_RELEASES"
"""


def _guard_script(copy: str) -> str:
    steps = steps_of_job(load_workflow(PROMOTE_COPIES[copy]), "validate")
    step = next(s for s in steps if "backwards" in str(s.get("name", "")).lower())
    return str(step["run"])


def _release(tag: str, *, draft: bool = False, prerelease: bool = False) -> dict:
    return {"tag_name": tag, "draft": draft, "prerelease": prerelease}


def _run(
    copy: str,
    tmp_path: Path,
    *,
    version: str,
    releases: list[dict],
    tag_prefix: str = "",
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "gh"
    stub.write_text(GH_STUB)
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "GH_STUB_RELEASES": json.dumps(releases),
        "GITHUB_REPOSITORY": "vig-os/testrepo",
        "VERSION": version,
        "TAG_PREFIX": tag_prefix,
    }
    return subprocess.run(
        ["bash", "-c", _guard_script(copy)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.mark.parametrize("copy", COPIES)
def test_lower_version_is_refused(copy: str, tmp_path: Path) -> None:
    """A hotfix promoted after a higher train would walk the floating ref back."""
    proc = _run(
        copy,
        tmp_path,
        version="1.14.2",
        releases=[_release("1.14.1"), _release("1.15.0")],
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "backwards" in proc.stdout
    assert "1.15.0" in proc.stdout
    assert "abandon" in proc.stdout


@pytest.mark.parametrize("copy", COPIES)
def test_higher_version_passes(copy: str, tmp_path: Path) -> None:
    proc = _run(
        copy,
        tmp_path,
        version="1.15.0",
        releases=[_release("1.14.1"), _release("1.14.0")],
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.parametrize("copy", COPIES)
def test_ordering_is_numeric_not_lexical(copy: str, tmp_path: Path) -> None:
    """1.10.0 is above 1.9.0 (sort -V), so promoting it must pass."""
    proc = _run(copy, tmp_path, version="1.10.0", releases=[_release("1.9.0")])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    proc = _run(copy, tmp_path, version="1.9.1", releases=[_release("1.10.0")])
    assert proc.returncode == 1, proc.stdout + proc.stderr


@pytest.mark.parametrize("copy", COPIES)
def test_no_published_final_passes(copy: str, tmp_path: Path) -> None:
    """First release ever, or only drafts and pre-releases so far: nothing to protect."""
    proc = _run(copy, tmp_path, version="0.1.0", releases=[])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    proc = _run(
        copy,
        tmp_path,
        version="0.1.0",
        releases=[
            _release("0.1.0", draft=True),
            _release("9.0.0-rc1", prerelease=True),
        ],
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.parametrize("copy", COPIES)
def test_drafts_and_prereleases_are_ignored(copy: str, tmp_path: Path) -> None:
    """Only published finals move the floating refs; a stray draft must not block."""
    proc = _run(
        copy,
        tmp_path,
        version="1.15.0",
        releases=[
            _release("1.14.1"),
            _release("9.9.9", draft=True),
            _release("9.9.9-rc1", prerelease=True),
        ],
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_scaffold_strips_the_tag_prefix(tmp_path: Path) -> None:
    """Prefixed release tags (#1044) are compared as bare versions."""
    proc = _run(
        "scaffold",
        tmp_path,
        version="1.14.2",
        releases=[_release("v1.15.0")],
        tag_prefix="v",
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    proc = _run(
        "scaffold",
        tmp_path,
        version="1.15.1",
        releases=[_release("v1.15.0")],
        tag_prefix="v",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_scaffold_ignores_tags_outside_the_prefix(tmp_path: Path) -> None:
    """Pre-devkit bare tags are not part of the prefixed line being protected."""
    proc = _run(
        "scaffold",
        tmp_path,
        version="1.0.1",
        releases=[_release("3.0.0"), _release("v1.0.0")],
        tag_prefix="v",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
