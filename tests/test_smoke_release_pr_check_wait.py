"""Release-PR check-wait tests: the wait must not clear on a superseded SHA.

Issue #1737: the smoke-listener's ``wait-release-pr-ci`` job (step "Poll
release PR required checks until green") could observe a complete, green
required-check set for the release PR's PRE-push head SHA, pass, and let
``trigger-promote-release`` dispatch ``promote-release.yml`` while
``finalize``'s ``sync-issues`` push was re-triggering the release PR's CI. On
the 1.17.0 train (run 36389373270), ``Wait for release PR required checks``
passed against a stale check set and promote's own (correct) guard then
refused with "PR #<n> has checks still in progress" -- a race, not a content
defect (a plain re-dispatch, run 36392110808, passed cleanly).

Live timing fact that rules out a naive "recheck the SHA across two 30s poll
iterations" fix: ``sync-issues`` started at 06:57:29 and pushed at 06:58:32,
~63s later -- comfortably longer than one poll interval, so the wait needs
more than a two-sample SHA comparison.

Two families of assertions, mirroring ``tests/test_smoke_dispatch_wait.py``'s
shape/behaviour split:

* **Shape** -- the branch name comes from the PR itself (not reconstructed
  from the version), the release-branch quiescence check (no ``queued``/
  ``in_progress`` run) gates every iteration, the required-checks read is
  anchored by a head-SHA snapshot taken immediately before and after
  ``gh pr checks``, the confirmed SHA is exposed as a job output, and
  ``trigger-promote-release`` carries a last-mile guard that re-reads the PR
  head immediately before dispatch and consumes that output.
* **Behaviour** -- the wait step's real bash executed against a stubbed
  ``gh`` (and a no-op ``sleep``), replaying the 1.17.0 timeline: required
  checks green for SHA A while ``Sync Issues and PRs`` is ``in_progress`` on
  the release branch, then the head moves to SHA B with checks pending, then
  B goes green. The wait must not exit 0 while A was the head, and must exit
  0 only once B is green, reporting B. A head move straddling the checks
  query itself is discarded (no pass, no fail/cancel verdict) rather than
  either accepted or failed.

Refs: #1737
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import TYPE_CHECKING

from tests.workflow_scaffold import (
    REPO_ROOT,
    load_workflow,
    parse_github_output,
    step_by_name,
    steps_of_job,
)

if TYPE_CHECKING:
    from pathlib import Path

LISTENER = (
    REPO_ROOT
    / "assets"
    / "smoke-test"
    / ".github"
    / "workflows"
    / "repository-dispatch.yml"
)

WAIT_JOB = "wait-release-pr-ci"
PROMOTE_JOB = "trigger-promote-release"
WAIT_STEP_NAME = "poll release pr required checks until green"


def _listener() -> dict:
    return load_workflow(LISTENER)


def _steps(job: str) -> list[dict]:
    return steps_of_job(_listener(), job)


def _wait_step() -> dict:
    return step_by_name(_steps(WAIT_JOB), WAIT_STEP_NAME)


def _run_of(step: dict) -> str:
    return str(step.get("run", ""))


# --------------------------------------------------------------------------- #
# Shape
# --------------------------------------------------------------------------- #


def test_head_branch_resolved_from_pr_not_reconstructed_from_version() -> None:
    """The release branch name must come from the PR, not `release/<version>`."""
    body = _run_of(_wait_step())
    assert "--json headRefName" in body, (
        "the wait step must resolve the release PR's head branch via "
        "`gh pr view --json headRefName` (#1737)"
    )
    assert (
        'HEAD_REF_NAME="$(gh pr view' in body
        or 'HEAD_REF_NAME="$(gh pr view' in body.replace("\n", " ")
    ), "the resolved branch name must be captured into a HEAD_REF_NAME variable"
    assert "release/${" not in body.replace(" ", ""), (
        "the branch must not be reconstructed from BASE_VERSION/needs.validate outputs"
    )


def test_quiescence_gate_checks_queued_and_in_progress_runs() -> None:
    """Every iteration must require the release branch to be quiet."""
    body = _run_of(_wait_step())
    assert "gh run list" in body, "expected a `gh run list` quiescence query (#1737)"
    assert '--branch "${HEAD_REF_NAME}"' in body, (
        "the quiescence query must scope to the PR's own head branch"
    )
    assert "--status queued" in body, "must check for queued runs on the release branch"
    assert "--status in_progress" in body, (
        "must check for in_progress runs on the release branch -- this is the "
        "half that actually holds the wait across the finalize -> sync-issues "
        "-> push chain (#1737)"
    )


def test_checks_query_is_anchored_by_head_sha_before_and_after() -> None:
    """`gh pr checks` must be bracketed by two headRefOid reads that must match."""
    body = _run_of(_wait_step())
    assert body.count("headRefOid") >= 2, (
        "the wait must resolve headRefOid both immediately before and "
        "immediately after the `gh pr checks` query (#1737)"
    )

    checks_idx = body.index("gh pr checks")
    before = body[:checks_idx]
    after = body[checks_idx:]
    assert "headRefOid" in before, "no head-SHA snapshot taken before the checks query"
    assert "headRefOid" in after, "no head-SHA snapshot taken after the checks query"

    # A mismatch must be discarded (continue polling), never treated as a
    # pass or a fail/cancel verdict.
    assert re.search(r"PRE_SHA.*!=.*POST_SHA|POST_SHA.*!=.*PRE_SHA", body), (
        "expected an explicit PRE_SHA/POST_SHA mismatch comparison (#1737)"
    )


def test_mismatch_discards_the_observation_without_a_verdict() -> None:
    """A moved head during the checks query must neither pass nor fail the wait."""
    body = _run_of(_wait_step())
    mismatch_re = re.search(r"PRE_SHA.*!=.*POST_SHA|POST_SHA.*!=.*PRE_SHA", body)
    assert mismatch_re, "no PRE_SHA/POST_SHA mismatch guard found"
    # The block guarding the mismatch must `continue` polling, not `exit`.
    tail = body[mismatch_re.start() :]
    next_continue = tail.find("continue")
    next_exit = tail.find("exit")
    assert next_continue != -1, "a discarded observation must `continue` polling"
    assert next_exit == -1 or next_continue < next_exit, (
        "a discarded (superseded) observation must never resolve via `exit` "
        "before it `continue`s polling"
    )


def test_preserved_behaviors_still_present() -> None:
    """Everything already correct must survive: CLOSED/MERGED, --required, etc."""
    body = _run_of(_wait_step())
    assert 'PR_STATE}" = "CLOSED"' in body
    assert 'PR_STATE}" = "MERGED"' in body
    assert "--required" in body
    assert "no required checks reported yet" in body
    assert 'gh pr checks "${PR_NUMBER}" --required --json bucket 2>&1' in body
    assert 'PENDING_COUNT}" -eq 0' in body
    assert "TIMEOUT=1800" in body
    assert "INTERVAL=30" in body
    assert "timed out waiting for release PR required checks" in body


def test_wait_step_has_id_and_job_emits_head_sha_output() -> None:
    """The job must expose the confirmed SHA so promote can consume it."""
    doc = _listener()
    job = doc["jobs"][WAIT_JOB]
    step = _wait_step()
    step_id = step.get("id")
    assert step_id, "the poll step needs an `id` for its output to be wired"

    outputs = job.get("outputs") or {}
    assert "head_sha" in outputs, f"{WAIT_JOB} must expose a `head_sha` output (#1737)"
    assert step_id in str(outputs["head_sha"]), (
        "the head_sha job output must reference the poll step's own output"
    )
    assert 'echo "head_sha=' in _run_of(step) or "head_sha=" in _run_of(step), (
        "the poll step must emit `head_sha=<sha>` to GITHUB_OUTPUT"
    )


def test_promote_job_consumes_the_confirmed_sha_with_a_last_mile_guard() -> None:
    """`trigger-promote-release` must re-check the head immediately before dispatch."""
    doc = _listener()
    promote_job = doc["jobs"][PROMOTE_JOB]
    needs = promote_job.get("needs") or []
    assert WAIT_JOB in needs, f"{PROMOTE_JOB} must depend on {WAIT_JOB} for its output"
    assert "ready-release-pr" in needs, (
        f"{PROMOTE_JOB} must depend on ready-release-pr directly to read the PR number "
        "for the last-mile guard"
    )

    steps = promote_job["steps"]
    names = [str(s.get("name", "")) for s in steps]
    guard_idx = next(
        (
            i
            for i, n in enumerate(names)
            if "guard" in n.lower() or "superseded" in n.lower()
        ),
        None,
    )
    assert guard_idx is not None, (
        f"{PROMOTE_JOB} must carry a guard step re-checking the PR head before dispatch (#1737)"
    )
    trigger_idx = next(i for i, n in enumerate(names) if "Trigger promote-release" in n)
    assert guard_idx < trigger_idx, "the guard must run before the promote dispatch"

    guard_step = steps[guard_idx]
    env = guard_step.get("env") or {}
    assert any(f"needs.{WAIT_JOB}.outputs.head_sha" in str(v) for v in env.values()), (
        "the guard step must consume the confirmed head_sha from the wait job"
    )
    body = _run_of(guard_step)
    assert "headRefOid" in body, "the guard must re-read the current PR head"
    assert "exit 1" in body, "a mismatch must fail the job with an explicit message"


# --------------------------------------------------------------------------- #
# Behaviour -- the wait step's real bash against a stubbed `gh`
# --------------------------------------------------------------------------- #

GH_STUB = r'''#!/usr/bin/env python3
"""`gh` stub for the release-PR check-wait harness.

