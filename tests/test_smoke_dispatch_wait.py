"""Smoke-listener shape + behaviour tests: the wait must bind to the dispatched run.

Issue #1477: ``assets/smoke-test/.github/workflows/repository-dispatch.yml``
implements "trigger a workflow, then wait for it" three times (prepare-release,
release, promote-release). Each captured a ``BEFORE_RUN_ID`` baseline and then
polled for *any* run with ``databaseId > BEFORE_RUN_ID`` and
``status == completed``. That guard is not a binding: the dispatched run needs a
moment to appear in the API, so the poll's first iteration can surface a
**previous** run that is already completed and still newer than a stale
baseline. On the 1.8.0 final the release wait printed success 1.5 s after
starting — matching the rc4 run from 47 minutes earlier — and promote-release
was then dispatched against a repo with no ``1.8.0`` release.

Two families of assertions:

* **Shape** — every site stamps a ``DISPATCH_TS`` immediately before
  ``gh workflow run``, feeds it to the wait step, binds on ``createdAt`` *and*
  the id baseline, and uses identical ``--workflow`` / ``--branch`` / ``--event``
  filters on both the capture and the poll so the baseline describes the
  population being polled.
* **Behaviour** — the wait step's real bash is executed against a stubbed ``gh``
  (and a no-op ``sleep``), replaying the 1.8.0 timeline: a stale completed run
  must never be accepted, the dispatched run must be waited on to completion,
  and a newer run appearing mid-wait must not hijack an already-bound wait.

Refs: #1477
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import (
    REPO_ROOT,
    load_workflow,
    step_by_id,
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

# One entry per trigger-and-wait site: job id, dispatched workflow file, the
# baseline-capture step id, the trigger step id and the wait step's name
# fragment. The three sites live in three separate jobs, so the block is
# deliberately inlined three times; these tests keep the copies in lockstep.
SITES = [
    pytest.param(
        "trigger-prepare-release",
        "prepare-release.yml",
        "capture_prepare_before",
        "trigger_prepare",
        "wait for prepare-release completion",
        id="prepare-release",
    ),
    pytest.param(
        "trigger-release",
        "release.yml",
        "capture_release_before",
        "trigger_release",
        "wait for release workflow completion",
        id="release",
    ),
    pytest.param(
        "trigger-promote-release",
        "promote-release.yml",
        "capture_promote_before",
        "trigger_promote",
        "wait for promote-release workflow completion",
        id="promote-release",
    ),
]

# A `gh run list ...` invocation, up to the end of its line or the pipe that
# feeds jq (line continuations are not used inside these invocations).
GH_RUN_LIST_RE = re.compile(r"gh run list [^\n|]*")


def _listener() -> dict:
    return load_workflow(LISTENER)


def _steps(job: str) -> list[dict]:
    return steps_of_job(_listener(), job)


def _run_of(step: dict) -> str:
    return str(step.get("run", ""))


def _gh_run_list(text: str) -> list[str]:
    return [m.group(0).strip() for m in GH_RUN_LIST_RE.finditer(text)]


# --------------------------------------------------------------------------- #
# Shape
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("job", "workflow", "capture_id", "trigger_id", "wait"), SITES)
def test_dispatch_timestamp_stamped_before_trigger(
    job: str, workflow: str, capture_id: str, trigger_id: str, wait: str
) -> None:
    """The trigger step stamps the dispatch time immediately before dispatching."""
    step = step_by_id(_steps(job), trigger_id)
    body = _run_of(step)

    assert "DISPATCH_TS=" in body, (
        f"{job}: the trigger step must stamp a DISPATCH_TS so the wait can bind "
        "to the run it dispatched (#1477)"
    )
    assert re.search(r"DISPATCH_TS=\"\$\(\s*date -u", body), (
        f"{job}: DISPATCH_TS must come from `date -u` in UTC"
    )
    assert 'dispatch_ts=${DISPATCH_TS}" >> "${GITHUB_OUTPUT}"' in body, (
        f"{job}: DISPATCH_TS must be exposed as the `dispatch_ts` step output"
    )

    stamp = body.index("DISPATCH_TS=")
    dispatch = body.index(f"gh workflow run {workflow}")
    assert stamp < dispatch, (
        f"{job}: the timestamp must be stamped BEFORE `gh workflow run`, "
        "otherwise the dispatched run can be created before the stamp and "
        "filtered out of its own wait"
    )


@pytest.mark.parametrize(("job", "workflow", "capture_id", "trigger_id", "wait"), SITES)
def test_wait_step_consumes_baseline_and_timestamp(
    job: str, workflow: str, capture_id: str, trigger_id: str, wait: str
) -> None:
    """The wait step reads both the id baseline and the dispatch timestamp."""
    env = step_by_name(_steps(job), wait).get("env") or {}

    assert (
        env.get("BEFORE_RUN_ID")
        == f"${{{{ steps.{capture_id}.outputs.before_run_id }}}}"
    ), f"{job}: the wait step must keep the id baseline as belt-and-braces"
    assert (
        env.get("DISPATCH_TS") == f"${{{{ steps.{trigger_id}.outputs.dispatch_ts }}}}"
    ), f"{job}: the wait step must consume the trigger step's dispatch timestamp"


@pytest.mark.parametrize(("job", "workflow", "capture_id", "trigger_id", "wait"), SITES)
def test_wait_binds_on_creation_time_and_baseline(
    job: str, workflow: str, capture_id: str, trigger_id: str, wait: str
) -> None:
    """The poll predicate requires a creation-time bind, not only an id ordering."""
    body = _run_of(step_by_name(_steps(job), wait))

    assert "--arg ts" in body and "$ts" in body, (
        f"{job}: the poll must pass DISPATCH_TS into jq (`gh --jq` cannot take "
        "`--arg`, so the JSON is piped to jq)"
    )
    assert re.search(r"\.createdAt\s*>=\s*\$ts", body), (
        f"{job}: the poll must require `createdAt >= DISPATCH_TS` — an id "
        "comparison alone matches a stale completed run (#1477)"
    )
    assert re.search(r"\.databaseId\s*>\s*\(\$before", body), (
        f"{job}: the poll must keep the `databaseId > BEFORE_RUN_ID` guard"
    )


@pytest.mark.parametrize(("job", "workflow", "capture_id", "trigger_id", "wait"), SITES)
def test_capture_and_poll_filters_are_aligned(
    job: str, workflow: str, capture_id: str, trigger_id: str, wait: str
) -> None:
    """Baseline and poll must query the same population of runs."""
    steps = _steps(job)
    capture = _gh_run_list(_run_of(step_by_id(steps, capture_id)))
    poll = _gh_run_list(_run_of(step_by_name(steps, wait)))

    assert len(capture) == 1, f"{job}: expected exactly one baseline `gh run list`"
    assert len(poll) == 1, f"{job}: expected exactly one poll `gh run list`"

    for label, invocation in (("capture", capture[0]), ("poll", poll[0])):
        for flag in (
            f"--workflow {workflow}",
            '--branch "${WORKFLOW_REF}"',
            "--event workflow_dispatch",
        ):
            assert flag in invocation, (
                f"{job}: the {label} `gh run list` must carry `{flag}` so the "
                "baseline describes the population being polled (#1477)"
            )


@pytest.mark.parametrize(("job", "workflow", "capture_id", "trigger_id", "wait"), SITES)
def test_wait_cannot_succeed_without_a_bound_run(
    job: str, workflow: str, capture_id: str, trigger_id: str, wait: str
) -> None:
    """Every success path is guarded by a non-empty, locked-on run id."""
    body = _run_of(step_by_name(_steps(job), wait))

    assert body.count("exit 0") == 1, f"{job}: expected exactly one success exit"
    guard = '[ -n "${RUN_ID}" ]'
    assert guard in body, f"{job}: the terminal-state check must be guarded by {guard}"
    assert body.index(guard) < body.index("exit 0"), (
        f"{job}: `exit 0` must be reachable only under the bound-run guard"
    )
    # Locked on: the run id is resolved only while still empty, so a newer run
    # appearing mid-wait cannot hijack an already-bound wait.
    assert '[ -z "${RUN_ID}" ]' in body, (
        f"{job}: the run id must be resolved only once and then locked on"
    )
    assert body.rstrip().endswith("exit 1"), (
        f"{job}: the timeout must remain a loud failure"
    )


def test_wait_blocks_are_textually_identical_across_sites() -> None:
    """The three inlined copies must stay one reviewable pattern."""
    bodies = []
    for param in SITES:
        job, workflow, _capture, _trigger, wait = param.values
        body = _run_of(step_by_name(_steps(job), wait))
        # Normalize the only intended differences: the workflow file, its
        # human-readable name and the per-site timeout.
        body = body.replace(workflow, "WORKFLOW.yml")
        body = body.replace(workflow.removesuffix(".yml"), "WORKFLOW")
        body = re.sub(r"TIMEOUT=\d+", "TIMEOUT=N", body)
        bodies.append(body)

    assert bodies[0] == bodies[1] == bodies[2], (
        "the three wait blocks must differ only in the dispatched workflow and "
        "the timeout; they are inlined copies of one pattern (#1477)"
    )


# --------------------------------------------------------------------------- #
# Behaviour — the wait step's real bash against a stubbed `gh`
# --------------------------------------------------------------------------- #

GH_STUB = r'''#!/usr/bin/env python3
"""Minimal `gh` stub for the wait-loop harness (tests/test_smoke_dispatch_wait.py).

