"""Workflow-shape tests: the DEVKIT_WORKFLOW knob (gitflow default | trunk).

Epic #1205 (sub-issues #1207 manifest key, #1208 scaffold render core, #1209
install/init flag + dev-branch gating). The spike (#1206) proved the approach;
the seams are now wired into production, so these tests drive the REAL
``init-workspace.sh`` end-to-end (the same executed-bash style as
``tests/test_ci_runner.py`` runs the real ``resolve-toolchain`` script).

The locked design realizes ``trunk`` entirely at scaffold time (mirroring the
``DEVKIT_MODE`` structural precedent): a scaffolded workspace is rewritten from
the gitflow shape (long-lived ``dev`` + ``main`` + ``sync-main-to-dev.yml``) to
the trunk shape (``main`` only). No resolve-toolchain runtime wiring, no workflow
twin — every ``dev`` reference in ``prepare-release.yml`` is a plain branch
literal (or an inert step-name/comment), so the trunk render is an anchored
``dev -> main`` rewrite. gitflow is the unchanged default and a provable no-op.

Refs: #1205
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.workflow_scaffold import (
    INIT_WORKSPACE,
    WORKSPACE,
    cached_tree,
    jobs,
    load_workflow,
    scaffold,
    scaffold_tree,
)

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

# Files the trunk render rewrites that carry NO build-time placeholders, so a
# gitflow scaffold copies them byte-for-byte from the template (codeql.yml is
# excluded here: render_codeql_matrix rewrites it in every mode).
NO_PLACEHOLDER_RENDER_FILES = (
    ".github/workflows/prepare-release.yml",
    ".github/workflows/promote-release.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/sync-issues.yml",
    ".github/renovate-default.json",
    ".claude/skills/branch-naming/SKILL.md",
    ".pre-commit-config.yaml",
)


def _wf(rendered: Path, name: str) -> str:
    return (rendered / ".github" / "workflows" / name).read_text(encoding="utf-8")


# ── gitflow no-op guard (the load-bearing default-path invariant) ─────────────


def test_gitflow_scaffold_matches_default_path() -> None:
    """The gitflow path == the default (no --workflow) path, byte-for-byte.

    The knob must not perturb the default: an explicit ``--workflow gitflow``
    and an omitted ``--workflow`` produce identical trees.
    """
    default = cached_tree(None)
    gitflow = cached_tree("gitflow")
    diff = subprocess.run(
        ["diff", "-r", str(default), str(gitflow)], capture_output=True, text=True
    )
    assert diff.returncode == 0, f"gitflow != default:\n{diff.stdout}"


def test_gitflow_render_files_are_byte_identical_to_template() -> None:
    """gitflow leaves every render target byte-identical to today's template.

    render_workflow_model is a no-op for gitflow, so the dev-shaped template
    files copy through unchanged (placeholder-free files only; codeql.yml is
    rewritten by render_codeql_matrix in every mode and is excluded).
    """
    rendered = cached_tree("gitflow")
    for rel in NO_PLACEHOLDER_RENDER_FILES:
        assert (rendered / rel).read_bytes() == (WORKSPACE / rel).read_bytes(), rel


def test_gitflow_keeps_sync_main_to_dev() -> None:
    """gitflow retains sync-main-to-dev.yml (only trunk excludes it)."""
    rendered = cached_tree("gitflow")
    assert (rendered / ".github" / "workflows" / "sync-main-to-dev.yml").exists()


def test_gitflow_vig_os_workflow_line_stays_empty() -> None:
    """Conditional writeback: a gitflow .vig-os keeps the bare DEVKIT_WORKFLOW=.

    Only trunk writes a value back, so a gitflow repo's manifest carries no
    new non-empty line — exactly one bare ``DEVKIT_WORKFLOW=`` line.
    """
    rendered = cached_tree("gitflow")
    lines = (rendered / ".vig-os").read_text(encoding="utf-8").splitlines()
    workflow_lines = [ln for ln in lines if ln.startswith("DEVKIT_WORKFLOW=")]
    assert workflow_lines == ["DEVKIT_WORKFLOW="]


# ── trunk shape ──────────────────────────────────────────────────────────────


def test_trunk_upgrade_prunes_leftover_sync_main_to_dev(tmp_path: Path) -> None:
    """A gitflow->trunk upgrade prunes a sync-main-to-dev.yml left by the prior
    gitflow scaffold (the rsync excludes the template copy; the prune removes the
    pre-existing leftover)."""
    gitflow = scaffold_tree(tmp_path, "gitflow", name="upgrade")
    assert (gitflow / ".github" / "workflows" / "sync-main-to-dev.yml").exists()
    # Re-scaffold the SAME tree as trunk (the realistic upgrade path).
    proc = scaffold(tmp_path, workflow="trunk", seed=None, name="upgrade")
    assert proc.returncode == 0, proc.stderr
    assert not (gitflow / ".github" / "workflows" / "sync-main-to-dev.yml").exists()


def test_trunk_persists_workflow_in_manifest() -> None:
    """trunk writes DEVKIT_WORKFLOW=trunk back to .vig-os (upgrade-persistent)."""
    rendered = cached_tree("trunk")
    text = (rendered / ".vig-os").read_text(encoding="utf-8")
    assert "DEVKIT_WORKFLOW=trunk" in text


def test_trunk_prepare_release_has_no_dev_cruft() -> None:
    """No residual `dev` in prepare-release beyond /dev/null + the SHA var names.

    The maintainer decision (#1208) rewrites the inert dev step-names/comments to
    main so a trunk repo carries no dev cruft; only the device path is preserved
    (the dev_sha/DEV_SHA names the render used to carry are gone since #1479
    renamed them to the model-neutral freeze_sha/FREEZE_SHA).
    """
    text = _wf(cached_tree("trunk"), "prepare-release.yml")
    # The branch base itself is retargeted: no heads/dev ref survives, the
    # release branch forks from heads/main (the checkout-ref half lives in
    # test_workflow_prepare_extension.py::test_trunk_prepare_forks_release_branch_from_main).
    # `refs/heads/main` is deliberately NOT asserted: since #1479 nothing in a
    # trunk render writes to the trunk, so main appears only as a ref *read*.
    assert "heads/dev" not in text
    assert "heads/main" in text
    allowed = ("/dev/null",)
    stray = [
        line
        for line in text.splitlines()
        # word-boundary 'dev' not inside development/devkit/devcontainer
        if any(
            tok in line
            for tok in (" dev ", " dev,", " dev.", " dev'", "/dev\n", "dev branch")
        )
        and not any(a in line for a in allowed)
    ]
    assert not stray, "stray dev tokens:\n" + "\n".join(stray)


def test_trunk_promote_release_has_no_sync_main_to_dev_prose() -> None:
    """promote-release.yml carries no `sync-main-to-dev` prose in trunk (#1233).

    sync-main-to-dev.yml is copy-excluded in trunk, so the two parenthetical
    comments naming it (the header step list + the Summary echo) must be
    scrubbed — otherwise a trunk repo ships comments referencing a workflow it
    does not have. Follow-up to #1226 for a file the render did not touch.
    """
    text = _wf(cached_tree("trunk"), "promote-release.yml")
    assert "sync-main-to-dev" not in text


def test_trunk_ci_pr_filter_excludes_dev() -> None:
    """ci.yml drops `- dev` from the PR branch filter; commit-gate TRUNK=main."""
    text = _wf(cached_tree("trunk"), "ci.yml")
    assert "\n      - dev\n" not in text
    assert 'TRUNK="main"' in text
    assert 'TRUNK="dev"' not in text
    # #1226: no lying `dev` prose survives the render. Only the negatives are
    # pinned — the replacement wording is free to change.
    assert "Pull requests to dev" not in text
    assert "origin/dev" not in text


def test_trunk_codeql_pr_filter_excludes_dev() -> None:
    """codeql.yml drops `- dev` from the PR filter; the main leg survives."""
    text = _wf(cached_tree("trunk"), "codeql.yml")
    assert "\n      - dev\n" not in text
    assert "\n      - main\n" in text
    # #1226: no lying `dev` prose survives the render (negative-only pin).
    assert "Pull requests to dev" not in text


def test_trunk_skill_base_branch_main() -> None:
    """branch-naming SKILL base default dev -> main; example branch untouched."""
    rendered = cached_tree("trunk")
    text = (rendered / ".claude" / "skills" / "branch-naming" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "fall back to `main`" in text
    assert "use `main` as" in text
    # The `chore/sync-main-to-dev` illustration is a branch NAME, not a base
    # default — anchoring must leave it intact.
    assert "chore/sync-main-to-dev" in text


def test_trunk_precommit_drops_dev_clause() -> None:
    """.pre-commit-config drops the `(?!dev$)` protect-clause; main stays."""
    rendered = cached_tree("trunk")
    text = (rendered / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "(?!dev$)" not in text
    assert "(?!main$)" in text


def test_trunk_renovate_preset_targets_main() -> None:
    """renovate-default.json baseBranchPatterns dev -> main (#1336).

    Renovate restricted to a base-branch pattern that matches no existing
    branch has nothing to operate on, so a trunk consumer keeping the
    gitflow-shaped ``["dev"]`` runs no updates at all. The trunk render must
    retarget the shipped preset to main.
    """
    rendered = cached_tree("trunk")
    text = (rendered / ".github" / "renovate-default.json").read_text(encoding="utf-8")
    assert '"baseBranchPatterns": ["main"]' in text
    assert '["dev"]' not in text


def test_trunk_flake_forwards_workflow_to_hooks() -> None:
    """The flake-hooks path follows the workflow model too (#1224).

    The scaffolded ``.pre-commit-config.yaml`` is workflow-model-aware, but a
    direnv consumer on flake-generated hooks (#1167) gets its branch guard from
    ``mkProjectShell`` (the ``nix/hooks.nix`` consumer render), not that file.
    So the scaffolded ``flake.nix`` reads ``DEVKIT_WORKFLOW`` from ``.vig-os``
    and forwards it as ``mkProjectShell``'s ``workflow`` argument, which drops
    the ``(?!dev$)`` clause for trunk — mirroring the scaffold render. Here we
    assert the forwarding wiring is present and the manifest it reads declares
    trunk; the flake-eval half (the generated guard actually loses the clause)
    is covered by ``tests/test_flake_hooks.py::TestWorkflowModelBranchGuard``.
    """
    rendered = cached_tree("trunk")
    flake = (rendered / "flake.nix").read_text(encoding="utf-8")
    # The key is read through the shared vigOsValue helper since #1432.
    assert 'vigOsValue "DEVKIT_WORKFLOW"' in flake, (
        "flake.nix does not read the workflow model"
    )
    assert "inherit workflow;" in flake, "flake.nix does not forward `workflow`"
    manifest = (rendered / ".vig-os").read_text(encoding="utf-8")
    assert "DEVKIT_WORKFLOW=trunk" in manifest


def test_template_flake_guards_workflow_forwarding() -> None:
    """#1249: forward ``workflow`` only when the resolved builder accepts it.

    The template's ``vigos`` input deliberately floats on the default branch,
    so a fresh scaffold may resolve a devkit whose ``mkProjectShell`` predates
    the ``workflow`` argument — unconditional forwarding then fails eval on
    first shell entry (``called with unexpected argument 'workflow'``). The
    call site must gate ``inherit workflow;`` behind a
    ``builtins.functionArgs … ? workflow`` check so older builders fall back
    to their gitflow default instead of breaking the scaffold.
    """
    flake = (WORKSPACE / "flake.nix").read_text(encoding="utf-8")
    assert "inherit workflow;" in flake, "flake.nix does not forward `workflow`"
    assert "builtins.functionArgs vigos.lib.mkProjectShell ? workflow" in flake, (
        "flake.nix forwards `workflow` unconditionally — the floating vigos "
        "input may resolve a devkit that predates the argument (#1249)"
    )
    assert "optionalAttrs" in flake, (
        "flake.nix must merge the guarded `workflow` via lib.optionalAttrs"
    )


def test_anchoring_preserves_dev_prefixed_and_device_tokens() -> None:
    """Anchoring must not touch /dev/null or development/devkit tokens.

    The render's word-boundary/end anchors exist precisely so these behaviorally
    or lexically dev-adjacent tokens survive. /dev/null in particular would be a
    catastrophic corruption if rewritten. (The ``dev_sha`` output this also used
    to pin is gone — #1479 renamed it ``freeze_sha`` — so the devkit-prefixed
    composite name carries the word-boundary half of the assertion now.)
    """
    text = _wf(cached_tree("trunk"), "prepare-release.yml")
    assert "/dev/null" in text  # device path, not a branch ref
    assert "setup-devkit-toolchain" in text  # dev-prefixed token preserved


# ── release topology: branch before freeze, freeze off the trunk (#1479) ─────
#
# The trunk render is a literal ``dev -> main`` substitution, so the SHIPPED
# (gitflow) asset has to carry an ordering that is already model-agnostic:
#
#   1. capture the base head (BASE_SHA),
#   2. create ``release/X.Y.Z`` AT that SHA,
#   3. freeze the changelog onto the freeze target — the base branch under
#      gitflow, the release branch under trunk,
#   4. wait for the freeze target to advance past BASE_SHA (#617),
#   5. fast-forward ``release/X.Y.Z`` onto the freeze commit (a real FF under
#      gitflow, a no-op under trunk — the freeze already landed there).
#
# Freezing onto the base first (the pre-#1479 order) collapses the two-branch
# topology under trunk: head and base resolve to the SAME commit, so
# ``gh pr create`` fails with "No commits between main and release/X.Y.Z", and
# the freeze is a direct push to a trunk that a require-PR ruleset protects.

SCAFFOLD_PREPARE = WORKSPACE / ".github" / "workflows" / "prepare-release.yml"

# The freeze target the trunk render substitutes for gitflow's refs/heads/dev.
TRUNK_FREEZE_TARGET = "refs/heads/${{ needs.validate.outputs.release_branch }}"
TRUNK_FREEZE_REF = "heads/${{ needs.validate.outputs.release_branch }}"


def _prepare_doc(model: str) -> dict:
    """The parsed prepare-release.yml for a workflow model.

    gitflow reads the shipped asset directly (the render is a no-op for it);
    trunk reads the rendered scaffold tree.
    """
    if model == "gitflow":
        return load_workflow(SCAFFOLD_PREPARE)
    path = cached_tree(model) / ".github" / "workflows" / "prepare-release.yml"
    return load_workflow(path)


def _steps(doc: dict, job: str) -> list[dict]:
    return [s for s in (jobs(doc)[job].get("steps") or []) if isinstance(s, dict)]


def _is_commit_action(step: dict) -> bool:
    return "vig-os/commit-action" in str(step.get("uses", ""))


def _is_branch_create(step: dict) -> bool:
    run = str(step.get("run", ""))
    return "git/refs" in run and '-f ref="refs/heads/$RELEASE_BRANCH"' in run


def _index_where(steps: list[dict], pred, what: str) -> int:
    for i, step in enumerate(steps):
        if pred(step):
            return i
    raise AssertionError(f"no step {what}")


@pytest.mark.parametrize("model", ["gitflow", "trunk"])
def test_release_branch_is_created_before_the_changelog_freeze(model: str) -> None:
    """Ordering invariant that makes the trunk render a literal substitution."""
    steps = _steps(_prepare_doc(model), "prepare")
    create = _index_where(steps, _is_branch_create, "creating release/X.Y.Z")
    freeze = _index_where(steps, _is_commit_action, "committing the changelog freeze")
    assert create < freeze, (
        "release/X.Y.Z must be created BEFORE the changelog freeze, so the "
        "freeze target can be the release branch under trunk (#1479)"
    )


def test_gitflow_freeze_still_targets_dev() -> None:
    """The gitflow leg is unchanged: the freeze commit still lands on dev."""
    steps = _steps(_prepare_doc("gitflow"), "prepare")
    freeze = steps[_index_where(steps, _is_commit_action, "committing the freeze")]
    assert (freeze.get("env") or {}).get("TARGET_BRANCH") == "refs/heads/dev"


def test_trunk_freeze_targets_the_release_branch() -> None:
    """Trunk: the freeze lands on release/X.Y.Z, never on the trunk (#1479)."""
    steps = _steps(_prepare_doc("trunk"), "prepare")
    freeze = steps[_index_where(steps, _is_commit_action, "committing the freeze")]
    assert (freeze.get("env") or {}).get("TARGET_BRANCH") == TRUNK_FREEZE_TARGET


def test_trunk_never_commits_to_the_trunk_branch() -> None:
    """No commit-action anywhere in a trunk render writes to ``main``.

    Both the prepare freeze and the rollback's changelog restore must target
    the release branch: a direct push to the trunk is refused by a require-PR
    ruleset unless the Commit App is a bypass actor — the collision class
    #1227 resolved by not pushing to ``main`` at all.
    """
    doc = _prepare_doc("trunk")
    targets = [
        (step.get("env") or {}).get("TARGET_BRANCH")
        for job in jobs(doc).values()
        if isinstance(job, dict)
        for step in (job.get("steps") or [])
        if isinstance(step, dict) and _is_commit_action(step)
    ]
    assert targets, "expected at least one commit-action step"
    assert set(targets) == {TRUNK_FREEZE_TARGET}, targets


@pytest.mark.parametrize("job", ["prepare", "rollback"])
def test_gitflow_freeze_ref_reads_dev(job: str) -> None:
    """The freeze-target ref read (#617 wait, rollback guard) follows dev."""
    refs = [
        (step.get("env") or {}).get("FREEZE_REF")
        for step in _steps(_prepare_doc("gitflow"), job)
        if (step.get("env") or {}).get("FREEZE_REF")
    ]
    assert refs == ["heads/dev"], refs


@pytest.mark.parametrize("job", ["prepare", "rollback"])
def test_trunk_freeze_ref_reads_the_release_branch(job: str) -> None:
    """Under trunk the freeze lives on the release branch, so its ref reads do too.

    The rollback deletes ``release/X.Y.Z`` first, so its post-delete read of
    this ref cannot resolve — which is exactly the "nothing to restore" answer
    the trunk leg needs, and never a read of (or a write to) ``main``.
    """
    refs = [
        (step.get("env") or {}).get("FREEZE_REF")
        for step in _steps(_prepare_doc("trunk"), job)
        if (step.get("env") or {}).get("FREEZE_REF")
    ]
    assert refs == [TRUNK_FREEZE_REF], refs


@pytest.mark.parametrize("model", ["gitflow", "trunk"])
def test_release_branch_fast_forward_is_gated_and_non_forcing(model: str) -> None:
    """Step 5 is a NON-force FF, taken only on a branch this run created.

    A pre-existing ``release/X.Y.Z`` (re-prepare race; ``validate`` normally
    rejects it) may already carry commits that are not ancestors of the freeze
    commit, where the update is not a fast-forward at all — so the tolerant
    pre-#1479 behaviour is kept by skipping it.
    """
    steps = _steps(_prepare_doc(model), "prepare")
    ff = [s for s in steps if "-X PATCH" in str(s.get("run", ""))]
    assert len(ff) == 1, "expected exactly one release-branch fast-forward step"
    assert "-F force=false" in str(ff[0]["run"]), (
        "the release-branch fast-forward must pin force=false"
    )
    assert "branch_created == 'true'" in str(ff[0].get("if", "")), (
        "the fast-forward must be gated on this run having created the branch"
    )


@pytest.mark.parametrize("model", ["gitflow", "trunk"])
def test_open_pr_refuses_a_zero_commit_release_pr(model: str) -> None:
    """The same-SHA guard: head == base is caught in-workflow, before the PR call.

    GitHub refuses to open a PR whose head and base resolve to the same commit
    ("No commits between main and release/X.Y.Z") — the exact trunk failure of
    #1479. A local-git simulation cannot express that server-side refusal (why
    the #1206 spike could not catch it), so the workflow asserts it itself.
    """
    steps = _steps(_prepare_doc(model), "open-pr")
    step = steps[
        _index_where(
            steps,
            lambda s: "gh pr create" in str(s.get("run", "")),
            "opening the draft PR",
        )
    ]
    run = str(step["run"])
    guard = run.find('"$BASE_SHA" = "$HEAD_SHA"')
    assert guard != -1, (
        "the PR-opening step must compare the resolved base and head SHAs"
    )
    assert guard < run.find("gh pr create"), (
        "the same-SHA guard must run before the PR is created"
    )


# ── guards (enum + contradiction) ────────────────────────────────────────────


def test_enum_guard_rejects_invalid_workflow(tmp_path: Path) -> None:
    """An unknown --workflow value is refused loudly before any mutation."""
    proc = scaffold(tmp_path, workflow="bogus", check=False)
    assert proc.returncode != 0
    assert "Invalid --workflow" in proc.stderr


def test_contradiction_guard_refuses_implicit_switch(tmp_path: Path) -> None:
    """An explicit --workflow contradicting the persisted value is refused."""
    scaffold_tree(tmp_path, "trunk", name="switch")  # persists DEVKIT_WORKFLOW=trunk
    proc = scaffold(tmp_path, workflow="gitflow", seed=None, name="switch", check=False)
    assert proc.returncode != 0
    assert "contradicts the persisted DEVKIT_WORKFLOW" in proc.stderr


# ── production wiring seams (flipped from xfail — #1207 / #1208 now landed) ────


def test_init_workspace_invokes_render_workflow_model() -> None:
    """#1208: init-workspace.sh ports + invokes render_workflow_model.

    The render logic now lives in init-workspace.sh (sibling to
    render_codeql_matrix), invoked after the rsync copy — no spike prototype.
    """
    init = INIT_WORKSPACE.read_text(encoding="utf-8")
    assert "render_workflow_model" in init
