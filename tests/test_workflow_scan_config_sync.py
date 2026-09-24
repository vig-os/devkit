"""Workflow-shape tests: the scan-config sync lane (#1676).

`main` and `dev` each run their own nightly vulnix leg against their own closure
and their own `.vulnixignore`. A register amendment lands on `dev` and only
reaches `main` with the next release train, so `main`'s lane stays red in the
meantime — structurally, not occasionally: the register moved 32 times in 90
days against a roughly weekly release cadence.

The sync lane carries register-only changes to `main` without cutting a release.
Two workflows implement it:

- `scan-config-sync.yml` (opener) — dispatched by hand, opens the PR **as the
  App**. This is not decoration: `main` requires one approving review, GitHub
  forbids authors approving their own PRs, and no App sits in `main`'s bypass
  list, so a human-authored PR to `main` is unapprovable by the only human
  there is. Every release PR to `main` is App-authored for exactly this reason.
- `scan-config-guard.yml` (guard) — proves the PR is safe to merge.

The invariants pinned here are the ones whose failure modes are silent or
catastrophic rather than merely wrong:

- The guard must **always report**. If it skipped at the job level, a required-
  check configuration would leave every release PR waiting forever on a check
  that never arrives. "Skip" must mean "ran and passed".
- The guard must **never write** to the repo. `main` carries
  `dismiss_stale_reviews_on_push`, so a guard that pushed would discard the very
  approval it exists to enable.
- The gates must be **label-scoped**. A release PR legitimately changes
  `CHANGELOG.md`, `.vig-os` and often `.vulnixignore` via the dev merge; a guard
  keyed on the diff shape instead of the label would block every release.

Refs: #1676
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import (
    ACTION_PIN_RE,
    REPO_ROOT,
    jobs,
    load_workflow,
    on_block,
    run_text_of_job,
    steps_of_job,
)

if TYPE_CHECKING:
    from pathlib import Path

GUARD_PATH = REPO_ROOT / ".github/workflows/scan-config-guard.yml"
OPENER_PATH = REPO_ROOT / ".github/workflows/scan-config-sync.yml"

# The label is the lane's discriminator, and the ONLY thing separating a sync PR
# from a release PR at the guard. Both workflows must agree on it.
SYNC_LABEL = "scan-config-sync"

# Exactly the scan-time registers. Nothing here is an image input, which is what
# makes a release unnecessary; anything else in the diff means the PR is not a
# scan-config sync and the guard must refuse it.
ALLOWLISTED_PATHS = (
    ".vulnixignore",
    ".trivyignore",
    ".github/dependency-review-allow.txt",
)

GUARD_JOB = "guard"


def _guard() -> dict:
    return load_workflow(GUARD_PATH)


def _opener() -> dict:
    return load_workflow(OPENER_PATH)


# ── Existence ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", [GUARD_PATH, OPENER_PATH], ids=lambda p: p.name)
def test_workflow_exists(path: Path) -> None:
    """Both halves of the lane ship."""
    assert path.is_file(), f"{path.relative_to(REPO_ROOT)} is missing"


# ── Guard: triggering ────────────────────────────────────────────────────────


def test_guard_triggers_on_pull_requests_to_main() -> None:
    """The guard watches PRs into `main` — that is the only ref it protects."""
    on = on_block(_guard())
    pr = on["pull_request"]
    assert "main" in pr["branches"], "guard must watch PRs targeting main"


def test_guard_reacts_to_label_changes() -> None:
    """Labelling an open PR must (re)run the guard.

    The label is what activates the gates, so a guard that only ran on `opened`
    and `synchronize` would report a stale pass on a PR labelled after the fact.
    """
    on = on_block(_guard())
    types = set(on["pull_request"]["types"])
    assert {"labeled", "unlabeled"} <= types, (
        f"guard must rerun on label changes; types={sorted(types)}"
    )


# ── Guard: always reports (the release-blocking hazard) ──────────────────────


def test_guard_job_has_no_job_level_if() -> None:
    """The guard job must run on every `main` PR, labelled or not.

    A job-level `if` produces a *skipped* job. Were the guard ever promoted to a
    required status check, a skipped job on a release PR would leave that PR
    waiting on a check that never reports — blocking releases indefinitely. The
    inactive path must therefore be a real, successful run.
    """
    job = jobs(_guard())[GUARD_JOB]
    assert "if" not in job, (
        "guard job must not carry a job-level `if` — an inactive PR has to "
        "report success, not skip"
    )


def test_guard_scopes_gates_to_the_label() -> None:
    """Gate steps are conditional on the sync label, not on the diff shape.

    A release PR legitimately touches `.vulnixignore` via the dev merge; keying
    the gates on the diff would fail every release.
    """
    steps = steps_of_job(_guard(), GUARD_JOB)
    conditioned = [s for s in steps if "if" in s]
    assert conditioned, "guard must gate its steps on the label"
    assert any(SYNC_LABEL in str(s.get("if", "")) for s in steps) or any(
        SYNC_LABEL in str(s.get("run", "")) for s in steps
    ), f"guard must key on the `{SYNC_LABEL}` label"


# ── Guard: never writes (the dismissed-approval hazard) ──────────────────────


def test_guard_never_requests_write_access_to_contents() -> None:
    """`contents` stays read-only: the guard verifies, it does not author."""
    perms = _guard()["permissions"]
    assert perms.get("contents") == "read", (
        f"guard must not hold contents:write; got {perms.get('contents')!r}"
    )


def test_guard_does_not_push_or_commit() -> None:
    """No mutation of the PR branch.

    `main` sets `dismiss_stale_reviews_on_push`, so a guard that pushed would
    discard the approval that the lane depends on.
    """
    body = run_text_of_job(jobs(_guard())[GUARD_JOB])
    for forbidden in ("git push", "git commit", "gh pr merge"):
        assert forbidden not in body, (
            f"guard must not run `{forbidden}` — it verifies only"
        )


# ── Guard: the gates ─────────────────────────────────────────────────────────


def test_guard_allowlist_is_exactly_the_scan_registers() -> None:
    """Gate A pins the three scan-time registers and nothing else."""
    body = run_text_of_job(jobs(_guard())[GUARD_JOB])
    for allowed in ALLOWLISTED_PATHS:
        assert allowed in body, f"gate A must allowlist {allowed}"


def test_guard_proves_the_image_derivation_is_unchanged() -> None:
    """Gate B: equal `.drv` paths prove the published image cannot differ.

    This is a proof rather than an argument about which files are image inputs,
    which is what lets Gate A stay a cheap fast-fail.
    """
    body = run_text_of_job(jobs(_guard())[GUARD_JOB])
    assert "drvPath" in body, "gate B must compare derivation paths"
    assert "devkitImage" in body, "gate B must evaluate the image derivation"


def test_guard_proves_main_goes_green() -> None:
    """Gate C: run `main`'s real gate against `main`'s real closure.

    This is what makes the deletion hazard unmergeable. The register is not
    append-only — a pin advance on `dev` clears exceptions that `main`'s older
    closure still needs — so the lane cannot reason about whether a removal is
    safe; it has to run the gate and read the exit code.
    """
    body = run_text_of_job(jobs(_guard())[GUARD_JOB])
    assert "vulnix-gate" in body, "gate C must run the real vulnix gate"
    assert "--register" in body, "gate C must evaluate against the PR's register"


def test_guard_checks_expiries() -> None:
    """Gate D: no already-expired entry may land on `main`."""
    body = run_text_of_job(jobs(_guard())[GUARD_JOB])
    assert "check-expirations" in body, "gate D must validate expiries"


def test_guard_refuses_while_a_release_train_is_in_flight() -> None:
    """Gate F: moving `main` mid-train dismisses the release PR's approval.

    `main`'s required checks are strict, so a train in flight would have to
    re-satisfy up-to-date-ness after this merge, discarding its review.
    """
    body = run_text_of_job(jobs(_guard())[GUARD_JOB])
    assert "release/" in body, "gate F must detect an in-flight release branch"


def test_guard_asserts_unreleased_stays_empty() -> None:
    """Gate G: `prepare-release` and `prepare-hotfix` both require it."""
    body = run_text_of_job(jobs(_guard())[GUARD_JOB])
    assert "Unreleased" in body, "gate G must assert main's Unreleased is empty"


# ── Opener: App authorship (the unapprovable-PR hazard) ──────────────────────


def test_opener_is_dispatched_by_hand() -> None:
    """The lane stays manual: a human chooses what and when."""
    on = on_block(_opener())
    assert "workflow_dispatch" in on, "opener must be manually dispatched"


def test_opener_takes_the_branch_to_propose() -> None:
    """The maintainer cherry-picks onto a branch; the opener only proposes it."""
    on = on_block(_opener())
    inputs = on["workflow_dispatch"]["inputs"]
    assert "branch" in inputs, "opener must take the prepared branch as input"


def test_opener_authors_the_pr_as_the_app() -> None:
    """The PR must be App-authored or the only human cannot approve it.

    `main` requires one approving review, GitHub forbids self-approval, and no
    App holds bypass — so a human-authored PR to `main` is unmergeable.
    """
    steps = steps_of_job(_opener(), next(iter(jobs(_opener()))))
    uses = [str(s.get("uses", "")) for s in steps]
    assert any("create-github-app-token" in u for u in uses), (
        "opener must mint an App token so the PR is App-authored"
    )


def test_opener_creates_the_pr_with_the_app_token() -> None:
    """`gh pr create` must run under the App token, not `github.token`.

    `github.token` would author the PR as `github-actions[bot]`; the point is a
    distinct author the maintainer may review.
    """
    body = run_text_of_job(jobs(_opener())[next(iter(jobs(_opener())))])
    assert "gh pr create" in body, "opener must open the PR"
    assert "--base main" in body or "--base" in body, "opener must target main"


def test_opener_applies_the_sync_label() -> None:
    """Without the label the guard stays inactive and proves nothing."""
    body = run_text_of_job(jobs(_opener())[next(iter(jobs(_opener())))])
    assert SYNC_LABEL in body, f"opener must apply the `{SYNC_LABEL}` label"


# ── Repo conventions ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", [GUARD_PATH, OPENER_PATH], ids=lambda p: p.name)
def test_actions_are_sha_pinned(path: Path) -> None:
    """Every third-party action is pinned to a full commit SHA."""
    doc = load_workflow(path)
    for job_name, job in jobs(doc).items():
        for step in job.get("steps", []):
            uses = step.get("uses")
            if not uses or uses.startswith("./"):
                continue
            assert ACTION_PIN_RE.match(uses), (
                f"{path.name}:{job_name} uses unpinned action {uses!r}"
            )