Scenario carries a list of "iterations", indexed by successive calls to
`gh pr view --json state` (the first call each loop iteration makes). Each
iteration provides the PR state, the queued/in_progress run counts on the
release branch, and (if the wait ever gets that far) the head SHA(s) seen by
the pre/post `headRefOid` snapshots around `gh pr checks`, plus the required
checks bucket set.
"""

import json
import os
import pathlib
import sys

scenario = json.loads(pathlib.Path(os.environ["GH_STUB_SCENARIO"]).read_text())
state_path = pathlib.Path(os.environ["GH_STUB_STATE"])
state = json.loads(state_path.read_text()) if state_path.exists() else {}
state.setdefault("iter", -1)
state.setdefault("oid_calls", 0)

argv = sys.argv[1:]
iterations = scenario["iterations"]


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def save():
    state_path.write_text(json.dumps(state))


def current():
    idx = max(0, min(state["iter"], len(iterations) - 1))
    return iterations[idx]


if argv[:2] == ["pr", "view"]:
    field = opt("--json")
    if field == "state":
        state["iter"] += 1
        state["oid_calls"] = 0
        save()
        print(current()["state"])
    elif field == "headRefName":
        print(scenario["head_ref_name"])
    elif field == "headRefOid":
        it = current()
        state["oid_calls"] += 1
        n = state["oid_calls"]
        save()
        key = "pre_sha" if n <= 1 else "post_sha"
        print(it.get(key, it.get("head_sha", "")))
    else:
        sys.exit(f"gh stub: unsupported pr view --json {field!r}")
    sys.exit(0)

if argv[:2] == ["run", "list"]:
    status = opt("--status")
    it = current()
    print(it.get(f"{status}_count", 0))
    sys.exit(0)

if argv[:2] == ["pr", "checks"]:
    it = current()
    print(json.dumps(it.get("checks", [])))
    sys.exit(0)

sys.exit(f"gh stub: unsupported invocation {argv!r}")
'''

HEAD_REF_NAME = "release/1.17.0"


def _run_wait_step(
    tmp_path: Path, iterations: list[dict]
) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    """Execute the poll step's real bash with a stubbed `gh` and a no-op `sleep`."""
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir()
    gh = stub_dir / "gh"
    gh.write_text(GH_STUB, encoding="utf-8")
    gh.chmod(0o755)
    sleep = stub_dir / "sleep"
    sleep.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    sleep.chmod(0o755)

    scenario = tmp_path / "scenario.json"
    scenario.write_text(
        json.dumps({"head_ref_name": HEAD_REF_NAME, "iterations": iterations}),
        encoding="utf-8",
    )
    github_output = tmp_path / "github_output"
    github_output.touch()

    script = _run_of(_wait_step())
    env = {
        **os.environ,
        "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}",
        "GH_STUB_SCENARIO": str(scenario),
        "GH_STUB_STATE": str(tmp_path / "state.json"),
        "GH_TOKEN": "stub",
        "PR_NUMBER": "1737",
        "PR_URL": "https://github.com/vig-os/devkit-smoke-test/pull/1737",
        "GITHUB_OUTPUT": str(github_output),
    }
    proc = subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True, check=False
    )
    return proc, parse_github_output(github_output)


