"""Smoke-listener deploy-PR reclaim: a partial create must stay recoverable.

Issue #1499: on the 1.9.0 rc1 train the ``deploy`` job's ``Create deploy PR``
step failed on a transient GraphQL 500 whose wording was
``pull request update failed`` — *update*, not create. ``gh pr create --label``
creates the PR and then labels it in a **second** mutation: the create had
succeeded (devkit-smoke-test#367 existed), the labelling is what 500'd, and the
step exited 1. So ``pr_url`` never reached ``GITHUB_OUTPUT`` (every downstream
job skipped) and an **unlabelled** deploy PR was left open.

``Close stale deploy PRs`` selected candidates with ``--label deploy`` only, so
that orphan was invisible to it: the documented recovery — re-run the failed
jobs — re-entered the create and failed with *"a pull request already exists"*
until a human labelled the PR by hand. The one step whose partial success is
most likely was the one the cleanup could not reclaim.

Three defects, three families of assertions here:

* **Reclaim by branch** — the cleanup selects on ``headRefName`` as well as on
  the label. The branch name is deterministic and is pushed *before* the PR
  exists, so unlike the label it cannot be lost to a partial failure.
* **Adopt, then record, then label** — the create step adopts an existing open
  PR on the deploy branch instead of failing on it, writes ``pr_url``
  immediately, and leaves labelling to a separate, non-fatal step.
* **Notify retries** — the same transient class also killed
  ``notify-failure``'s ``gh issue create`` 20 s later, so no upstream incident
  issue was filed at all. The job that exists for when everything else failed
  must retry.

Shape assertions parse the YAML; behaviour assertions execute the steps' **real
bash** against a stubbed ``gh`` (and a no-op ``sleep``), replaying the rc1
timeline. ``--jq`` filters are handed to the real ``jq``, so the selector under
test is the one that runs.

Refs: #1499
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

# The rc1 deploy branch (dots mapped to dashes, #1444) and the PR the partial
# create left behind on it.
TAG = "1.9.0-rc1"
BRANCH = "chore/deploy-1-9-0-rc1"
ORPHAN_URL = "https://github.com/vig-os/devkit-smoke-test/pull/367"
CREATED_URL = "https://github.com/vig-os/devkit-smoke-test/pull/368"

# A GitHub Actions expression: not valid bash (`${{` is a bad substitution), so
# the executed-bash harness substitutes them out before running a step.
EXPRESSION_RE = re.compile(r"\$\{\{[^{}]*\}\}")


def _steps(job: str) -> list[dict]:
    return steps_of_job(load_workflow(LISTENER), job)


def _run_of(step: dict) -> str:
    return str(step.get("run", ""))


def _deploy_step(*, step_id: str | None = None, name: str | None = None) -> dict:
    steps = _steps("deploy")
    return step_by_id(steps, step_id) if step_id else step_by_name(steps, str(name))


def _pr(number: int, head: str, *, labels: tuple[str, ...] = ()) -> dict:
    return {
        "number": number,
        "headRefName": head,
        "labels": [{"name": label} for label in labels],
        "url": f"https://github.com/vig-os/devkit-smoke-test/pull/{number}",
    }


# --------------------------------------------------------------------------- #
# Shape
# --------------------------------------------------------------------------- #


def test_cleanup_reclaims_deploy_prs_by_head_branch() -> None:
    """The cleanup selector must not depend on a label that can be lost."""
    body = _run_of(_deploy_step(name="Close stale deploy PRs"))

    assert "headRefName" in body, (
        "the stale-PR query must ask for the head branch: a partially-created "
        "deploy PR has no label to select it by (#1499)"
    )
    assert 'startswith("chore/deploy-")' in body, (
        "stale deploy PRs must be reclaimed by the deterministic deploy-branch "
        "prefix, which exists before the PR does"
    )


def test_cleanup_still_reclaims_by_label() -> None:
    """Branch reclaim is additive: a labelled PR must still be closed."""
    body = _run_of(_deploy_step(name="Close stale deploy PRs"))

    assert '"deploy"' in body and "labels" in body, (
        "the label selector must be kept alongside the branch selector"
    )


def test_create_step_does_not_label() -> None:
    """Creating and labelling in one step is the defect itself."""
    body = _run_of(_deploy_step(step_id="create_pr"))

    assert "--label" not in body, (
        "`gh pr create --label` labels in a second mutation whose failure fails "
        "the whole step and loses pr_url (#1499); label in its own step"
    )


def test_pr_url_is_recorded_before_labelling() -> None:
    """``pr_url`` must survive a labelling failure, so it is written first."""
    steps = _steps("deploy")
    create = step_by_id(steps, "create_pr")
    label = step_by_id(steps, "label_pr")

    assert 'pr_url=${PR_URL}" >> "${GITHUB_OUTPUT}"' in _run_of(create), (
        "the create step must publish the PR url as its `pr_url` output"
    )
    assert steps.index(create) < steps.index(label), (
        "labelling must run after the url is recorded, never before"
    )
    assert label.get("env", {}).get("PR_URL") == (
        "${{ steps.create_pr.outputs.pr_url }}"
    ), "the label step must consume the recorded url"


def test_labelling_cannot_fail_the_job() -> None:
    """A label transient must not strand a PR the cleanup can already reclaim."""
    body = _run_of(step_by_id(_steps("deploy"), "label_pr"))

    assert "gh pr edit" in body and "--add-label deploy" in body
    assert "exit 1" not in body, (
        "labelling is advisory now that the cleanup reclaims by branch: it must "
        "not fail the deploy job (#1499)"
    )


def test_notify_retries_upstream_issue_creation() -> None:
    """The job that reports every other failure must survive a transient."""
    body = _run_of(step_by_name(_steps("notify-failure"), "Create upstream failure"))

    assert "gh issue create" in body
    assert re.search(r"for attempt in .*; do", body), (
        "the upstream issue creation must retry: the same GraphQL 500 class "
        "that broke the deploy also swallowed the incident issue (#1499)"
    )


# --------------------------------------------------------------------------- #
# Behaviour — the steps' real bash against a stubbed `gh`
# --------------------------------------------------------------------------- #

GH_STUB = r'''#!/usr/bin/env python3
"""Minimal `gh` stub for the deploy-PR reclaim harness.

