"""Rollback guard tests: ``release.yml`` must never clobber foreign commits.

Issue #1462: the ``rollback`` job's "Rollback release branch" step built a
commit whose **tree was reset to ``PRE_SHA``** — the branch tip captured when
``validate`` started — whenever the run failed and the tip had moved at all.
Both live incidents (#1459/#1460) had ``finalize`` SKIPPED: nothing had been
written, yet the reset destroyed the merged content of #1447 and #1448 on
``release/1.8.0``.

The guarded design pinned here (both devkit's own ``release.yml`` and the
scaffolded consumer ``release.yml``/``release-core.yml``):

1. **No-op when finalize never ran** (``FINALIZE_RESULT`` skipped/empty) and
   for candidates (finalize is branch-neutral unless ``release_kind`` is
   ``final``).
2. **Refuse instead of clobber**: finalize exports the exact commit SHA it
   wrote (commit-action's ``commit-sha`` output) and the last branch tip it
   observed; rollback only proceeds when the current tip is exactly that
   chain — the finalize commit, optionally with the sync-issues commit on
   top, parented on the pre-finalization snapshot. Anything else fails the
   step loudly and leaves the branch alone.
3. The tree-level revert commit is kept, but only after the chain proof makes
   it equivalent to reverting the run's own commit(s). The existing
   ``CURRENT_SHA == PRE_SHA`` no-op is retained.

The decision matrix is executed for real: the step's bash runs against ``gh``
and ``retry`` stubs that simulate the Git Data API, mirroring the executed-bash
harness precedent in ``workflow_scaffold.run_resolve_toolchain``.

Refs: #1462
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from tests.workflow_scaffold import (
    WORKFLOWS,
    load_workflow,
    step_by_name,
    steps_of_job,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# copy id -> release.yml path carrying the rollback job
ROLLBACK_COPIES: dict[str, Path] = {
    "devkit": REPO_ROOT / ".github" / "workflows" / "release.yml",
    "scaffold": WORKFLOWS / "release.yml",
}


def _rollback_step(copy: str) -> dict:
    workflow = load_workflow(ROLLBACK_COPIES[copy])
    steps = steps_of_job(workflow, "rollback")
    return step_by_name(steps, "Rollback release branch")


# ── finalize exports the SHA(s) it wrote ──────────────────────────────────────


def test_devkit_finalize_exports_commit_and_post_sync_shas() -> None:
    """Devkit finalize exposes the commit-action SHA and the post-sync tip."""
    workflow = load_workflow(ROLLBACK_COPIES["devkit"])
    finalize = workflow["jobs"]["finalize"]
    outputs = finalize["outputs"]
    assert "finalize_commit_sha" in outputs
    assert "commit-sha" in outputs["finalize_commit_sha"]
    assert "post_sync_sha" in outputs

    # The commit-action step carries the id the output references.
    commit_step = step_by_name(finalize["steps"], "Commit finalization")
    assert commit_step.get("id"), "commit-action step needs an id for its output"
    assert commit_step["id"] in outputs["finalize_commit_sha"]

    # The post-sync tip is recorded after the sync-issues wait so the rollback
    # job can recognize the sync commit as this run's own write.
    names = [str(s.get("name", "")) for s in finalize["steps"]]
    sync_idx = next(i for i, n in enumerate(names) if "Trigger sync-issues" in n)
    post_idx = next(i for i, n in enumerate(names) if "post-sync" in n.lower())
    assert post_idx > sync_idx


def test_scaffold_core_exports_finalize_result_and_commit_sha() -> None:
    """release-core.yml re-exposes finalize's ran/skipped state and commit SHA.

    ``jobs.finalize.result`` would be the natural source, but actionlint's
    jobs-context type for ``workflow_call`` outputs only carries ``outputs``,
    so the signal is a first-step marker output: empty (-> 'skipped') when the
    job never started, 'ran' otherwise.
    """
    core = load_workflow(WORKFLOWS / "release-core.yml")
    call_outputs = core[True]["workflow_call"]["outputs"]

    assert "finalize_result" in call_outputs
    result_value = call_outputs["finalize_result"]["value"]
    assert "jobs.finalize.outputs.finalize_ran" in result_value
    assert "'skipped'" in result_value

    finalize = core["jobs"]["finalize"]
    assert "finalize_ran" in finalize["outputs"]
    first_step = finalize["steps"][0]
    assert first_step.get("id") == "started", (
        "the ran/skipped marker must be the first step so any finalize "
        "execution — even one that fails immediately after — records it"
    )

    assert "finalize_commit_sha" in call_outputs
    assert "finalize_commit_sha" in finalize["outputs"]
    assert "commit-sha" in finalize["outputs"]["finalize_commit_sha"]
    commit_step = step_by_name(finalize["steps"], "Commit and push finalization")
    assert commit_step.get("id"), "commit-action step needs an id for its output"
    assert commit_step["id"] in finalize["outputs"]["finalize_commit_sha"]


# ── rollback step wiring ──────────────────────────────────────────────────────


@pytest.mark.parametrize("copy", ROLLBACK_COPIES)
def test_rollback_step_threads_the_guard_inputs(copy: str) -> None:
    """The step receives finalize result/kind and the run-written SHAs."""
    env = _rollback_step(copy)["env"]
    for key in (
        "PRE_SHA",
        "FINALIZE_RESULT",
        "RELEASE_KIND",
        "FINALIZE_COMMIT_SHA",
        "FINAL_TIP_SHA",
    ):
        assert key in env, f"{copy}: rollback step env is missing {key}"
    if copy == "devkit":
        assert "needs.finalize.result" in env["FINALIZE_RESULT"]
    else:
        assert "needs.core.outputs.finalize_result" in env["FINALIZE_RESULT"]


def test_scaffold_rollback_never_rewrites_history() -> None:
    """The consumer rollback drops ``reset --hard`` + force-push for a revert."""
    run = _rollback_step("scaffold")["run"]
    assert "reset --hard" not in run
    assert "--force-with-lease" not in run
    assert "git push" not in run


def test_scaffold_rollback_needs_no_release_branch_checkout() -> None:
    """The API-based revert needs no working-tree checkout of the branch."""
    workflow = load_workflow(ROLLBACK_COPIES["scaffold"])
    names = [str(s.get("name", "")) for s in steps_of_job(workflow, "rollback")]
    assert "Checkout release branch" not in names
    assert "Configure git" not in names


@pytest.mark.parametrize("copy", ROLLBACK_COPIES)
def test_rollback_gates_the_sync_tip_on_the_fixed_message(copy: str) -> None:
    """Both copies pin the sync commit's message; devkit also pins the author.

    The message constant is shared: the scaffolded sync-issues.yml ships the
    same 'chore: sync issues and PRs' default and the release-core dispatch
    does not override it. The author is only a constant inside the vig-os
    org (commit-action-bot[bot], live-verified on daeb5c54), so the scaffold
    omits the SYNC_COMMIT_AUTHOR knob.
    """
    step = _rollback_step(copy)
    assert "chore: sync issues and PRs" in step["run"]
    if copy == "devkit":
        assert step["env"].get("SYNC_COMMIT_AUTHOR") == "commit-action-bot[bot]"
    else:
        assert "SYNC_COMMIT_AUTHOR" not in step["env"]


def test_devkit_pr_body_restore_skips_when_finalize_never_ran() -> None:
    """The PR-body restore (and its token mint) no-op when finalize skipped."""
    workflow = load_workflow(ROLLBACK_COPIES["devkit"])
    steps = steps_of_job(workflow, "rollback")
    restore = step_by_name(steps, "Restore release PR body")
    token = step_by_name(steps, "Generate Release App Token")
    for step in (restore, token):
        assert "needs.finalize.result != 'skipped'" in str(step["if"])


# ── executed decision matrix ──────────────────────────────────────────────────

_GH_STUB = """\
#!/usr/bin/env bash
# Git Data API simulator for the rollback step.
#  - ref read  -> $FAKE_CURRENT_SHA
#  - commit read (--jq .tree.sha)  -> tree-<sha>
#  - commit read (facts query, jq join) -> $PARENT_<sha> TAB $AUTHOR_<sha> TAB $TITLE_<sha>
#  - commit read (parents query)   -> $PARENT_<sha> (empty when unset)
#  - POST git/commits -> $FAKE_REVERT_SHA ; PATCH ref -> recorded only
args="$*"
echo "$args" >> "$GH_LOG"
case "$args" in
  *"-X POST"*)
    echo "$FAKE_REVERT_SHA"
    ;;
  *"-X PATCH"*)
    ;;
  *git/refs/heads/*|*git/ref/heads/*)
    echo "$FAKE_CURRENT_SHA"
    ;;
  *git/commits/*)
    sha="${args##*git/commits/}"
    sha="${sha%% *}"
    if [[ "$args" == *".tree.sha"* ]]; then
      echo "tree-$sha"
    elif [[ "$args" == *"join"* ]]; then
      p="PARENT_$sha"; a="AUTHOR_$sha"; t="TITLE_$sha"
      printf '%s\\t%s\\t%s\\n' "${!p:-}" "${!a:-}" "${!t:-}"
    else
      var="PARENT_$sha"
      echo "${!var:-}"
    fi
    ;;
esac
"""

_RETRY_STUB = """\
#!/usr/bin/env bash
while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do shift; done
shift
exec "$@"
"""


def _run_rollback_script(
    copy: str, tmp_path: Path, env_overrides: dict[str, str]
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Execute the rollback step's bash against the gh/retry stubs."""
    script = _rollback_step(copy)["run"]
    script = script.replace("${{ github.repository }}", "o/r")
    assert "${{" not in script, f"{copy}: unreplaced expression in run script"

    stub_bin = tmp_path / "bin"
    stub_bin.mkdir(exist_ok=True)
    for name, body in (("gh", _GH_STUB), ("retry", _RETRY_STUB)):
        stub = stub_bin / name
        stub.write_text(body, encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

    gh_log = tmp_path / "gh.log"
    gh_log.touch()

    env = {
        **os.environ,
        "PATH": f"{stub_bin}{os.pathsep}{os.environ['PATH']}",
        "GH_LOG": str(gh_log),
        "GH_TOKEN": "test-token",
        "VERSION": "9.9.9",
        "PRE_SHA": "presha",
        "FAKE_REVERT_SHA": "revertsha",
        # defaults; individual cases override
        "FINALIZE_RESULT": "success",
        "RELEASE_KIND": "final",
        "FINALIZE_COMMIT_SHA": "",
        "FINAL_TIP_SHA": "",
        "FAKE_CURRENT_SHA": "presha",
        **env_overrides,
    }
    # Mirror literal (non-expression) step env the workflow copy defines, e.g.
    # devkit's SYNC_COMMIT_AUTHOR knob; the scaffold omits it on purpose.
    step_env = _rollback_step(copy).get("env", {})
    for key, value in step_env.items():
        if key not in env and "${{" not in str(value):
            env[key] = str(value)
    proc = subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True
    )
    calls = gh_log.read_text(encoding="utf-8").splitlines()
    return proc, calls


def _writes(calls: list[str]) -> list[str]:
    return [c for c in calls if "-X POST" in c or "-X PATCH" in c]


@pytest.mark.parametrize("copy", ROLLBACK_COPIES)
def test_noop_when_finalize_skipped(copy: str, tmp_path: Path) -> None:
    """THE incident shape: validate failed, finalize skipped, branch moved."""
    proc, calls = _run_rollback_script(
        copy,
        tmp_path,
        {"FINALIZE_RESULT": "skipped", "FAKE_CURRENT_SHA": "foreignsha"},
    )
    assert proc.returncode == 0, proc.stderr
    assert not _writes(calls), f"branch written despite skipped finalize: {calls}"


@pytest.mark.parametrize("copy", ROLLBACK_COPIES)
def test_noop_for_candidates(copy: str, tmp_path: Path) -> None:
    """Candidates never write a finalize commit; the branch is left alone."""
    proc, calls = _run_rollback_script(
        copy,
        tmp_path,
        {"RELEASE_KIND": "candidate", "FAKE_CURRENT_SHA": "foreignsha"},
    )
    assert proc.returncode == 0, proc.stderr
    assert not _writes(calls), f"branch written on a candidate run: {calls}"


@pytest.mark.parametrize("copy", ROLLBACK_COPIES)
def test_noop_when_branch_already_at_pre_sha(copy: str, tmp_path: Path) -> None:
    """The existing exact-match no-op survives the redesign."""
    proc, calls = _run_rollback_script(copy, tmp_path, {})
    assert proc.returncode == 0, proc.stderr
    assert not _writes(calls)


@pytest.mark.parametrize("copy", ROLLBACK_COPIES)
def test_reverts_when_tip_is_the_finalize_commit(copy: str, tmp_path: Path) -> None:
    """Tip == finalize commit parented on the snapshot: revert proceeds."""
    proc, calls = _run_rollback_script(
        copy,
        tmp_path,
        {
            "FINALIZE_COMMIT_SHA": "fsha",
            "FINAL_TIP_SHA": "fsha",
            "FAKE_CURRENT_SHA": "fsha",
            "PARENT_fsha": "presha",
        },
    )
    assert proc.returncode == 0, proc.stderr
    writes = _writes(calls)
    assert any("-X POST" in c and "tree=tree-presha" in c for c in writes), (
        f"expected a revert commit with the pre-finalization tree: {calls}"
    )
    assert any("-X PATCH" in c and "sha=revertsha" in c for c in writes), (
        f"expected the branch ref moved to the revert commit: {calls}"
    )


@pytest.mark.parametrize("copy", ROLLBACK_COPIES)
def test_reverts_when_tip_is_sync_commit_on_finalize(copy: str, tmp_path: Path) -> None:
    """Tip == genuine sync commit whose chain is sync -> finalize -> snapshot."""
    proc, calls = _run_rollback_script(
        copy,
        tmp_path,
        {
            "FINALIZE_COMMIT_SHA": "fsha",
            "FINAL_TIP_SHA": "ssha",
            "FAKE_CURRENT_SHA": "ssha",
            "PARENT_ssha": "fsha",
            "AUTHOR_ssha": "commit-action-bot[bot]",
            "TITLE_ssha": "chore: sync issues and PRs",
            "PARENT_fsha": "presha",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert any("-X PATCH" in c and "sha=revertsha" in c for c in _writes(calls))


@pytest.mark.parametrize("copy", ROLLBACK_COPIES)
def test_refuses_foreign_squash_commit_atop_finalize(copy: str, tmp_path: Path) -> None:
    """A squash merge is single-parent too: parentage alone cannot tell a
    foreign PR squash-merged between the finalize commit and the post-sync
    record from the sync commit. The message gate must refuse it."""
    proc, calls = _run_rollback_script(
        copy,
        tmp_path,
        {
            "FINALIZE_COMMIT_SHA": "fsha",
            "FINAL_TIP_SHA": "xsha",
            "FAKE_CURRENT_SHA": "xsha",
            "PARENT_xsha": "fsha",
            "AUTHOR_xsha": "Some Human",
            "TITLE_xsha": "fix(scope): foreign change squash-merged mid-run",
            "PARENT_fsha": "presha",
        },
    )
    assert proc.returncode != 0, "foreign squash commit must fail the rollback step"
    assert not _writes(calls), f"foreign squash commit clobbered: {calls}"
    assert "Refusing" in proc.stdout + proc.stderr


@pytest.mark.parametrize("copy", ROLLBACK_COPIES)
def test_sync_author_gate_applies_where_the_bot_name_is_constant(
    copy: str, tmp_path: Path
) -> None:
    """Right message but wrong author: devkit pins its org's commit bot via the
    SYNC_COMMIT_AUTHOR knob and refuses; the scaffold ships without the knob
    (consumer App bot names are not a devkit-known constant) and relies on the
    message gate, so it reverts."""
    proc, calls = _run_rollback_script(
        copy,
        tmp_path,
        {
            "FINALIZE_COMMIT_SHA": "fsha",
            "FINAL_TIP_SHA": "xsha",
            "FAKE_CURRENT_SHA": "xsha",
            "PARENT_xsha": "fsha",
            "AUTHOR_xsha": "Some Human",
            "TITLE_xsha": "chore: sync issues and PRs",
            "PARENT_fsha": "presha",
        },
    )
    if copy == "devkit":
        assert proc.returncode != 0, "devkit must also pin the sync commit author"
        assert not _writes(calls)
    else:
        assert proc.returncode == 0, proc.stderr
        assert any("-X PATCH" in c for c in _writes(calls))


@pytest.mark.parametrize("copy", ROLLBACK_COPIES)
def test_refuses_when_tip_is_a_foreign_commit(copy: str, tmp_path: Path) -> None:
    """A tip this run did not write fails loudly and leaves the branch alone."""
    proc, calls = _run_rollback_script(
        copy,
        tmp_path,
        {
            "FINALIZE_COMMIT_SHA": "fsha",
            "FINAL_TIP_SHA": "fsha",
            "FAKE_CURRENT_SHA": "foreignsha",
            "PARENT_fsha": "presha",
        },
    )
    assert proc.returncode != 0, "foreign tip must fail the rollback step"
    assert not _writes(calls), f"foreign tip clobbered: {calls}"
    assert "Refusing" in proc.stdout + proc.stderr


@pytest.mark.parametrize("copy", ROLLBACK_COPIES)
def test_refuses_when_finalize_commit_sits_on_a_foreign_parent(
    copy: str, tmp_path: Path
) -> None:
    """A mid-run merge beneath the finalize commit blocks the tree reset."""
    proc, calls = _run_rollback_script(
        copy,
        tmp_path,
        {
            "FINALIZE_COMMIT_SHA": "fsha",
            "FINAL_TIP_SHA": "fsha",
            "FAKE_CURRENT_SHA": "fsha",
            "PARENT_fsha": "mergesha",
        },
    )
    assert proc.returncode != 0, "foreign parent must fail the rollback step"
    assert not _writes(calls), f"foreign parent clobbered: {calls}"


@pytest.mark.parametrize("copy", ROLLBACK_COPIES)
def test_refuses_when_no_finalize_commit_sha_and_branch_moved(
    copy: str, tmp_path: Path
) -> None:
    """Finalize failed without exporting its SHA and the tip moved: refuse."""
    proc, calls = _run_rollback_script(
        copy,
        tmp_path,
        {
            "FINALIZE_RESULT": "failure",
            "FAKE_CURRENT_SHA": "somesha",
        },
    )
    assert proc.returncode != 0
    assert not _writes(calls)