def test_wait_holds_while_sync_issues_is_in_progress_then_passes_on_new_head(
    tmp_path: Path,
) -> None:
    """The 1.17.0 replay: green-for-A-but-in-progress must not pass; B must."""
    iterations = [
        # sync-issues still running on the release branch; checks never even
        # queried -- the quiescence gate must hold regardless of A's state.
        {"state": "OPEN", "queued_count": 0, "in_progress_count": 1},
        {"state": "OPEN", "queued_count": 0, "in_progress_count": 1},
        # sync-issues finished and pushed; head is now B, its CI still pending.
        {
            "state": "OPEN",
            "queued_count": 0,
            "in_progress_count": 0,
            "head_sha": "B",
            "checks": [{"bucket": "pending"}, {"bucket": "pass"}],
        },
        # B is green.
        {
            "state": "OPEN",
            "queued_count": 0,
            "in_progress_count": 0,
            "head_sha": "B",
            "checks": [{"bucket": "pass"}, {"bucket": "pass"}],
        },
    ]
    proc, outputs = _run_wait_step(tmp_path, iterations)

    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert "A" not in outputs.get("head_sha", "?A?"), (
        f"the wait must never confirm the superseded head A:\n{proc.stdout}"
    )
    assert outputs.get("head_sha") == "B", (
        f"the wait must report the confirmed head B:\n{proc.stdout}\n{outputs}"
    )
    assert "in_progress" in proc.stdout.lower() or "quiesce" in proc.stdout.lower(), (
        f"expected the quiescence hold to be logged:\n{proc.stdout}"
    )


