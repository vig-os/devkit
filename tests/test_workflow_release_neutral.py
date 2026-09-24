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

The gates genuinely discriminate. Measured against `main` at 2026-09-24:

    devkit's own .github/workflows/**, tests/**, docs/CONTAINER_SECURITY.md
        -> devkitImage d6ikbz96... == main's d6ikbz96...      ADMITTED
    the same tree plus a CHANGELOG.md entry
        -> devkitImage ffbgni7c... != main's d6ikbz96...      REFUSED

That second line is why `CHANGELOG.md` counts as release content: the changelog
is mirrored into `assets/workspace/.devcontainer/CHANGELOG.md`, which is baked
into the image. It is also why a lane PR must never carry a changelog edit —
beyond neutrality, a changelog entry on `main` would leave `## Unreleased`
non-empty, which `prepare-release` and `prepare-hotfix` both refuse to start on.

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
RELEASE_CONTENT = (
    "CHANGELOG.md",
    ".vig-os",
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


def test_gate_3_refuses_scaffold_changes() -> None:
    """Gate 3: `assets/` is what consumers scaffold.

    Formally subsumed by gate 2 (the scaffold is copied into the image), but
    kept for diagnostics: naming the offending file beats two unequal hashes.
    """
    assert "assets/" in _guard_body(), "gate 3 must check the scaffold tree"


def test_gate_4_asserts_unreleased_stays_empty() -> None:
    """Gate 4: `prepare-release` and `prepare-hotfix` both require it."""
    assert "Unreleased" in _guard_body(), "gate 4 must assert Unreleased is empty"


def test_gate_5_refuses_while_a_release_train_is_in_flight() -> None:
    """Gate 5: moving `main` mid-train dismisses the release PR's approval.

    `main`'s required checks are strict, so the train would have to re-satisfy
    up-to-date-ness after this merge, discarding its review.
    """
    assert "release/" in _guard_body(), "gate 5 must detect an in-flight train"


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