Scenario runs carry `visible_after` (how many `gh run list` calls must happen
before the run shows up, modelling the API visibility lag) and `completed_after`
(how many status queries against that run return a non-terminal status first).
"""

import json
import os
import pathlib
import re
import sys

scenario = json.loads(pathlib.Path(os.environ["GH_STUB_SCENARIO"]).read_text())
state_path = pathlib.Path(os.environ["GH_STUB_STATE"])
state = json.loads(state_path.read_text()) if state_path.exists() else {}
state.setdefault("list_calls", 0)
state.setdefault("status_calls", {})

argv = sys.argv[1:]


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def save():
    state_path.write_text(json.dumps(state))


if argv[:2] == ["run", "list"]:
    seq = state["list_calls"]
    state["list_calls"] += 1
    save()
    runs = [r for r in scenario["runs"] if seq >= r.get("visible_after", 0)]
    runs.sort(key=lambda r: -r["databaseId"])  # gh lists newest first
    runs = runs[: int(opt("--limit", "1"))]
    fields = (opt("--json") or "databaseId").split(",")
    payload = [{f: r[f] for f in fields} for r in runs]
    jq = opt("--jq")
    if jq is not None:
        m = re.fullmatch(r"\.\[0\]\.databaseId // (empty|0)", jq)
        if not m:
            sys.exit(f"gh stub: unsupported --jq {jq!r}")
        if payload:
            print(payload[0]["databaseId"])
        elif m.group(1) == "0":
            print(0)
    else:
        print(json.dumps(payload))
    sys.exit(0)

if argv[:2] == ["run", "view"]:
    run_id = argv[2]
    run = next(
        (r for r in scenario["runs"] if str(r["databaseId"]) == run_id), None
    )
    if run is None:
        sys.exit(f"gh stub: no such run {run_id}")
    if opt("--json") == "status":
        seen = state["status_calls"].get(run_id, 0)
        state["status_calls"][run_id] = seen + 1
        save()
        print("completed" if seen >= run.get("completed_after", 0) else "in_progress")
    else:
        print(run.get("conclusion", "success"))
    sys.exit(0)

sys.exit(f"gh stub: unsupported invocation {argv!r}")
'''

# The 1.8.0 final (listener run 31603474367): a days-old baseline, the rc4
# release run from 47 minutes earlier, and the run this job actually dispatched.
STALE_BASELINE = 29848630377
RC4_RUN = {
    "databaseId": 31599958705,
    "createdAt": "2026-08-12T13:09:00Z",
    "url": "https://github.com/vig-os/devkit-smoke-test/actions/runs/31599958705",
    "status": "completed",
    "conclusion": "success",
    "visible_after": 0,
    "completed_after": 0,
}
DISPATCHED_RUN = {
    "databaseId": 31604068811,
    "createdAt": "2026-08-12T13:56:27Z",
    "url": "https://github.com/vig-os/devkit-smoke-test/actions/runs/31604068811",
    "conclusion": "success",
    # Invisible to the first two polls: the API lag that made the stale match
    # possible in the first place.
    "visible_after": 2,
    "completed_after": 1,
}
DISPATCH_TS = "2026-08-12T13:55:28Z"


def _run_wait_step(
    tmp_path: Path, job: str, wait: str, runs: list[dict]
) -> subprocess.CompletedProcess[str]:
    """Execute a wait step's real bash with a stubbed `gh` and a no-op `sleep`."""
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir()
    gh = stub_dir / "gh"
    gh.write_text(GH_STUB, encoding="utf-8")
    gh.chmod(0o755)
    sleep = stub_dir / "sleep"
    sleep.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    sleep.chmod(0o755)

    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps({"runs": runs}), encoding="utf-8")

    script = _run_of(step_by_name(_steps(job), wait))
    env = {
        **os.environ,
        "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}",
        "GH_STUB_SCENARIO": str(scenario),
        "GH_STUB_STATE": str(tmp_path / "state.json"),
        "GH_TOKEN": "stub",
        "WORKFLOW_REF": "dev",
        "BEFORE_RUN_ID": str(STALE_BASELINE),
        "DISPATCH_TS": DISPATCH_TS,
    }
    return subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True, check=False
    )


