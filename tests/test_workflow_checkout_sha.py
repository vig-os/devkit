"""Container jobs must not run git before the workspace is a safe.directory.

In a ``container:`` job the checked-out workspace is owned by a different uid
than the container user, so git refuses every command with "detected dubious
ownership" (exit 128) until the workspace is marked a ``safe.directory``. The
scaffold marks it in ``setup-devkit-toolchain``'s in-container branch
(``assets/workspace/.github/actions/setup-devkit-toolchain/action.yml``, step
"Configure in-container toolchain env": ``git config --global --add
safe.directory "$GITHUB_WORKSPACE"``). #2031 put a ``git rev-parse HEAD``
capture before that step and broke Prepare Release in container mode (#2055).

A capture that directly follows ``actions/checkout`` therefore takes the SHA
from the action's documented ``commit`` output instead of running git. A
capture that follows a ``run:`` step which moved HEAD (a later manual
checkout) records that new HEAD with git; the ordering scan below proves it
runs after the safe-directory setup in every container job.

Refs: #2055
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TREES = (ROOT / ".github/workflows", ROOT / "assets/workspace/.github/workflows")
WORKFLOWS = [path for tree in TREES for path in sorted(tree.glob("*.yml"))]
SAFE_DIRECTORY_ACTION = "./.github/actions/setup-devkit-toolchain"
CAPTURE = "Record checkout SHA"
# `git` as a command word: line start, after a shell separator, or in $(...).
GIT_COMMAND = re.compile(r"(?:^|[\s;&|(`])git(?:\s|$)", re.MULTILINE)


def jobs(path):
    return (yaml.safe_load(path.read_text()) or {}).get("jobs", {}) or {}


def runs_git(step):
    return bool(GIT_COMMAND.search(step.get("run", "")))


def establishes_safe_directory(step):
    return step.get("uses", "") == SAFE_DIRECTORY_ACTION or (
        "safe.directory" in step.get("run", "")
    )


CONTAINER_JOBS = [
    pytest.param(path, name, id=f"{path.relative_to(ROOT)}:{name}")
    for path in WORKFLOWS
    for name, job in jobs(path).items()
    if "container" in job
]
CAPTURES = [
    pytest.param(path, name, index, id=f"{path.relative_to(ROOT)}:{name}:{index}")
    for path in WORKFLOWS
    for name, job in jobs(path).items()
    for index, step in enumerate(job.get("steps", []))
    if step.get("name") == CAPTURE
]


def test_scan_is_not_vacuous():
    assert len(CONTAINER_JOBS) >= 20
    assert len(CAPTURES) == 18


def test_safe_directory_action_marks_the_workspace():
    action = yaml.safe_load(
        (ROOT / "assets/workspace" / SAFE_DIRECTORY_ACTION / "action.yml").read_text()
    )
    step = next(
        s
        for s in action["runs"]["steps"]
        if s["name"] == "Configure in-container toolchain env"
    )
    assert 'git config --global --add safe.directory "$GITHUB_WORKSPACE"' in step["run"]


@pytest.mark.parametrize("path,name", CONTAINER_JOBS)
def test_container_job_runs_no_git_before_safe_directory(path, name):
    steps = jobs(path)[name].get("steps", [])
    safe = next(
        (i for i, step in enumerate(steps) if establishes_safe_directory(step)),
        len(steps),
    )
    early = [step.get("name") for step in steps[:safe] if runs_git(step)]
    assert not early, f"git runs before safe.directory is set: {early}"


@pytest.mark.parametrize("path,name,index", CAPTURES)
def test_capture_reads_the_checkout_commit_output(path, name, index):
    steps = jobs(path)[name]["steps"]
    capture, source = steps[index], steps[index - 1]
    assert "${{" not in capture["run"], "pass expressions through env:, not run:"
    assert "set -euo pipefail" in capture["run"]
    assert 'echo "sha=$CHECKOUT_SHA" >> "$GITHUB_OUTPUT"' in capture["run"]
    if "actions/checkout@" in source.get("uses", ""):
        assert source.get("id"), "checkout needs an id for its commit output"
        assert capture.get("env", {}).get("CHECKOUT_SHA") == (
            f"${{{{ steps.{source['id']}.outputs.commit }}}}"
        )
        assert not runs_git(capture)
        assert 'test -n "$CHECKOUT_SHA"' in capture["run"]
    else:
        # A later manual checkout moved HEAD past what actions/checkout saw.
        assert runs_git(source) and "checkout" in source["run"]
        assert "CHECKOUT_SHA=$(git rev-parse HEAD)" in capture["run"]
