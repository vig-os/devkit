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
  ``install.sh`` bootstrap and the ``nix develop`` commit — both run under a
  Nix that trusts the consumer flake's own ``nixConfig`` (#1599);
- no ``run:`` block interpolates a dispatch input or event field directly
  (zizmor template-injection: every such value is routed through ``env:``);
- the base branch is workflow-model aware (``dev`` gitflow / ``main`` trunk),
  realized by the scaffold-time ``render_workflow_model`` retarget;
- a failed run leaves an artifact in the repo (#1530): the ``report`` job files
  and re-uses ONE marker-tracked issue per repo and closes it on the next green
  run, with every leg best-effort so a missing App grant cannot break the
  upgrade path it reports on;
- the ``devkit-upgrade`` feature group (#1284) opts the whole file out.

Refs: #1296
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from tests.workflow_scaffold import (
    INIT_WORKSPACE,
    NIX_SETTINGS,
    WORKSPACE,
    cached_tree,
    needs_of,
    parse_nix_settings,
    run_text_of_job,
    scaffold,
    step_by_id,
    step_by_name,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = WORKSPACE / ".github" / "workflows" / "devkit-upgrade.yml"
REL = ".github/workflows/devkit-upgrade.yml"

# The failure-report contract (#1530): a body marker is the de-duplication key
# and the title carries no version, so a failure on a different target still
# finds the same open issue.
MARKER = "<!-- devkit-upgrade-failure -->"
TITLE = "chore(devkit): automated devkit upgrade is failing"


def _rendered(workflow: str | None = None) -> str:
    return (cached_tree(workflow) / REL).read_text(encoding="utf-8")


def _jobs(text: str | None = None) -> dict:
    return yaml.safe_load(text or TEMPLATE.read_text(encoding="utf-8"))["jobs"]


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
        # Every mint uses the preferred client-id input (with the one-release
        # legacy fallback), never the deprecated numeric app-id input.
        with_block = s.get("with", {})
        assert with_block.get("client-id") == (
            "${{ secrets.DEVKIT_UPGRADE_APP_CLIENT_ID || secrets.DEVKIT_UPGRADE_APP_ID }}"
        )
        assert "app-id" not in with_block
    # Least-privilege mint (zizmor github-app audit): the upgrade job's token is
    # scoped to exactly the permissions that job exercises. It must stay
    # issues-free — the report job (#1530) mints its own issues-scoped token, so
    # an installation without the Issues grant cannot break the upgrade path.
    upgrade_mint = step_by_id(_jobs(text)["upgrade"]["steps"], "app-token")
    with_block = upgrade_mint["with"]
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
    # The installer is fetched over the network; which ref it comes from is
    # pinned by the test below.
    assert "raw.githubusercontent.com/vig-os/devkit/" in text
    assert "install.sh" in text
    assert "--force" in text and "--version" in text
    assert "nix develop -c git commit" in text
    # A nix installer action provides the `flake update vigos` leg.
    assert "install-nix-action" in text


def test_install_nix_carries_the_toolchain_nix_settings() -> None:
    """The installer step must trust the consumer flake's own nixConfig (#1599).

    ``install-nix-action`` with only ``experimental-features`` leaves the
    runner's Nix untrusting: a consumer ``flake.nix`` that declares
    ``nixConfig.extra-substituters`` gets

        warning: ignoring untrusted flake configuration setting
        'extra-substituters'. Pass '--accept-flake-config' to trust it

    on BOTH Nix legs of this job (the ``nix flake update vigos`` inside
    install.sh and the ``nix develop -c git commit`` after it), and the
    dev-shell resolves against ``cache.nixos.org`` alone.

    ``setup-devkit-toolchain`` — same scaffold payload, same runner class,
    same consumer flake — has always passed the full set. Pin them to ONE
    constant so the third copy cannot drift from the first two.

    Not a regression of #773: that removed ``accept-flake-config`` from the
    *image's baked* ``nix.conf``, where it would trust any foreign flake a
    container ran. Here it is a per-runner setting in a job that evaluates the
    consumer's own repo flake and nothing else.
    """
    step = step_by_name(_steps(TEMPLATE.read_text(encoding="utf-8")), "Install Nix")
    assert parse_nix_settings(step["with"]["extra_nix_config"]) == NIX_SETTINGS


def test_installer_is_fetched_from_the_target_release_tag() -> None:
    """The installer comes from ``$TARGET``'s tag, never ``main`` tip (#1532).

    Fetching ``install.sh`` from ``main`` while installing a pinned ``$TARGET``
    pairs an installer with a scaffold payload from a different ref — an
    untested combination, and precisely the one every *scheduled* consumer run
    gets whenever ``main`` is ahead of the latest release. It also means any
    push to devkit ``main`` immediately changes code that executes with
    ``contents: write`` in every consumer repo, with no review gate between the
    commit and the fleet. Pinning the fetch to the target tag closes both:
    installer and payload move together, and only a published release can
    change what runs.

    No ``main`` fallback: the resolve step accepts only a strict
    ``X.Y.Z[-prerelease]`` semver, and every devkit tag of that shape carries a
    root-level ``install.sh``.
    """
    text = TEMPLATE.read_text(encoding="utf-8")
    step = step_by_id(_jobs(text)["upgrade"]["steps"], "upgrade")
    run = str(step["run"])
    # Double-quoted: the URL now interpolates $TARGET.
    assert (
        'curl -sSfL "https://raw.githubusercontent.com/vig-os/devkit'
        '/refs/tags/${TARGET}/install.sh"' in run
    )
    # TARGET is already env-routed into this step — no new plumbing.
    assert step["env"]["TARGET"] == "${{ steps.resolve.outputs.target }}"
    # No main-tip installer fetch survives anywhere in the template.
    assert "devkit/main/install.sh" not in text


def test_upgrade_step_captures_the_flake_bump_report() -> None:
    """The install.sh output's ``flake-bump:`` line becomes a step output (#1497).

    install.sh prints exactly one ``flake-bump:`` line per run (advanced /
    skipped-with-reason / no input recognized). A silent decline was the whole
    bug — the workflow must capture the line so the adoption PR can carry it.
    """
    job = _jobs()["upgrade"]
    step = next(
        s
        for s in job["steps"]
        if str(s.get("name", "")).startswith("Run the devkit upgrade")
    )
    assert step.get("id") == "upgrade"
    run = str(step["run"])
    assert "tee" in run, "install.sh output must be captured, not discarded"
    assert "flake-bump:" in run
    assert "flake-bump=" in run and "GITHUB_OUTPUT" in run


def test_pr_body_carries_the_flake_bump_report_via_env() -> None:
    """The adoption PR body includes the flake-bump outcome, env-routed (#1497).

    Routed through ``env:`` (never ``${{ }}`` inside ``run:``) per the
    template-injection doctrine pinned below.
    """
    job = _jobs()["upgrade"]
    step = next(s for s in job["steps"] if "adoption PR" in str(s.get("name", "")))
    assert step["env"]["FLAKE_BUMP"] == "${{ steps.upgrade.outputs.flake-bump }}"
    assert "$FLAKE_BUMP" in str(step["run"])


def test_reset_excluded_paths() -> None:
    """DEVKIT_UPGRADE_EXCLUDE paths are reset to the base branch before commit."""
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "DEVKIT_UPGRADE_EXCLUDE" in text
    assert "git checkout --" in text


def test_no_adoption_issue_lifecycle() -> None:
    """The upgrade job manages no adoption issue at all (#1405).

    Adoption PRs are bot PRs like Renovate's: the PR is the traceable
    artifact and the changelog entry (#1404) links it. Dropping the issue
    removes the whole lifecycle — creation, the ``Refs:`` line, the
    ``Closes #`` body marker, the issues:write grant, and the #1347 no-diff
    cleanup step that existed only to garbage-collect stranded issues
    (`Closes #` never auto-closes on a dev-targeted PR anyway).

    The failure tracking issue (#1530) is a different lifecycle in a different
    job — opened only on failure, one per repo, closed by the next green run —
    so the no-adoption-issue rule is asserted on the ``upgrade`` job alone.
    """
    text = TEMPLATE.read_text(encoding="utf-8")
    # No issue commands on the adoption path, no Refs/Closes markers anywhere.
    assert "gh issue" not in run_text_of_job(_jobs(text)["upgrade"])
    assert "Refs: #" not in text
    assert "Closes #" not in text
    # The branch is the guard-legal chore/<summary> shape, keyed on the train.
    assert 'BRANCH="chore/devkit-${SUFFIX}"' in text
    # The PR body points reviewers at the devkit release notes instead.
    assert "releases/tag/" in text


# ── failure reporting (#1530) ─────────────────────────────────────────────────


def _report_job(text: str | None = None) -> dict:
    return _jobs(text)["report"]


def test_report_is_a_separate_result_gated_job() -> None:
    """Reporting lives in its own ``needs:``-gated job, not a late step (#1530).

    A step-level ``if: failure()`` never runs once the job itself is aborted —
    the 30-minute timeout, a lost runner — which is one of the silent-failure
    modes this closes. A ``needs`` job keyed on ``needs.upgrade.result`` covers
    those, covers a resolve-step failure (malformed pin / missing
    ``DEVKIT_VERSION``) and reports nothing on a cancelled run.
    """
    jobs = _jobs()
    report = _report_job()
    assert needs_of(report) == ["upgrade"]
    cond = str(report["if"])
    assert "needs.upgrade.result == 'failure'" in cond
    assert "needs.upgrade.result == 'success'" in cond
    # Without a status-check function in the expression, Actions applies an
    # implicit success() to a job-level `if` — the report job would be skipped
    # on exactly the failed runs it exists for.
    assert "!cancelled()" in cond
    # Reading this run's own step conclusions is all the default token needs.
    assert report["permissions"] == {"actions": "read"}
    assert "timeout-minutes" in report
    # Not a step in the upgrade job: nothing there touches issues.
    assert "gh issue" not in run_text_of_job(jobs["upgrade"])


def test_report_mint_is_issues_scoped_and_best_effort() -> None:
    """The issues grant is minted separately and may fail harmlessly (#1530).

    ``create-github-app-token`` fails the mint when it requests a permission the
    installation lacks, and the devkit-upgrade App has needed no Issues grant
    since #1405. Requesting it on the upgrade job's mint would therefore turn a
    green upgrade red on every org that has not re-granted it, so the report
    mints its own token and every leg is ``continue-on-error``.
    """
    report = _report_job()
    mint = step_by_id(report["steps"], "issues-token")
    assert re.search(r"create-github-app-token@[0-9a-f]{40}", mint["uses"])
    with_block = mint["with"]
    assert with_block["permission-issues"] == "write"
    # Least privilege: the report writes issues and nothing else.
    assert [k for k in with_block if k.startswith("permission-")] == [
        "permission-issues"
    ]
    for step in report["steps"]:
        assert step.get("continue-on-error") is True, (
            f"report step {step.get('name')!r} may not fail the run"
        )


def test_failure_leg_files_or_reuses_one_marker_tracked_issue() -> None:
    """At most one open tracking issue per repo; repeats comment on it (#1530)."""
    step = step_by_name(_report_job()["steps"], "File or update")
    assert step["if"] == "needs.upgrade.result == 'failure'"
    run = str(step["run"])
    # De-duplication keys on a body marker (exact, and immediately visible in
    # the REST issue list — unlike the eventually-consistent search index).
    assert MARKER in run
    assert "gh issue list" in run
    assert run.index("gh issue list") < run.index("gh issue create"), (
        "the lookup must precede creation, else a new issue is filed weekly"
    )
    assert "gh issue comment" in run
    # The title is version-free, so a failure on a different target finds the
    # same issue and no title ever goes stale.
    assert f"TITLE='{TITLE}'" in run


def test_failure_leg_body_carries_run_phase_and_versions() -> None:
    """The issue names the run, the failing step and current vs target (#1530)."""
    step = step_by_name(_report_job()["steps"], "File or update")
    env = step["env"]
    assert env["GH_TOKEN"] == "${{ steps.issues-token.outputs.token }}"
    # No checkout in this job, so gh resolves the repo from the environment.
    assert env["GH_REPO"] == "${{ github.repository }}"
    assert "${{ github.run_id }}" in env["RUN_URL"]
    # Versions come from the resolve step's outputs, promoted to job outputs.
    assert env["CURRENT"] == "${{ needs.upgrade.outputs.current }}"
    assert env["TARGET"] == "${{ needs.upgrade.outputs.target }}"
    run = str(step["run"])
    for var in ("$RUN_URL", "$FAILED", "${CURRENT:-", "${TARGET:-"):
        assert var in run, f"the issue body must report {var}"
    # The failing step is read off this run's own job records with the default
    # token — no per-step instrumentation to keep in sync with the steps above.
    assert env["RUN_TOKEN"] == "${{ github.token }}"
    assert 'GH_TOKEN="$RUN_TOKEN" gh api' in run
    assert "/actions/runs/${GITHUB_RUN_ID}/jobs" in run


def test_failure_leg_degrades_when_the_app_lacks_the_issues_grant() -> None:
    """A missing grant yields a warning, never a failed step (#1530)."""
    run = str(step_by_name(_report_job()["steps"], "File or update")["run"])
    assert '[ -z "${GH_TOKEN}" ]' in run
    assert "::warning::" in run


def test_success_leg_closes_the_tracking_issue() -> None:
    """A fully green run self-cleans the alert with a link to that run (#1530)."""
    step = step_by_name(_report_job()["steps"], "Close the upgrade-failure issue")
    assert step["if"] == "needs.upgrade.result == 'success'"
    run = str(step["run"])
    assert MARKER in run
    assert run.index("gh issue list") < run.index("gh issue close")
    assert "$RUN_URL" in run
    assert step["env"]["GH_TOKEN"] == "${{ steps.issues-token.outputs.token }}"


def test_resolve_publishes_the_versions_the_report_names() -> None:
    """``current`` is a job output emitted before any later failure (#1530).

    A resolve failure on the target (malformed dispatch input, unreachable
    release query) must still report the pin the repo is stuck on, so the
    ``current`` output is written as soon as ``.vig-os`` is read.
    """
    upgrade = _jobs()["upgrade"]
    assert upgrade["outputs"]["current"] == "${{ steps.resolve.outputs.current }}"
    assert upgrade["outputs"]["target"] == "${{ steps.resolve.outputs.target }}"
    run = str(step_by_id(upgrade["steps"], "resolve")["run"])
    assert run.index('echo "current=') < run.index("malformed target version")


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


def test_gitflow_base_branch_is_dev() -> None:
    """A gitflow scaffold checks out and targets `dev`."""
    text = _rendered()
    assert "ref: dev" in text
    assert "BASE: dev" in text


def test_trunk_base_branch_is_main() -> None:
    """A trunk scaffold retargets the base branch dev -> main (#1205)."""
    text = _rendered(workflow="trunk")
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


def test_valid_feature_group_default_ships_the_workflow() -> None:
    """With no opt-out, the workflow is scaffolded."""
    tree = cached_tree(None)
    assert (tree / REL).is_file()