@pytest.mark.parametrize(("job", "workflow", "capture_id", "trigger_id", "wait"), SITES)
def test_stale_completed_run_is_never_accepted(
    tmp_path: Path,
    job: str,
    workflow: str,
    capture_id: str,
    trigger_id: str,
    wait: str,
) -> None:
    """The 1.8.0 replay: only the stale rc4 run exists, so the wait must not pass."""
    proc = _run_wait_step(tmp_path, job, wait, [RC4_RUN])

    assert proc.returncode != 0, (
        "a completed run created before the dispatch must never satisfy the "
        f"wait; stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "completed successfully" not in proc.stdout, (
        f"the wait reported success without observing its own run:\n{proc.stdout}"
    )
    assert "timed out" in proc.stdout, (
        f"the timeout must remain a loud failure:\n{proc.stdout}"
    )


@pytest.mark.parametrize(("job", "workflow", "capture_id", "trigger_id", "wait"), SITES)
def test_dispatched_run_is_bound_and_waited_on(
    tmp_path: Path,
    job: str,
    workflow: str,
    capture_id: str,
    trigger_id: str,
    wait: str,
) -> None:
    """The dispatched run appears late, is bound, and is waited on to completion."""
    proc = _run_wait_step(tmp_path, job, wait, [RC4_RUN, dict(DISPATCHED_RUN)])

    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert str(DISPATCHED_RUN["databaseId"]) in proc.stdout, (
        f"the matched run id must be logged for diagnosis:\n{proc.stdout}"
    )
    assert DISPATCHED_RUN["url"] in proc.stdout, (
        f"the matched run url must be logged for diagnosis:\n{proc.stdout}"
    )
    assert str(RC4_RUN["databaseId"]) not in proc.stdout, (
        f"the stale run must never be bound:\n{proc.stdout}"
    )
    assert "completed successfully" in proc.stdout