def test_head_move_straddling_the_checks_query_is_discarded(tmp_path: Path) -> None:
    """A push landing between the pre- and post-checks SHA reads must be discarded."""
    iterations = [
        # The branch is quiet, but the head moves from A to B exactly while
        # `gh pr checks` is being queried -- the bucket set cannot be
        # attributed to a single commit.
        {
            "state": "OPEN",
            "queued_count": 0,
            "in_progress_count": 0,
            "pre_sha": "A",
            "post_sha": "B",
            "checks": [{"bucket": "pass"}],
        },
        # Now steady on B, and green.
        {
            "state": "OPEN",
            "queued_count": 0,
            "in_progress_count": 0,
            "head_sha": "B",
            "checks": [{"bucket": "pass"}],
        },
    ]
    proc, outputs = _run_wait_step(tmp_path, iterations)

    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert outputs.get("head_sha") == "B"
    assert "moved" in proc.stdout.lower() or "discard" in proc.stdout.lower(), (
        f"the straddling observation must be logged as discarded:\n{proc.stdout}"
    )
    # Must not have exited/passed on the very first (ambiguous) observation.
    first_pass_idx = proc.stdout.find("Release PR required checks passed")
    discard_idx = proc.stdout.lower().find("discard")
    if discard_idx == -1:
        discard_idx = proc.stdout.lower().find("moved")
    assert discard_idx != -1 and (
        first_pass_idx == -1 or discard_idx < first_pass_idx
    ), f"the wait must discard before it ever passes:\n{proc.stdout}"


def test_pending_checks_are_not_a_verdict(tmp_path: Path) -> None:
    """Pending required checks must keep polling, not pass or fail."""
    iterations = [
        {
            "state": "OPEN",
            "queued_count": 0,
            "in_progress_count": 0,
            "head_sha": "B",
            "checks": [{"bucket": "pending"}],
        },
        {
            "state": "OPEN",
            "queued_count": 0,
            "in_progress_count": 0,
            "head_sha": "B",
            "checks": [{"bucket": "pass"}],
        },
    ]
    proc, outputs = _run_wait_step(tmp_path, iterations)
    assert proc.returncode == 0
    assert outputs.get("head_sha") == "B"


def test_failed_required_check_fails_the_wait_for_the_anchored_sha(
    tmp_path: Path,
) -> None:
    """A failed required check (no pending left) must fail the wait loudly."""
    iterations = [
        {
            "state": "OPEN",
            "queued_count": 0,
            "in_progress_count": 0,
            "head_sha": "B",
            "checks": [{"bucket": "fail"}],
        },
    ]
    proc, _outputs = _run_wait_step(tmp_path, iterations)
    assert proc.returncode == 1
    assert "failed" in proc.stdout.lower()


# --------------------------------------------------------------------------- #
# Behaviour -- the promote-lane last-mile guard
# --------------------------------------------------------------------------- #

GUARD_GH_STUB = r"""#!/usr/bin/env bash
set -euo pipefail
if [ "$1 $2" = "pr view" ]; then
  echo "$CURRENT_SHA"
  exit 0
fi
echo "gh stub: unsupported invocation: $*" >&2
exit 1
"""


def _guard_step() -> dict:
    doc = _listener()
    steps = doc["jobs"][PROMOTE_JOB]["steps"]
    names = [str(s.get("name", "")) for s in steps]
    idx = next(
        i
        for i, n in enumerate(names)
        if "guard" in n.lower() or "superseded" in n.lower()
    )
    return steps[idx]


def _run_guard_step(
    tmp_path: Path, confirmed_sha: str, current_sha: str
) -> subprocess.CompletedProcess[str]:
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir()
    gh = stub_dir / "gh"
    gh.write_text(GUARD_GH_STUB, encoding="utf-8")
    gh.chmod(0o755)

    script = _run_of(_guard_step())
    env = {
        **os.environ,
        "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}",
        "GH_TOKEN": "stub",
        "PR_NUMBER": "1737",
        "CONFIRMED_SHA": confirmed_sha,
        "CURRENT_SHA": current_sha,
    }
    return subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True, check=False
    )


def test_guard_passes_when_head_is_unchanged(tmp_path: Path) -> None:
    proc = _run_guard_step(tmp_path, confirmed_sha="B", current_sha="B")
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"


def test_guard_fails_loudly_when_head_moved_again(tmp_path: Path) -> None:
    proc = _run_guard_step(tmp_path, confirmed_sha="B", current_sha="C")
    assert proc.returncode != 0
    assert "B" in proc.stdout and "C" in proc.stdout, (
        f"the guard failure must name both the confirmed and current SHA:\n{proc.stdout}"
    )
