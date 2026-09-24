"""Workflow-shape tests: the release-neutral lane (#1676).

`main` can only be written by a release — `prepare-release` and `prepare-hotfix`
are the only lanes, and both cut a tag, publish a GHCR image and trigger
adoption PRs across every consumer. But plenty of changes belong on `main` while
changing **nothing a consumer receives**: devkit's own `.github/workflows/**`,
`tests/**`, most of `docs/**`, the scan-time registers.

The release-neutral lane merges those without a release, admitted only when a
machine proof shows no published artifact changes. Two workflows implement it:

- `release-neutral-open.yml` — dispatched by hand, opens the PR **as the App**.
  Not decoration: `main` requires one approving review, GitHub forbids authors
  approving their own PRs, and no App sits in `main`'s bypass list, so a
  human-authored PR to `main` is unapprovable by the only human there is.
- `release-neutral-guard.yml` — proves release-neutrality.

THE CONTRACT IS GATE 2, derivation identity. Equal `.drv` paths mean the
published artifacts *cannot* differ, whatever the diff touched — a proof rather
than an argument about which files happen to be inputs. It is deliberately not a
path allowlist: an allowlist encodes a guess about what is published and would
need extending for every new kind of release-neutral change.

The comparison is NORMALIZED, and that is not a softening of the contract.
`CHANGELOG.md` is mirrored into `assets/workspace/.devcontainer/CHANGELOG.md`,
which is baked into the image, so a changelog entry *alone* moves
`devkitImage`'s derivation. Measured on this branch against `main` at
2026-09-24:

    the raw tree (it carries a CHANGELOG.md entry)
        -> devkitImage d5gf56y0... != main's d6ikbz96...      REFUSED
    the same tree, changelog and mirror reverted to main's copy
        -> devkitImage d6ikbz96... == main's d6ikbz96...      ADMITTED

So gate 2 reverts those two files to the base's copy *before* evaluating: both
sides then share identical changelog content and any difference that survives is
genuinely non-changelog. Without that step no change carrying a release note
could ever ride the lane, which would defeat it.

This rests on a project decision that supersedes #590's invariant: `main` MAY
carry changes that have landed but are not yet shipped, and its `## Unreleased`
section describes them. `sync-main-to-dev.yml` triggers on `push: [main]`, so
the entry reaches `dev` automatically and the next train freezes it normally.
Two consequences pinned below: gate 1 refuses only `.vig-os`, and the old
"`main`'s `## Unreleased` is empty" gate is gone rather than merely relaxed.

The other invariants pinned here are the ones whose failure modes are silent or
catastrophic rather than merely wrong:

- The guard must **always report**. A job-level `if` yields a skipped job, and
  were the guard ever promoted to a required check, a skipped job on a release
  PR would leave that PR waiting forever. "Skip" must mean "ran and passed".
- The guard must **never write**. `main` carries
  `dismiss_stale_reviews_on_push`, so a guard that pushed would discard the very
  approval it exists to enable.
- The gates must be **label-scoped**. A release PR legitimately changes
  `CHANGELOG.md`, `.vig-os` and the scaffold; a guard keyed on the diff shape
  instead of the label would block every release.

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
    step_by_name,
    steps_of_job,
)

if TYPE_CHECKING:
    from pathlib import Path

GUARD_PATH = REPO_ROOT / ".github/workflows/release-neutral-guard.yml"
OPENER_PATH = REPO_ROOT / ".github/workflows/release-neutral-open.yml"

# The lane's discriminator, and the only thing separating a lane PR from a
# release PR at the guard. Both workflows must agree on it.
LANE_LABEL = "release-neutral"

# Files that ARE release content: changing them is releasing, not a
# release-neutral change. Note this is a *forbidden* set, not an allowlist —
# everything else is admitted unless a published derivation moves (gate 2).
#
# `.vig-os` is the whole set: it carries DEVKIT_VERSION, and editing that IS
# cutting a release. `CHANGELOG.md` deliberately is NOT here — see
# `test_gate_1_admits_changelog_edits`.
RELEASE_CONTENT = (".vig-os",)

# The two copies of the changelog, kept in step by a pre-commit hook. Gate 2
# normalizes both before comparing derivations.
CHANGELOG_PATHS = (
    "CHANGELOG.md",
    "assets/workspace/.devcontainer/CHANGELOG.md",
)

# Everything a consumer can receive: the image for devcontainer consumers, the
# dev shell for `direnv`/`bare` ones, and the closure the scanners read.
PUBLISHED_ATTRS = (
    "devShells",
    "devkitImage",
    "devkitImageEnv",
)

GUARD_JOB = "guard"


def _guard() -> dict:
    return load_workflow(GUARD_PATH)


def _opener() -> dict:
    return load_workflow(OPENER_PATH)


def _guard_body() -> str:
    return run_text_of_job(jobs(_guard())[GUARD_JOB])


def _opener_body() -> str:
    doc = _opener()
    return run_text_of_job(jobs(doc)[next(iter(jobs(doc)))])


# ── Existence ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", [GUARD_PATH, OPENER_PATH], ids=lambda p: p.name)
def test_workflow_exists(path: Path) -> None:
    """Both halves of the lane ship."""
    assert path.is_file(), f"{path.relative_to(REPO_ROOT)} is missing"


# ── Guard: triggering ────────────────────────────────────────────────────────


def test_guard_triggers_on_pull_requests_to_main() -> None:
    """`main` is the only ref this lane writes, so the only one it guards."""
    pr = on_block(_guard())["pull_request"]
    assert "main" in pr["branches"], "guard must watch PRs targeting main"


def test_guard_reacts_to_label_changes() -> None:
    """Labelling an open PR must (re)run the guard.

    The label activates the gates, so a guard that only ran on `opened` and
    `synchronize` would report a stale pass on a PR labelled afterwards.
    """
    types = set(on_block(_guard())["pull_request"]["types"])
    assert {"labeled", "unlabeled"} <= types, (
        f"guard must rerun on label changes; types={sorted(types)}"
    )


# ── Guard: always reports (the release-blocking hazard) ──────────────────────


def test_guard_job_has_no_job_level_if() -> None:
    """The guard job must run on every `main` PR, labelled or not.

    A job-level `if` produces a *skipped* job. Were the guard ever promoted to a
    required status check, a skipped job on a release PR would leave that PR
    waiting on a check that never reports — blocking releases indefinitely.
    """
    assert "if" not in jobs(_guard())[GUARD_JOB], (
        "guard job must not carry a job-level `if` — an inactive PR has to "
        "report success, not skip"
    )


def test_guard_scopes_gates_to_the_label() -> None:
    """Gates are conditional on the lane label, never on the diff shape.

    A release PR legitimately touches `CHANGELOG.md`, `.vig-os` and the
    scaffold; keying the gates on the diff would fail every release.
    """
    steps = steps_of_job(_guard(), GUARD_JOB)
    assert [s for s in steps if "if" in s], "guard must gate its steps"
    assert any(LANE_LABEL in str(s.get("if", "")) for s in steps) or any(
        LANE_LABEL in str(s.get("run", "")) for s in steps
    ), f"guard must key on the `{LANE_LABEL}` label"


# ── Guard: never writes (the dismissed-approval hazard) ──────────────────────


def test_guard_never_requests_write_access_to_contents() -> None:
    """`contents` stays read-only: the guard verifies, it does not author.

    Checked at the job level, where the effective grant is made — the
    workflow-level block is `{}` and would pass this vacuously.
    """
    doc = _guard()
    assert doc["permissions"] == {}, "workflow-level permissions must default-deny"
    perms = jobs(doc)[GUARD_JOB]["permissions"]
    assert perms.get("contents") == "read", (
        f"guard must not hold contents:write; got {perms.get('contents')!r}"
    )


def test_guard_does_not_push_or_commit() -> None:
    """No mutation of the PR branch.

    `main` sets `dismiss_stale_reviews_on_push`, so a guard that pushed would
    discard the approval the lane depends on.
    """
    body = _guard_body()
    for forbidden in ("git push", "git commit", "gh pr merge"):
        assert forbidden not in body, (
            f"guard must not run `{forbidden}` — it verifies only"
        )


# ── Guard: the gates ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", RELEASE_CONTENT)
def test_gate_1_refuses_release_content(path: str) -> None:
    """Gate 1 names the files whose change *is* a release."""
    assert path in _guard_body(), f"gate 1 must refuse changes to {path}"


@pytest.mark.parametrize("path", CHANGELOG_PATHS)
def test_gate_1_admits_changelog_edits(path: str) -> None:
    """Gate 1 must NOT refuse the changelog.

    `main` may now carry landed-but-unshipped changes and describe them under
    `## Unreleased`, so a release note no longer disqualifies a change from the
    lane. Gate 2's normalization is what keeps that safe: the changelog text is
    equalized before the derivations are compared, so a changelog entry proves
    nothing about neutrality either way.

    Asserted against the gate-1 step alone, not the job body — gate 2 and the
    verdict both name the changelog for legitimate reasons.
    """
    gate_1 = str(
        step_by_name(steps_of_job(_guard(), GUARD_JOB), "gate 1").get("run", "")
    )
    assert path not in gate_1, (
        f"gate 1 must no longer treat {path} as release content — `main` may "
        "carry a changelog entry for a change it has landed but not shipped"
    )


@pytest.mark.parametrize("attr", PUBLISHED_ATTRS)
def test_gate_2_compares_every_published_derivation(attr: str) -> None:
    """Gate 2 covers both consumption modes, not just the image.

    A `direnv`/`bare` consumer never pulls the image — it evaluates
    `devShells.default` from the flake — so an image-only comparison would wave
    through a change that alters every such consumer's toolchain.
    """
    assert attr in _guard_body(), f"gate 2 must compare {attr}"


def test_gate_2_compares_derivation_paths() -> None:
    """Gate 2 is a derivation-identity proof, not a heuristic."""
    assert "drvPath" in _guard_body(), "gate 2 must compare derivation paths"


def test_gate_2_normalizes_the_changelog_before_comparing() -> None:
    """Gate 2 equalizes the changelog on both sides, then compares.

    The changelog is baked into the image, so without this an entry alone moves
    `devkitImage`'s derivation (measured: `d5gf56y0…` vs `main`'s `d6ikbz96…`)
    and NO change carrying a release note could ever ride the lane. Reverting
    both copies to the base's makes the surviving difference — if any —
    genuinely non-changelog.

    The ordering is the whole point: the revert must precede the head-side
    evaluation, or it normalizes nothing.
    """
    gate_2 = str(
        step_by_name(steps_of_job(_guard(), GUARD_JOB), "gate 2").get("run", "")
    )
    revert = gate_2.find("git checkout")
    assert revert != -1, "gate 2 must revert the changelog before evaluating"
    for path in CHANGELOG_PATHS:
        assert path in gate_2[:revert] or path in gate_2[revert : revert + 400], (
            f"gate 2 must normalize {path} — both copies, or the mirror still "
            "moves the image derivation"
        )
    first_eval = gate_2.find("drvPath")
    assert first_eval != -1
    assert revert < first_eval, (
        "the changelog revert must come BEFORE the first drvPath evaluation; "
        "normalizing afterwards normalizes nothing"
    )


def test_gate_2_restores_the_head_tree_after_normalizing() -> None:
    """The normalization is scoped to the comparison, not left behind.

    Everything after gate 2 — the vulnix extra's diff, the verdict's file
    list — reads the real head tree. A gate that left `main`'s changelog in the
    worktree would make the verdict under-report what is being carried.
    """
    gate_2 = str(
        step_by_name(steps_of_job(_guard(), GUARD_JOB), "gate 2").get("run", "")
    )
    assert "git checkout HEAD --" in gate_2 or "git restore" in gate_2, (
        "gate 2 must restore the head tree's changelog after normalizing"
    )


def test_gate_3_refuses_scaffold_changes() -> None:
    """Gate 3: `assets/` is what consumers scaffold.

    Formally subsumed by gate 2 (the scaffold is copied into the image), but
    kept for diagnostics: naming the offending file beats two unequal hashes.
    """
    assert "assets/" in _guard_body(), "gate 3 must check the scaffold tree"


def test_no_gate_asserts_main_unreleased_is_empty() -> None:
    """The old gate 4 is GONE, not relaxed.

    It asserted `main`'s `## Unreleased` was empty, which #590 made true by
    construction. That invariant is superseded: `main` may now carry landed but
    unshipped changes, and `## Unreleased` is exactly where they are described.
    A guard still enforcing emptiness would refuse the model it is meant to
    serve, so the check is deleted rather than softened.

    (`prepare-hotfix` still refuses a non-empty section — phase 1 of #1676, a
    separate change. That is the hotfix lane's business, not this guard's.)
    """
    steps = steps_of_job(_guard(), GUARD_JOB)
    assert not [s for s in steps if "gate 4" in str(s.get("name", "")).lower()], (
        "gate 4 must be removed, not renumbered"
    )
    assert "/^## Unreleased/" not in _guard_body(), (
        "the guard must not extract main's Unreleased section — the emptiness "
        "invariant is superseded"
    )


def test_gate_5_refuses_while_a_release_train_is_in_flight() -> None:
    """Gate 5: moving `main` mid-train dismisses the release PR's approval.

    `main`'s required checks are strict, so the train would have to re-satisfy
    up-to-date-ness after this merge, discarding its review.
    """
    assert "release/" in _guard_body(), "gate 5 must detect an in-flight train"


def test_gate_6_reports_changelog_drift_explicitly() -> None:
    """The verdict must name the changelog difference it tolerated.

    Gate 2 normalizes the changelog away before comparing, so a release note
    passes the contract silently. Silently is the failure mode: the reviewer
    would have no way to tell a workflow-only carry from one that also writes
    `main`'s `## Unreleased`. The verdict therefore says so explicitly,
    conditioned on the diff actually touching the changelog.
    """
    verdict = str(
        step_by_name(steps_of_job(_guard(), GUARD_JOB), "verdict").get("run", "")
    )
    assert "-- CHANGELOG.md" in verdict, (
        "the verdict must test whether the diff touches the changelog, rather "
        "than reporting neutrality unconditionally"
    )
    lowered = verdict.lower()
    assert "changelog" in lowered, "the verdict must speak of the changelog"
    assert "normaliz" in lowered or "equaliz" in lowered, (
        "the verdict must say the comparison was normalized, so the reader "
        "knows the changelog was excluded from the proof rather than proved "
        "identical"
    )


# ── Opener: App authorship (the unapprovable-PR hazard) ──────────────────────


def test_opener_is_dispatched_by_hand() -> None:
    """The lane stays manual: a human chooses what and when."""
    assert "workflow_dispatch" in on_block(_opener()), (
        "opener must be manually dispatched"
    )


def test_opener_takes_the_branch_to_propose() -> None:
    """The maintainer prepares a branch; the opener only proposes it."""
    inputs = on_block(_opener())["workflow_dispatch"]["inputs"]
    assert "branch" in inputs, "opener must take the prepared branch as input"


def test_opener_authors_the_pr_as_the_app() -> None:
    """The PR must be App-authored or the only human cannot approve it.

    `main` requires one approving review, GitHub forbids self-approval, and no
    App holds bypass — so a human-authored PR to `main` is unmergeable.
    """
    doc = _opener()
    steps = steps_of_job(doc, next(iter(jobs(doc))))
    assert any("create-github-app-token" in str(s.get("uses", "")) for s in steps), (
        "opener must mint an App token so the PR is App-authored"
    )


def test_opener_targets_main_and_labels_the_pr() -> None:
    """Without the label the guard stays inactive and proves nothing."""
    body = _opener_body()
    assert "gh pr create" in body, "opener must open the PR"
    assert "--base main" in body, "opener must target main"
    assert LANE_LABEL in body, f"opener must apply the `{LANE_LABEL}` label"


# ── Repo conventions ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", [GUARD_PATH, OPENER_PATH], ids=lambda p: p.name)
def test_actions_are_sha_pinned(path: Path) -> None:
    """Every third-party action is pinned to a full commit SHA."""
    for job_name, job in jobs(load_workflow(path)).items():
        for step in job.get("steps", []):
            uses = step.get("uses")
            if not uses or uses.startswith("./"):
                continue
            assert ACTION_PIN_RE.match(uses), (
                f"{path.name}:{job_name} uses unpinned action {uses!r}"
            )
