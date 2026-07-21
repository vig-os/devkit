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
)

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

# Files the trunk render rewrites that carry NO build-time placeholders, so a
# gitflow scaffold copies them byte-for-byte from the template (codeql.yml is
# excluded here: render_codeql_matrix rewrites it in every mode).
NO_PLACEHOLDER_RENDER_FILES = (
    ".github/workflows/prepare-release.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/sync-issues.yml",
    ".claude/skills/branch-naming/SKILL.md",
    ".pre-commit-config.yaml",
)


def _scaffold(
    tmp_path: Path,
    *,
    workflow: str | None = None,
    seed: Path | None = None,
    name: str = "trunkflow",
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Scaffold a workspace by executing the real init-workspace.sh.

    Thin wrapper over the shared ``tests.workflow_scaffold.scaffold`` helper
    (SSoT for the init-workspace invocation, reused by the trunk-parametrized
    dev-assuming suites, #1210); preserves this suite's ``trunkflow`` default
    workspace name.
    """
    return scaffold(tmp_path, workflow=workflow, seed=seed, name=name, check=check)


def _tree(tmp_path: Path, workflow: str | None = None, **kw) -> Path:
    """Scaffold and return the workspace root."""
    name = kw.pop("name", workflow or "gitflow")
    proc = _scaffold(tmp_path, workflow=workflow, name=name, **kw)
    dest = tmp_path / name
    assert proc.returncode == 0, proc.stderr
    return dest


def _wf(rendered: Path, name: str) -> str:
    return (rendered / ".github" / "workflows" / name).read_text(encoding="utf-8")


# ── gitflow no-op guard (the load-bearing default-path invariant) ─────────────


def test_gitflow_scaffold_matches_default_path(tmp_path: Path) -> None:
    """The gitflow path == the default (no --workflow) path, byte-for-byte.

    The knob must not perturb the default: an explicit ``--workflow gitflow``
    and an omitted ``--workflow`` produce identical trees.
    """
    default = _tree(tmp_path, None, name="default")
    gitflow = _tree(tmp_path, "gitflow", name="gitflow")
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
    rendered = _tree(tmp_path, "gitflow")
    for rel in NO_PLACEHOLDER_RENDER_FILES:
        assert (rendered / rel).read_bytes() == (WORKSPACE / rel).read_bytes(), rel


def test_gitflow_keeps_sync_main_to_dev(tmp_path: Path) -> None:
    """gitflow retains sync-main-to-dev.yml (only trunk excludes it)."""
    rendered = _tree(tmp_path, "gitflow")
    assert (rendered / ".github" / "workflows" / "sync-main-to-dev.yml").exists()


def test_gitflow_vig_os_workflow_line_stays_empty(tmp_path: Path) -> None:
    """Conditional writeback: a gitflow .vig-os keeps the bare DEVKIT_WORKFLOW=.

    Only trunk writes a value back, so a gitflow repo's manifest carries no
    new non-empty line — exactly one bare ``DEVKIT_WORKFLOW=`` line.
    """
    rendered = _tree(tmp_path, "gitflow")
    lines = (rendered / ".vig-os").read_text(encoding="utf-8").splitlines()
    workflow_lines = [ln for ln in lines if ln.startswith("DEVKIT_WORKFLOW=")]
    assert workflow_lines == ["DEVKIT_WORKFLOW="]


# ── trunk shape ──────────────────────────────────────────────────────────────


def test_trunk_removes_sync_main_to_dev(tmp_path: Path) -> None:
    """A trunk workspace has no sync-main-to-dev.yml (copy-exclude)."""
    rendered = _tree(tmp_path, "trunk")
    assert not (rendered / ".github" / "workflows" / "sync-main-to-dev.yml").exists()


def test_trunk_upgrade_prunes_leftover_sync_main_to_dev(tmp_path: Path) -> None:
    """A gitflow->trunk upgrade prunes a sync-main-to-dev.yml left by the prior
    gitflow scaffold (the rsync excludes the template copy; the prune removes the
    pre-existing leftover)."""
    gitflow = _tree(tmp_path, "gitflow", name="upgrade")
    assert (gitflow / ".github" / "workflows" / "sync-main-to-dev.yml").exists()
    # Re-scaffold the SAME tree as trunk (the realistic upgrade path).
    proc = _scaffold(tmp_path, workflow="trunk", seed=None, name="upgrade")
    assert proc.returncode == 0, proc.stderr
    assert not (gitflow / ".github" / "workflows" / "sync-main-to-dev.yml").exists()


def test_trunk_persists_workflow_in_manifest(tmp_path: Path) -> None:
    """trunk writes DEVKIT_WORKFLOW=trunk back to .vig-os (upgrade-persistent)."""
    rendered = _tree(tmp_path, "trunk")
    text = (rendered / ".vig-os").read_text(encoding="utf-8")
    assert "DEVKIT_WORKFLOW=trunk" in text


def test_trunk_prepare_release_forks_from_main(tmp_path: Path) -> None:
    """prepare-release retargets its release base dev -> main, zero heads/dev."""
    text = _wf(_tree(tmp_path, "trunk"), "prepare-release.yml")
    assert "heads/dev" not in text
    assert "refs/heads/main" in text
    assert text.count("\n          ref: main\n") == 2  # both checkout jobs
    assert "Create release branch from main" in text


def test_trunk_prepare_release_has_no_dev_cruft(tmp_path: Path) -> None:
    """No residual `dev` in prepare-release beyond /dev/null + the SHA var names.

    The maintainer decision (#1208) rewrites the inert dev step-names/comments to
    main so a trunk repo carries no dev cruft; only the device path and the
    dev_sha/DEV_SHA variable/output names (behavior-neutral) are preserved.
    """
    text = _wf(_tree(tmp_path, "trunk"), "prepare-release.yml")
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


def test_trunk_ci_pr_filter_excludes_dev(tmp_path: Path) -> None:
    """ci.yml drops `- dev` from the PR branch filter; commit-gate TRUNK=main."""
    text = _wf(_tree(tmp_path, "trunk"), "ci.yml")
    assert "\n      - dev\n" not in text
    assert 'TRUNK="main"' in text
    assert 'TRUNK="dev"' not in text


def test_trunk_codeql_pr_filter_excludes_dev(tmp_path: Path) -> None:
    """codeql.yml drops `- dev` from the PR filter; the main leg survives."""
    text = _wf(_tree(tmp_path, "trunk"), "codeql.yml")
    assert "\n      - dev\n" not in text
    assert "\n      - main\n" in text


def test_trunk_sync_issues_default_main(tmp_path: Path) -> None:
    """sync-issues default target-branch dev -> main; no `|| 'dev'` fallback."""
    text = _wf(_tree(tmp_path, "trunk"), "sync-issues.yml")
    assert "default: 'main'" in text
    assert "|| 'dev'" not in text
    assert "|| 'main'" in text
    # The illustrative `e.g., dev, release/x.y.z` description text is left alone.
    assert "e.g., dev" in text


def test_trunk_skill_base_branch_main(tmp_path: Path) -> None:
    """branch-naming SKILL base default dev -> main; example branch untouched."""
    rendered = _tree(tmp_path, "trunk")
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
    rendered = _tree(tmp_path, "trunk")
    text = (rendered / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "(?!dev$)" not in text
    assert "(?!main$)" in text


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
    rendered = _tree(tmp_path, "trunk")
    flake = (rendered / "flake.nix").read_text(encoding="utf-8")
    assert "DEVKIT_WORKFLOW=" in flake, "flake.nix does not read the workflow model"
    assert "inherit workflow;" in flake, "flake.nix does not forward `workflow`"
    manifest = (rendered / ".vig-os").read_text(encoding="utf-8")
    assert "DEVKIT_WORKFLOW=trunk" in manifest


def test_anchoring_preserves_dev_prefixed_and_device_tokens(tmp_path: Path) -> None:
    """Anchoring must not touch /dev/null, dev_sha, or development/devkit tokens.

    The render's word-boundary/end anchors exist precisely so these behaviorally
    or lexically dev-adjacent tokens survive. /dev/null in particular would be a
    catastrophic corruption if rewritten.
    """
    text = _wf(_tree(tmp_path, "trunk"), "prepare-release.yml")
    assert "/dev/null" in text  # device path, not a branch ref
    assert "dev_sha:" in text  # workflow output variable name preserved


# ── guards (enum + contradiction) ────────────────────────────────────────────


def test_enum_guard_rejects_invalid_workflow(tmp_path: Path) -> None:
    """An unknown --workflow value is refused loudly before any mutation."""
    proc = _scaffold(tmp_path, workflow="bogus", check=False)
    assert proc.returncode != 0
    assert "Invalid --workflow" in proc.stderr


def test_contradiction_guard_refuses_implicit_switch(tmp_path: Path) -> None:
    """An explicit --workflow contradicting the persisted value is refused."""
    _tree(tmp_path, "trunk", name="switch")  # persists DEVKIT_WORKFLOW=trunk
    proc = _scaffold(
        tmp_path, workflow="gitflow", seed=None, name="switch", check=False
    )
    assert proc.returncode != 0
    assert "contradicts the persisted DEVKIT_WORKFLOW" in proc.stderr


# ── production wiring seams (flipped from xfail — #1207 / #1208 now landed) ────


def test_vig_os_declares_workflow_key() -> None:
    """#1207: the scaffold manifest ships the opt-in key (default gitflow).

    Mirrors test_ci_runner.py::test_vig_os_declares_ci_runner_key.
    """
    text = (WORKSPACE / ".vig-os").read_text(encoding="utf-8")
    assert "DEVKIT_WORKFLOW=" in text


def test_init_workspace_invokes_render_workflow_model() -> None:
    """#1208: init-workspace.sh ports + invokes render_workflow_model.

    The render logic now lives in init-workspace.sh (sibling to
    render_codeql_matrix), invoked after the rsync copy — no spike prototype.
    """
    init = INIT_WORKSPACE.read_text(encoding="utf-8")
    assert "render_workflow_model" in init