The scenario describes the repo's open PRs and how many times each mutation
fails transiently (modelling the GraphQL 500s of #1499). Every invocation is
appended to the log so tests can assert on what a step did, not only on its
exit code. `--jq` filters run through the real jq.
"""

import json
import os
import pathlib
import subprocess
import sys

scenario = json.loads(pathlib.Path(os.environ["GH_STUB_SCENARIO"]).read_text())
state_path = pathlib.Path(os.environ["GH_STUB_STATE"])
state = json.loads(state_path.read_text()) if state_path.exists() else {}

argv = sys.argv[1:]
with pathlib.Path(os.environ["GH_STUB_LOG"]).open("a") as fh:
    fh.write(json.dumps(argv) + "\n")


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def fails(key):
    """True while `key`'s budget of transient failures is not exhausted."""
    remaining = state.get(key, scenario.get(key, 0))
    if remaining <= 0:
        return False
    state[key] = remaining - 1
    state_path.write_text(json.dumps(state))
    return True


def emit(payload):
    jq = opt("--jq")
    if jq is None:
        print(json.dumps(payload))
        return
    proc = subprocess.run(
        ["jq", "-r", jq], input=json.dumps(payload), capture_output=True, text=True
    )
    if proc.returncode != 0:
        sys.exit(f"gh stub: jq failed for {jq!r}: {proc.stderr}")
    sys.stdout.write(proc.stdout)


if argv[:2] == ["pr", "list"]:
    prs = list(scenario.get("prs", []))
    head = opt("--head")
    if head is not None:
        prs = [p for p in prs if p["headRefName"] == head]
    fields = (opt("--json") or "number").split(",")
    emit([{f: p[f] for f in fields} for p in prs])
    sys.exit(0)

if argv[:2] == ["pr", "close"]:
    sys.exit(0)

if argv[:2] == ["pr", "create"]:
    if fails("create_fails"):
        sys.exit(scenario.get("create_error", "GraphQL: Something went wrong"))
    print(scenario["created_url"])
    sys.exit(0)

if argv[:2] == ["pr", "edit"]:
    if fails("edit_fails"):
        sys.exit("pull request update failed: GraphQL: Something went wrong")
    sys.exit(0)

if argv[:2] == ["label", "create"]:
    sys.exit(0)

if argv[:2] == ["issue", "create"]:
    if fails("issue_fails"):
        sys.exit("GraphQL: Something went wrong while executing your query")
    print(scenario.get("issue_url", "https://github.com/vig-os/devkit/issues/1"))
    sys.exit(0)

sys.exit(f"gh stub: unsupported invocation {argv!r}")
'''


class _Listener:
    """Executes listener steps in sequence against one stubbed `gh` state."""

    def __init__(self, tmp_path: Path, **scenario: object) -> None:
        stub_dir = tmp_path / "stub-bin"
        stub_dir.mkdir()
        gh = stub_dir / "gh"
        gh.write_text(GH_STUB, encoding="utf-8")
        gh.chmod(0o755)
        sleep = stub_dir / "sleep"
        sleep.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        sleep.chmod(0o755)

        scenario.setdefault("created_url", CREATED_URL)
        scenario_path = tmp_path / "scenario.json"
        scenario_path.write_text(json.dumps(scenario), encoding="utf-8")

        self._log = tmp_path / "gh-calls.jsonl"
        self._github_output = tmp_path / "github_output"
        self._github_output.touch()
        self._env = {
            **os.environ,
            "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}",
            "GH_STUB_SCENARIO": str(scenario_path),
            "GH_STUB_STATE": str(tmp_path / "state.json"),
            "GH_STUB_LOG": str(self._log),
            "GH_TOKEN": "stub",
            "GITHUB_OUTPUT": str(self._github_output),
            "GITHUB_REPOSITORY": "vig-os/devkit-smoke-test",
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_RUN_ID": "31710999351",
            "TAG": TAG,
            "BRANCH_NAME": BRANCH,
        }

    def run(self, step: dict, **env: str) -> subprocess.CompletedProcess[str]:
        # GitHub expressions are not bash; the steps under test use them only
        # for values the harness supplies directly.
        script = EXPRESSION_RE.sub("stubbed", _run_of(step))
        return subprocess.run(
            ["bash", "-c", script],
            env={**self._env, **env},
            capture_output=True,
            text=True,
            check=False,
        )

    @property
    def outputs(self) -> dict[str, str]:
        return parse_github_output(self._github_output)

    @property
    def calls(self) -> list[list[str]]:
        if not self._log.exists():
            return []
        return [json.loads(line) for line in self._log.read_text().splitlines()]

    def calls_of(self, *prefix: str) -> list[list[str]]:
        return [c for c in self.calls if c[: len(prefix)] == list(prefix)]


def test_unlabelled_deploy_pr_is_reclaimed(tmp_path: Path) -> None:
    """The rc1 replay: the orphan the partial create left must be closed."""
    orphan = _pr(367, BRANCH)
    labelled = _pr(350, "chore/deploy-1-8-0", labels=("deploy",))
    unrelated = _pr(360, "feature/1234-something", labels=("enhancement",))
    listener = _Listener(tmp_path, prs=[orphan, labelled, unrelated])

    proc = listener.run(_deploy_step(name="Close stale deploy PRs"))

    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    closed = {call[2] for call in listener.calls_of("pr", "close")}
    assert "367" in closed, (
        "an unlabelled deploy PR is invisible to a label-only selector, so the "
        f"re-run recovery deadlocks on it (#1499); closed: {closed}"
    )
    assert "350" in closed, f"labelled deploy PRs must still be closed: {closed}"
    assert "360" not in closed, f"a non-deploy PR must never be closed: {closed}"


def test_deploy_pr_url_survives_a_labelling_failure(tmp_path: Path) -> None:
    """The rc1 failure itself: labelling 500s, the url must still be recorded."""
    listener = _Listener(tmp_path, prs=[], edit_fails=99)

    create = listener.run(_deploy_step(step_id="create_pr"))
    label = listener.run(_deploy_step(step_id="label_pr"), PR_URL=CREATED_URL)

    assert create.returncode == 0, f"stdout:\n{create.stdout}\nstderr:\n{create.stderr}"
    assert listener.outputs.get("pr_url") == CREATED_URL, (
        "pr_url must reach GITHUB_OUTPUT before any labelling can fail — "
        f"without it every downstream job skips (#1499): {listener.outputs}"
    )
    assert label.returncode == 0, (
        "a labelling transient must not fail the deploy job now that the "
        f"cleanup reclaims by branch:\n{label.stdout}\n{label.stderr}"
    )


def test_existing_deploy_pr_is_adopted_not_recreated(tmp_path: Path) -> None:
    """A re-run must adopt the open PR instead of dying on 'already exists'."""
    existing = {**_pr(367, BRANCH), "url": ORPHAN_URL}
    listener = _Listener(
        tmp_path,
        prs=[existing],
        create_fails=99,
        create_error="a pull request for branch already exists",
    )

    proc = listener.run(_deploy_step(step_id="create_pr"))

    assert proc.returncode == 0, (
        "re-entering the create step must not fail on the PR a previous attempt "
        f"left open:\n{proc.stdout}\n{proc.stderr}"
    )
    assert listener.calls_of("pr", "create") == [], (
        "an open PR on the deploy branch must be adopted, not recreated"
    )
    assert listener.outputs.get("pr_url") == ORPHAN_URL, (
        f"the adopted PR's url must be recorded: {listener.outputs}"
    )


def test_labelling_retries_a_transient(tmp_path: Path) -> None:
    """Two 500s then success: the label lands without human help."""
    listener = _Listener(tmp_path, prs=[], edit_fails=2)

    proc = listener.run(_deploy_step(step_id="label_pr"), PR_URL=CREATED_URL)

    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert len(listener.calls_of("pr", "edit")) == 3, (
        f"expected two retries then success: {listener.calls_of('pr', 'edit')}"
    )


def test_notify_retries_a_transient(tmp_path: Path) -> None:
    """The incident issue must survive the transient that killed it on rc1."""
    listener = _Listener(tmp_path, issue_fails=2)

    proc = listener.run(step_by_name(_steps("notify-failure"), "Create upstream"))

    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert len(listener.calls_of("issue", "create")) == 3, (
        f"expected two retries then success: {listener.calls_of('issue', 'create')}"
    )


def test_notify_fails_loudly_when_retries_are_exhausted(tmp_path: Path) -> None:
    """A silently-skipped notification is how #1499 had to be written by hand."""
    listener = _Listener(tmp_path, issue_fails=99)

    proc = listener.run(step_by_name(_steps("notify-failure"), "Create upstream"))

    assert proc.returncode != 0, (
        "exhausting the retries must fail the step: an unfiled incident issue "
        f"has to be visible somewhere:\n{proc.stdout}\n{proc.stderr}"
    )