@pytest.mark.parametrize(("job", "workflow", "capture_id", "trigger_id", "wait"), SITES)
def test_bound_run_is_not_hijacked_by_a_newer_run(
    tmp_path: Path,
    job: str,
    workflow: str,
    capture_id: str,
    trigger_id: str,
    wait: str,
) -> None:
    """Once bound, a later run must not take over the wait or its conclusion."""
    bound = {**DISPATCHED_RUN, "conclusion": "failure", "completed_after": 4}
    hijacker = {
        "databaseId": DISPATCHED_RUN["databaseId"] + 1,
        "createdAt": "2026-08-12T13:58:00Z",
        "url": "https://github.com/vig-os/devkit-smoke-test/actions/runs/31604068812",
        "conclusion": "success",
        "visible_after": 3,
        "completed_after": 0,
    }
    proc = _run_wait_step(tmp_path, job, wait, [RC4_RUN, bound, hijacker])

    assert proc.returncode == 1, (
        "the bound run failed, so the wait must fail regardless of a newer "
        f"successful run; stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "concluded with 'failure'" in proc.stdout, (
        f"the bound run's conclusion must be reported:\n{proc.stdout}"
    )
    assert str(hijacker["databaseId"]) not in proc.stdout, (
        f"a later run must not hijack an already-bound wait:\n{proc.stdout}"
    )
