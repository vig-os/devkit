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

from tests.workflow_scaffold import (
    INIT_WORKSPACE,
    WORKSPACE,
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


def test_gitflow_scaffold_matches_default_path(tmp_path: Path) -> None:
    """The gitflow path == the default (no --workflow) path, byte-for-byte.

    The knob must not perturb the default: an explicit ``--workflow gitflow``
    and an omitted ``--workflow`` produce identical trees.
    """
    default = scaffold_tree(tmp_path, None, name="default")
    gitflow = scaffold_tree(tmp_path, "gitflow", name="gitflow")
    diff = subprocess.run(
        ["diff", "-r", str(default), str(gitflow)], capture_output=True, text=True
    )
    assert diff.returncode == 0, f"gitflow != default:\n{diff.stdout}"


def test_gitflow_render_files_are_byte_identical_to_template(tmp_path: Path) -> None:
    """gitflow leaves every render target byte-identical to today's template.

    render_workflow_model is a no-op for gitflow, so the dev-shaped template
    files copy through unchanged (placeholder-free files only; codeql.yml is
    rewritten by render_codeql_matrix in every mode and is excluded).
    """
    rendered = scaffold_tree(tmp_path, "gitflow")
    for rel in NO_PLACEHOLDER_RENDER_FILES:
        assert (rendered / rel).read_bytes() == (WORKSPACE / rel).read_bytes(), rel


def test_gitflow_keeps_sync_main_to_dev(tmp_path: Path) -> None:
    """gitflow retains sync-main-to-dev.yml (only trunk excludes it)."""
    rendered = scaffold_tree(tmp_path, "gitflow")
    assert (rendered / ".github" / "workflows" / "sync-main-to-dev.yml").exists()


def test_gitflow_vig_os_workflow_line_stays_empty(tmp_path: Path) -> None:
    """Conditional writeback: a gitflow .vig-os keeps the bare DEVKIT_WORKFLOW=.

    Only trunk writes a value back, so a gitflow repo's manifest carries no
    new non-empty line — exactly one bare ``DEVKIT_WORKFLOW=`` line.
    """
    rendered = scaffold_tree(tmp_path, "gitflow")
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


def test_trunk_persists_workflow_in_manifest(tmp_path: Path) -> None:
    """trunk writes DEVKIT_WORKFLOW=trunk back to .vig-os (upgrade-persistent)."""
    rendered = scaffold_tree(tmp_path, "trunk")
    text = (rendered / ".vig-os").read_text(encoding="utf-8")
    assert "DEVKIT_WORKFLOW=trunk" in text


def test_trunk_prepare_release_has_no_dev_cruft(tmp_path: Path) -> None:
    """No residual `dev` in prepare-release beyond /dev/null + the SHA var names.

    The maintainer decision (#1208) rewrites the inert dev step-names/comments to
    main so a trunk repo carries no dev cruft; only the device path and the
    dev_sha/DEV_SHA variable/output names (behavior-neutral) are preserved.
    """
    text = _wf(scaffold_tree(tmp_path, "trunk"), "prepare-release.yml")
    # The branch base itself is retargeted: no heads/dev ref survives, the
    # release branch forks from refs/heads/main (the checkout-ref half lives in
    # test_workflow_prepare_extension.py::test_trunk_prepare_forks_release_branch_from_main).
    assert "heads/dev" not in text
    assert "refs/heads/main" in text
    allowed = ("/dev/null", "dev_sha", "DEV_SHA")
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


def test_trunk_promote_release_has_no_sync_main_to_dev_prose(tmp_path: Path) -> None:
    """promote-release.yml carries no `sync-main-to-dev` prose in trunk (#1233).

    sync-main-to-dev.yml is copy-excluded in trunk, so the two parenthetical
    comments naming it (the header step list + the Summary echo) must be
    scrubbed — otherwise a trunk repo ships comments referencing a workflow it
    does not have. Follow-up to #1226 for a file the render did not touch.
    """
    text = _wf(scaffold_tree(tmp_path, "trunk"), "promote-release.yml")
    assert "sync-main-to-dev" not in text


def test_trunk_ci_pr_filter_excludes_dev(tmp_path: Path) -> None:
    """ci.yml drops `- dev` from the PR branch filter; commit-gate TRUNK=main."""
    text = _wf(scaffold_tree(tmp_path, "trunk"), "ci.yml")
    assert "\n      - dev\n" not in text
    assert 'TRUNK="main"' in text
    assert 'TRUNK="dev"' not in text
    # #1226: no lying `dev` prose survives the render. Only the negatives are
    # pinned — the replacement wording is free to change.
    assert "Pull requests to dev" not in text
    assert "origin/dev" not in text


def test_trunk_codeql_pr_filter_excludes_dev(tmp_path: Path) -> None:
    """codeql.yml drops `- dev` from the PR filter; the main leg survives."""
    text = _wf(scaffold_tree(tmp_path, "trunk"), "codeql.yml")
    assert "\n      - dev\n" not in text
    assert "\n      - main\n" in text
    # #1226: no lying `dev` prose survives the render (negative-only pin).
    assert "Pull requests to dev" not in text


def test_trunk_skill_base_branch_main(tmp_path: Path) -> None:
    """branch-naming SKILL base default dev -> main; example branch untouched."""
    rendered = scaffold_tree(tmp_path, "trunk")
    text = (rendered / ".claude" / "skills" / "branch-naming" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "fall back to `main`" in text
    assert "use `main` as" in text
    # The `chore/sync-main-to-dev` illustration is a branch NAME, not a base
    # default — anchoring must leave it intact.
    assert "chore/sync-main-to-dev" in text


def test_trunk_precommit_drops_dev_clause(tmp_path: Path) -> None:
    """.pre-commit-config drops the `(?!dev$)` protect-clause; main stays."""
    rendered = scaffold_tree(tmp_path, "trunk")
    text = (rendered / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "(?!dev$)" not in text
    assert "(?!main$)" in text


def test_trunk_renovate_preset_targets_main(tmp_path: Path) -> None:
    """renovate-default.json baseBranchPatterns dev -> main (#1336).

    Renovate restricted to a base-branch pattern that matches no existing
    branch has nothing to operate on, so a trunk consumer keeping the
    gitflow-shaped ``["dev"]`` runs no updates at all. The trunk render must
    retarget the shipped preset to main.
    """
    rendered = scaffold_tree(tmp_path, "trunk")
    text = (rendered / ".github" / "renovate-default.json").read_text(encoding="utf-8")
    assert '"baseBranchPatterns": ["main"]' in text
    assert '["dev"]' not in text


def test_trunk_flake_forwards_workflow_to_hooks(tmp_path: Path) -> None:
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
    rendered = scaffold_tree(tmp_path, "trunk")
    flake = (rendered / "flake.nix").read_text(encoding="utf-8")
    assert "DEVKIT_WORKFLOW=" in flake, "flake.nix does not read the workflow model"
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


def test_anchoring_preserves_dev_prefixed_and_device_tokens(tmp_path: Path) -> None:
    """Anchoring must not touch /dev/null, dev_sha, or development/devkit tokens.

    The render's word-boundary/end anchors exist precisely so these behaviorally
    or lexically dev-adjacent tokens survive. /dev/null in particular would be a
    catastrophic corruption if rewritten.
    """
    text = _wf(scaffold_tree(tmp_path, "trunk"), "prepare-release.yml")
    assert "/dev/null" in text  # device path, not a branch ref
    assert "dev_sha:" in text  # workflow output variable name preserved


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
