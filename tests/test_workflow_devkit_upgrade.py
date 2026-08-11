"""Scaffold + wiring tests for the self-polling devkit-upgrade workflow (#1296).

A managed ``devkit-upgrade.yml`` ships into every consumer and, weekly (or on
explicit dispatch), runs the full-fidelity ``install.sh --force`` upgrade and
opens the adoption PR — Renovate-style pull, with no devkit-side action at
release time. These tests pin the deliverable without executing the workflow:

- the two runtime knobs (``DEVKIT_AUTO_UPGRADE`` gates the schedule path;
  ``DEVKIT_UPGRADE_EXCLUDE`` lists paths reset before the commit) are declared
  in ``.vig-os`` — pinned with every other knob in ``test_vig_os_manifest.py``;
- the template carries the managed banner, both triggers, the public
  ``releases/latest`` version check with prerelease-aware compare, the dedicated
  GitHub App identity (a per-run installation token minted from
  ``DEVKIT_UPGRADE_APP_CLIENT_ID`` + ``DEVKIT_UPGRADE_APP_PRIVATE_KEY``, with a
  one-release legacy ``DEVKIT_UPGRADE_APP_ID`` fallback — #1365/#1366; fail-fast
  when absent; never the default ``GITHUB_TOKEN`` for the PR — #1302), the
  ``install.sh`` bootstrap and the ``nix develop`` commit;
- no ``run:`` block interpolates a dispatch input or event field directly
  (zizmor template-injection: every such value is routed through ``env:``);
- the base branch is workflow-model aware (``dev`` gitflow / ``main`` trunk),
  realized by the scaffold-time ``render_workflow_model`` retarget;
- the ``devkit-upgrade`` feature group (#1284) opts the whole file out.

Refs: #1296
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from tests.workflow_scaffold import (
    INIT_WORKSPACE,
    WORKSPACE,
    scaffold,
    scaffold_tree,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = WORKSPACE / ".github" / "workflows" / "devkit-upgrade.yml"
REL = ".github/workflows/devkit-upgrade.yml"


def _rendered(tmp_path: Path, workflow: str | None = None) -> str:
    tree = scaffold_tree(tmp_path, workflow=workflow)
    return (tree / REL).read_text(encoding="utf-8")


def _steps(text: str) -> list[dict]:
    doc = yaml.safe_load(text)
    steps: list[dict] = []
    for job in (doc.get("jobs") or {}).values():
        for step in job.get("steps", []) or []:
            if isinstance(step, dict):
                steps.append(step)
    return steps


# ── production wiring seams ───────────────────────────────────────────────────


def test_init_workspace_registers_feature_group() -> None:
    """init-workspace.sh lists devkit-upgrade among the valid feature groups."""
    init = INIT_WORKSPACE.read_text(encoding="utf-8")
    assert "devkit-upgrade" in init
    # The VALID_FEATURES allowlist must carry it (an unknown group aborts).
    valid_line = next(
        line for line in init.splitlines() if line.strip().startswith("VALID_FEATURES=")
    )
    assert "devkit-upgrade" in valid_line


def test_init_workspace_writes_back_upgrade_keys() -> None:
    """The manifest-only keys are written back so an upgrade preserves them."""
    init = INIT_WORKSPACE.read_text(encoding="utf-8")
    assert "write_manifest_value DEVKIT_AUTO_UPGRADE" in init
    assert "write_manifest_value DEVKIT_UPGRADE_EXCLUDE" in init


# ── template shape ────────────────────────────────────────────────────────────


def test_template_exists_with_managed_banner() -> None:
    """The workflow ships and carries the managed-file banner."""
    assert TEMPLATE.is_file()
    assert TEMPLATE.read_text(encoding="utf-8").startswith("# Managed by vigOS devkit")


def test_triggers_are_weekly_cron_and_dispatch_version() -> None:
    """Schedule (weekly Monday) + workflow_dispatch with a version input."""
    doc = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    on = doc.get("on", doc.get(True))
    assert isinstance(on, dict)
    crons = [c["cron"] for c in on["schedule"]]
    assert any(c.endswith("* * 1") for c in crons), crons
    assert "version" in on["workflow_dispatch"]["inputs"]


def test_schedule_path_gated_on_auto_upgrade_and_queries_latest() -> None:
    """Schedule path reads DEVKIT_AUTO_UPGRADE and queries the public latest."""
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "DEVKIT_AUTO_UPGRADE" in text
    assert "repos/vig-os/devkit/releases/latest" in text


def test_version_compare_is_prerelease_aware() -> None:
    """A semver compare exists and accounts for prerelease suffixes."""
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "version_ge" in text
    # No-op when current or AHEAD: prerelease handling is load-bearing so a
    # consumer on an rc of a newer train is never downgraded.
    assert "prerelease" in text.lower()


def test_requires_app_identity_and_never_uses_github_token_for_pr() -> None:
    """The GitHub App is the ONLY identity: a per-run installation token is
    minted from DEVKIT_UPGRADE_APP_CLIENT_ID + DEVKIT_UPGRADE_APP_PRIVATE_KEY
    (fail-fast when absent), and no static token secret remains (#1302)."""
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "secrets.DEVKIT_UPGRADE_APP_CLIENT_ID" in text
    assert "secrets.DEVKIT_UPGRADE_APP_PRIVATE_KEY" in text
    # A clear fail-fast guard when either secret is absent.
    assert "not configured" in text
    steps = _steps(text)
    # A SHA-pinned create-github-app-token step mints the per-run token.
    mint_steps = [
        s for s in steps if "create-github-app-token" in str(s.get("uses", ""))
    ]
    assert mint_steps, "no create-github-app-token step found"
    for s in mint_steps:
        assert re.search(r"create-github-app-token@[0-9a-f]{40}", s["uses"]), (
            "app-token action must be SHA-pinned"
        )
        # The mint uses the preferred client-id input (with the one-release
        # legacy fallback), never the deprecated numeric app-id input.
        with_block = s.get("with", {})
        assert with_block.get("client-id") == (
            "${{ secrets.DEVKIT_UPGRADE_APP_CLIENT_ID || secrets.DEVKIT_UPGRADE_APP_ID }}"
        )
        assert "app-id" not in with_block
        # Least-privilege mint (zizmor github-app audit): the token must be
        # scoped to exactly the permissions the workflow exercises. With the
        # adoption issue gone (#1405) no issues permission remains.
        for perm in (
            "permission-contents",
            "permission-pull-requests",
            "permission-workflows",
        ):
            assert with_block.get(perm) == "write", f"missing {perm}: write"
        assert "permission-issues" not in with_block
    # The PR step authenticates gh with the minted token (not github.token),
    # otherwise the created PR would not trigger CI.
    pr_steps = [s for s in steps if "gh pr create" in str(s.get("run", ""))]
    assert pr_steps, "no PR-creating step found"
    for s in pr_steps:
        assert s.get("env", {}).get("GH_TOKEN") == (
            "${{ steps.app-token.outputs.token }}"
        )
    # Checkout persists the minted token so the push authenticates as the App.
    checkout_steps = [s for s in steps if "actions/checkout" in str(s.get("uses", ""))]
    assert checkout_steps, "no checkout step found"
    for s in checkout_steps:
        assert s.get("with", {}).get("token") == (
            "${{ steps.app-token.outputs.token }}"
        )


def test_legacy_numeric_app_id_still_accepted_with_warning() -> None:
    """The credential rename rides a minor (#1365): the legacy numeric
    DEVKIT_UPGRADE_APP_ID keeps working for one release — GitHub accepts either
    the App ID or the Client ID as the App JWT issuer, so the mint falls back to
    it — the preflight gates on *either* name being present, and the legacy path
    emits a deprecation warning. #1366 drops the fallback once the fleet has
    upgraded; a consumer that upgrades before its org grew the new secret is
    never bricked."""
    text = TEMPLATE.read_text(encoding="utf-8")
    # The fallback expression is the compatibility contract.
    assert (
        "secrets.DEVKIT_UPGRADE_APP_CLIENT_ID || secrets.DEVKIT_UPGRADE_APP_ID" in text
    )
    # The legacy path warns, pointing at the retirement issue.
    assert "::warning::" in text
    assert "1366" in text


def test_publishes_a_verified_commit_via_api_not_git_push() -> None:
    """The adoption commit reaching the remote must be GitHub-signed (#1308):
    the in-shell commit is a staging artifact, its tree is replayed through
    the git-data API (blobs -> tree -> commit -> ref) with the App token, so
    consumers' Signed-commits rulesets stay fully enforced — no bypasses."""
    text = TEMPLATE.read_text(encoding="utf-8")
    # The staging commit must never be pushed directly.
    assert "git push" not in text
    steps = _steps(text)
    publish_steps = [s for s in steps if "git/commits" in str(s.get("run", ""))]
    assert publish_steps, "no API publish step found"
    (publish,) = publish_steps
    run = str(publish["run"])
    # Full git-data flow with the minted App token.
    assert publish.get("env", {}).get("GH_TOKEN") == (
        "${{ steps.app-token.outputs.token }}"
    )
    assert "git/blobs" in run
    assert "git/trees" in run
    assert "git/refs" in run
    # Deletions are replayed as null-sha tree entries (the scaffold prunes
    # files; commit-action v0.3.x cannot express this, hence inline REST).
    assert "sha:null" in run.replace(" ", "")
    # Executable bits survive the replay (createCommitOnBranch would drop
    # them; the tree API carries an explicit mode per entry).
    assert "100755" in run
    # The branch ref is created on first use and force-updated within a train
    # (rc -> rc -> final reuse semantics).
    assert "force" in run


def test_bootstraps_installsh_and_commits_in_project_shell() -> None:
    """The upgrade runs install.sh --force --version and commits inside nix develop."""
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "raw.githubusercontent.com/vig-os/devkit/main/install.sh" in text
    assert "--force" in text and "--version" in text
    assert "nix develop -c git commit" in text
    # A nix installer action provides the `flake update vigos` leg.
    assert "install-nix-action" in text


def test_reset_excluded_paths() -> None:
    """DEVKIT_UPGRADE_EXCLUDE paths are reset to the base branch before commit."""
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "DEVKIT_UPGRADE_EXCLUDE" in text
    assert "git checkout --" in text


def test_no_adoption_issue_lifecycle() -> None:
    """The workflow manages no adoption issue at all (#1405).

    Adoption PRs are bot PRs like Renovate's: the PR is the traceable
    artifact and the changelog entry (#1404) links it. Dropping the issue
    removes the whole lifecycle — creation, the ``Refs:`` line, the
    ``Closes #`` body marker, the issues:write grant, and the #1347 no-diff
    cleanup step that existed only to garbage-collect stranded issues
    (`Closes #` never auto-closes on a dev-targeted PR anyway).
    """
    text = TEMPLATE.read_text(encoding="utf-8")
    # No issue commands, no Refs/Closes markers, no issue-numbered branch.
    assert "gh issue" not in text
    assert "Refs: #" not in text
    assert "Closes #" not in text
    # The branch is the guard-legal chore/<summary> shape, keyed on the train.
    assert 'BRANCH="chore/devkit-${SUFFIX}"' in text
    # The PR body points reviewers at the devkit release notes instead.
    assert "releases/tag/" in text


# ── security: no template injection (zizmor) ──────────────────────────────────


def test_no_run_block_interpolates_untrusted_input() -> None:
    """No ``run:`` interpolates a dispatch input or event field directly (#1279/#1287)."""
    offenders: list[str] = []
    for step in _steps(TEMPLATE.read_text(encoding="utf-8")):
        run = str(step.get("run", ""))
        if "${{ github.event" in run or "${{ inputs." in run:
            offenders.append(step.get("name", "<unnamed>"))
    assert not offenders, (
        f"run blocks interpolate untrusted input directly (route through env): {offenders}"
    )


# ── base-branch awareness (workflow model) ────────────────────────────────────


def test_gitflow_base_branch_is_dev(tmp_path: Path) -> None:
    """A gitflow scaffold checks out and targets `dev`."""
    text = _rendered(tmp_path)
    assert "ref: dev" in text
    assert "BASE: dev" in text


def test_trunk_base_branch_is_main(tmp_path: Path) -> None:
    """A trunk scaffold retargets the base branch dev -> main (#1205)."""
    text = _rendered(tmp_path, workflow="trunk")
    assert "ref: main" in text
    assert "BASE: main" in text
    assert "ref: dev" not in text
    assert "BASE: dev" not in text


# ── feature opt-out (#1284) ───────────────────────────────────────────────────


def test_disabling_feature_omits_the_workflow(tmp_path: Path) -> None:
    """DEVKIT_FEATURES_DISABLED=devkit-upgrade keeps the file out of the scaffold."""
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / ".vig-os").write_text(
        "DEVKIT_FEATURES_DISABLED=devkit-upgrade\n", encoding="utf-8"
    )
    proc = scaffold(tmp_path, seed=seed, name="disabled")
    assert proc.returncode == 0, proc.stderr
    assert not (tmp_path / "disabled" / REL).exists()
    # A non-disabled workflow still ships.
    assert (tmp_path / "disabled" / ".github/workflows/ci.yml").exists()


def test_valid_feature_group_default_ships_the_workflow(tmp_path: Path) -> None:
    """With no opt-out, the workflow is scaffolded."""
    tree = scaffold_tree(tmp_path)
    assert (tree / REL).is_file()
