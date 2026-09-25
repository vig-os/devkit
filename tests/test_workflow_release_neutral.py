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

# The concurrency lane, split by event kind (#1698). Code events share one
# cancel-in-progress lane; label events get a lane of their own keyed on the run
# id, because `gh pr create --label a --label b` emits two `labeled` events
# within a second and an undiscriminated lane made each cancel the run before it.
CONCURRENCY_GROUP = (
    "release-neutral-guard-${{ github.event.pull_request.number }}-"
    "${{ (github.event.action == 'labeled' || github.event.action == 'unlabeled') "
    "&& github.run_id || 'code' }}"
)

# The sticky-verdict marker: gate 6 upserts one comment rather than appending a
# thread of stale verdicts.
VERDICT_MARKER = "<!-- release-neutral-guard:verdict -->"


def _guard() -> dict:
    return load_workflow(GUARD_PATH)


def _opener() -> dict:
    return load_workflow(OPENER_PATH)


def _guard_body() -> str:
    return run_text_of_job(jobs(_guard())[GUARD_JOB])


def _opener_body() -> str:
    doc = _opener()
    return run_text_of_job(jobs(doc)[next(iter(jobs(doc)))])


def _verdict_step() -> dict:
    return step_by_name(steps_of_job(_guard(), GUARD_JOB), "verdict")


def _verdict_code() -> str:
    """Gate 6's executable lines only.

    Its comments name the alternatives it rejects (`gh pr comment --edit-last`,
    `always()`), so an assertion against the raw body would pass on a comment.
    """
    return "\n".join(
        line
        for line in str(_verdict_step().get("run", "")).splitlines()
        if not line.lstrip().startswith("#")
    )


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


# ── Guard: concurrency (the self-cancelling lane, #1698) ─────────────────────


def _concurrency() -> dict:
    block = _guard().get("concurrency")
    assert isinstance(block, dict), "guard must declare a concurrency block"
    return block


def test_guard_gives_label_events_their_own_concurrency_lane() -> None:
    """A label event must never cancel the run started by a code event.

    The guard triggers on `labeled`/`unlabeled` as well as `opened`/`synchronize`.
    With one undiscriminated `cancel-in-progress` lane per PR, every label event
    cancelled whatever guard run was in flight — and `gh pr create --label a
    --label b` emits two `labeled` events within a second, so a PR opened with
    two labels left `cancelled` guard runs on its head beside the eventual
    success. A cancelled check run of a *required* name keeps a PR's status
    rollup red however many successes land after it, which is why the split is
    worth having even though this guard is not required today.

    So the group is keyed on `github.run_id` for the two label actions and on a
    constant for everything else: label events are mutually independent, code
    events still supersede each other.
    """
    group = " ".join(str(_concurrency().get("group", "")).split())
    assert group == CONCURRENCY_GROUP, (
        f"expected concurrency group {CONCURRENCY_GROUP!r}, got {group!r} — "
        "label events need a lane of their own, keyed on the run id"
    )


def test_guard_still_supersedes_code_runs() -> None:
    """Cancellation stays unconditional; the lane split does the discriminating.

    Rejected alternative: one lane with
    `cancel-in-progress: ${{ github.event.action == 'synchronize' }}`.
    `cancel-in-progress: false` means QUEUE behind the in-flight run, not run
    beside it, so a label event would wait out an in-flight 90-minute vulnix
    extra — and the label event is exactly the one whose verdict must not be
    stale. Hence a literal `true` plus per-event groups.
    """
    cancel = _concurrency().get("cancel-in-progress")
    assert cancel is True, (
        f"cancel-in-progress must be a literal true, got {cancel!r} — a false or "
        "expression-valued setting queues a label event behind the in-flight "
        "code run instead of running it beside it"
    )


def test_guard_activation_gates_label_events_on_the_label_name() -> None:
    """An unrelated label must not start a gate run, only a cheap success.

    `area:ci`, a priority relabel, a `Refs` triage pass — none of them tell the
    guard anything it did not already know, and each one now gets its own lane,
    so without this every relabel would pay for a full gate run (up to a 90-min
    vulnix extra). Gating the label actions on `github.event.label.name` makes
    those runs an all-steps-skipped SUCCESS.

    The label *set* is still read from `github.event.pull_request.labels`, not
    from `github.event.label`, so an `unlabeled` event removing the lane label
    correctly deactivates rather than activating on its own name.
    """
    active = " ".join(str(jobs(_guard())[GUARD_JOB]["env"]["ACTIVE"]).split())
    assert (
        f"contains(github.event.pull_request.labels.*.name, '{LANE_LABEL}')" in active
    ), (
        "ACTIVE must read the label set from the pull request, so an "
        f"`unlabeled` event removing `{LANE_LABEL}` deactivates the gates"
    )
    assert f"github.event.label.name == '{LANE_LABEL}'" in active, (
        "ACTIVE must gate the label actions on the label name, or an unrelated "
        "label starts a full gate run in its own lane"
    )
    for action in ("labeled", "unlabeled"):
        assert f"github.event.action != '{action}'" in active, (
            f"ACTIVE must exempt non-`{action}` actions from the label-name "
            "test, or `opened`/`synchronize` (which carry no "
            "`github.event.label`) would never activate"
        )


def test_scope_report_distinguishes_an_unrelated_label_event() -> None:
    """The scope report must not claim the label is absent when it is present.

    Once `ACTIVE` gates the label actions on the label name, a relabel for
    something else resolves inactive on a PR that *does* carry
    `release-neutral` — so the two-branch report ("no `release-neutral` label")
    would state the opposite of the truth and invite the reviewer to add a label
    that is already there. Three states, three messages: active; carries the
    label but this event is not about it; no label at all.

    `LABELLED` is what makes the middle branch expressible — `ACTIVE` has
    already collapsed the label set and the event into one boolean.
    """
    env = jobs(_guard())[GUARD_JOB]["env"]
    labelled = " ".join(str(env.get("LABELLED", "")).split())
    assert (
        f"contains(github.event.pull_request.labels.*.name, '{LANE_LABEL}')" in labelled
    ), (
        "the job needs a LABELLED env reading the label set alone, or the scope "
        "report cannot tell 'no label' from 'not this event'"
    )
    run = str(step_by_name(steps_of_job(_guard(), GUARD_JOB), "Report scope")["run"])
    assert "LABELLED" in run, "the scope report must consult LABELLED"
    assert run.count("elif") >= 1, (
        "the scope report must branch three ways; with two branches an "
        "unrelated relabel is reported as 'no `release-neutral` label'"
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


def test_gate_3_excludes_the_changelog_mirror() -> None:
    """Gate 3 must not refuse the one `assets/` path gates 1 and 2 permit.

    `CHANGELOG.md` is mirrored to `assets/workspace/.devcontainer/CHANGELOG.md`.
    Gate 1 stopped refusing the changelog and gate 2 normalizes it away before
    comparing derivations — but a gate 3 that still refuses `assets/` wholesale
    would reject every changelog-carrying PR anyway, defeating the widening.
    """
    gate3 = str(
        step_by_name(steps_of_job(_guard(), GUARD_JOB), "Gate 3").get("run", "")
    )
    assert "exclude" in gate3, (
        "gate 3 must exclude the changelog mirror from its assets/ check, or it "
        "refuses exactly what gates 1 and 2 were widened to admit"
    )
    assert "assets/workspace/.devcontainer/CHANGELOG.md" in gate3, (
        "gate 3 must name the changelog mirror as the excluded path"
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


def test_gate_6_upserts_one_sticky_verdict_comment() -> None:
    """One current verdict, not a thread of stale ones.

    The guard reruns on every `synchronize` and on its own label event, and each
    run used to append another comment. A reviewer reading the first verdict
    would be reading a file list and a changelog diff that no longer exist. So
    the body carries an HTML marker, and the step looks that marker up and
    PATCHes the existing comment before falling back to posting a new one.

    Matched by marker rather than `gh pr comment --edit-last`, which edits the
    acting identity's last comment — for `github-actions[bot]` that may belong
    to an entirely different workflow.
    """
    verdict = str(
        step_by_name(steps_of_job(_guard(), GUARD_JOB), "verdict").get("run", "")
    )
    step = step_by_name(steps_of_job(_guard(), GUARD_JOB), "verdict")
    marker = VERDICT_MARKER in verdict or VERDICT_MARKER in str(step.get("env", {}))
    assert marker, (
        f"the verdict body must carry the {VERDICT_MARKER!r} marker, or a rerun "
        "cannot find the comment it wrote last time"
    )
    # Asserted against the executable lines: the step's comments name
    # `gh pr comment --edit-last` in order to reject it.
    code = "\n".join(
        line for line in verdict.splitlines() if not line.lstrip().startswith("#")
    )
    lookup = code.find("contains(")
    post = code.find("gh pr comment")
    assert lookup != -1, (
        "the verdict step must look the marker up among the PR's comments"
    )
    assert "--method PATCH" in code, (
        "the verdict step must PATCH the existing comment in place"
    )
    assert post != -1 and lookup < post, (
        "the marker lookup must precede the `gh pr comment` fallback, or every "
        "run posts a fresh comment before discovering the old one"
    )
    assert "--edit-last" not in code, (
        "`gh pr comment --edit-last` edits the token identity's last comment, "
        "which for `github-actions[bot]` may be another workflow's — match the "
        "marker instead"
    )
    assert "env.MARKER" in code, (
        "the marker must reach jq through the environment, not through a "
        "shell-escaped interpolation into the filter string"
    )


def test_gate_6_prunes_every_verdict_but_the_newest() -> None:
    """Concurrent ACTIVE runs must converge on exactly one verdict comment.

    Label events run in per-run lanes, so they neither cancel nor are cancelled:
    the opener's own flow (`opened` plus two `labeled` events for the lane label)
    can leave three ACTIVE runs in flight, each racing the marker lookup, each
    finding nothing and creating its own marked comment. The upsert alone then
    leaves two or three marked comments and only ever PATCHes the newest, so the
    stale ones outlive every later run.

    So after upserting, the step lists the marked comments again and deletes
    all but the newest. Whichever run finishes last leaves exactly one verdict, no
    matter how many raced. `pull-requests: write` already covers the delete.
    """
    step = step_by_name(steps_of_job(_guard(), GUARD_JOB), "verdict")
    code = "\n".join(
        line
        for line in str(step.get("run", "")).splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "--method DELETE" in code, (
        "gate 6 must delete the verdict comments it superseded, or concurrent "
        "label runs leave a pile of marked comments behind"
    )
    prune = code.find("--method DELETE")
    for upsert in ("--method PATCH", "gh pr comment"):
        assert code.find(upsert) < prune, (
            f"the prune must run AFTER the {upsert!r} upsert, or it deletes the "
            "comment this run is about to write"
        )
    assert "newest" in code and "continue" in code, (
        "the prune must keep the newest marked comment and delete only the "
        "others — a prune with no exception deletes the verdict itself"
    )


def test_gate_6_runs_after_a_gate_failure_and_on_deactivation() -> None:
    """The verdict must be rewritten, not left standing, when the proof fails.

    Gate 6 ran under a bare `if: env.ACTIVE == 'true'`, which carries an
    implicit `success()`: a gate-2 failure, or an `unlabeled` event, skipped it
    and left the last *positive* verdict standing. Since the verdict became
    sticky (#1698) that stale pass is not merely buried under newer comments —
    it is the pull request's single, permanent verdict, and the guard is not a
    required check, so nothing else stops a reviewer reading it as a pass.

    `!cancelled()`, never `always()`: code events still supersede each other, and
    a run cancelled by a newer head must not overwrite the sticky comment with a
    refusal it never actually reached.

    The `!` needs the `${{ }}` form — bare `!cancelled()` is a YAML tag.
    """
    step = _verdict_step()
    cond = " ".join(str(step.get("if", "")).split())
    assert "cancelled()" in cond, (
        "gate 6 must drop the implicit `success()` — with it, a failed gate "
        f"leaves the last positive verdict standing; got {cond!r}"
    )
    assert "always()" not in cond, (
        "gate 6 must use `!cancelled()`, not `always()`: a run cancelled by a "
        "superseding head would overwrite the verdict with a refusal it never "
        "reached"
    )
    assert cond.startswith("${{"), (
        "the condition must be written in the `${{ }}` form, or YAML reads the "
        f"leading `!` as a tag; got {cond!r}"
    )
    assert "env.ACTIVE == 'true'" in cond, "gate 6 must still run on the active lane"
    assert "env.DEACTIVATED == 'true'" in cond, (
        "gate 6 must also run when the lane label was just removed, or the "
        "verdict it wrote while active outlives the label"
    )
    assert step.get("continue-on-error") is True, (
        "a failure to post the verdict must not turn the gates' conclusion red"
    )


def test_guard_defines_a_deactivation_discriminator() -> None:
    """`ACTIVE` and `LABELLED` are BOTH false on the payload that needs gate 6.

    On an `unlabeled` event the label is already gone from
    `github.event.pull_request.labels`, so the label set reads empty: `ACTIVE`
    is false and so is `LABELLED`. The obvious
    `always() && (env.ACTIVE == 'true' || env.LABELLED == 'true')` therefore
    stays false on exactly the event that must retract the verdict. A third
    discriminator, read from `github.event.label` rather than from the set, is
    what makes the retraction expressible.
    """
    env = jobs(_guard())[GUARD_JOB]["env"]
    deactivated = " ".join(str(env.get("DEACTIVATED", "")).split())
    assert "github.event.action == 'unlabeled'" in deactivated, (
        "the job needs a DEACTIVATED env keyed on the `unlabeled` action — the "
        "label set is already empty by then, so neither ACTIVE nor LABELLED can "
        "express it"
    )
    assert f"github.event.label.name == '{LANE_LABEL}'" in deactivated, (
        "DEACTIVATED must read `github.event.label.name` and scope it to "
        f"`{LANE_LABEL}`, or removing an unrelated label retracts the verdict"
    )


def test_every_gated_step_is_readable_by_the_verdict() -> None:
    """Every step the verdict can be wrong about must carry an `id`.

    Gate 6 decides which verdict to write from `steps.<id>.outcome`, so a gated
    step without an `id` is invisible to it — and an invisible *failure* reads as
    a pass. The checkout and the toolchain set-up count too: if either fails,
    every gate after it is `skipped`, which is not `failure`, so a verdict
    consulting only the gates would report neutrality on a run that proved
    nothing.
    """
    verdict = _verdict_step()
    read = str(verdict.get("env", {})) + str(verdict.get("run", ""))
    gated = [
        s
        for s in steps_of_job(_guard(), GUARD_JOB)
        if s is not verdict and "env.ACTIVE" in str(s.get("if", ""))
    ]
    assert gated, "the guard must still gate its steps on the lane"
    for step in gated:
        step_id = step.get("id")
        assert step_id, (
            f"gated step {step.get('name')!r} carries no `id`, so gate 6 cannot "
            "read its outcome and a failure there reads as a pass"
        )
        assert f"steps.{step_id}.outcome" in read, (
            f"gate 6 must consult `steps.{step_id}.outcome` — "
            f"{step.get('name')!r} can fail, and an unread failure leaves a "
            "positive verdict standing"
        )


def test_gate_6_refuses_instead_of_repeating_the_positive_verdict() -> None:
    """The positive wording must sit behind the outcome test, not before it.

    The whole defect is a verdict that says "release-neutral" on a run that
    proved nothing. So the body branches on the outcomes first, and the positive
    sentence is reachable only when no gate failed.
    """
    code = _verdict_code()
    assert "failure" in code, (
        "gate 6 must test the gates' outcomes for `failure`, or it writes the "
        "same verdict whatever happened"
    )
    positive = code.find("This change is release-neutral")
    assert positive != -1, "the green verdict's wording must survive unchanged"
    assert code.find("failure") < positive, (
        "the outcome test must precede the positive verdict, or the refusal is "
        "written after the pass it is supposed to replace"
    )
    assert "not release-neutral" in code.lower(), (
        "the refusal must say so in words — a reviewer reads the comment, not "
        "the job's conclusion"
    )


def test_gate_6_separates_an_infrastructure_failure_from_a_refusal() -> None:
    """ "The gates refused it" and "the runner broke" are different messages.

    A failed checkout or a failed `setup-env` proves nothing either way; only a
    gate failing is a refusal. Conflating them would either libel a change that
    was never examined or excuse one that was.
    """
    code = _verdict_code()
    assert "infrastructure" in code.lower(), (
        "the refusal must distinguish a gate refusal from an infrastructure "
        "failure (the checkout or `setup-env`), which proves nothing either way"
    )


def test_gate_6_retracts_the_verdict_without_ever_creating_one() -> None:
    """Deactivation is PATCH-or-nothing; only the failure path may create.

    A pull request that carried the label briefly and never had a verdict must
    get no comment at all — an "inactive" stub on a PR that was never judged is
    pure noise. So the deactivation branch withdraws an existing sticky comment
    and posts nothing when there is none.

    It must also not touch the worktree. `ACTIVE` is false on the `unlabeled`
    payload, so the checkout step is skipped and there is no tree to read; and on
    a gate-2 or vulnix-extra failure the tree is still parked on the base ref,
    because the `git checkout -q -` restore comes *after* the command that
    failed. Both non-green branches therefore state their verdict from the event
    alone.
    """
    code = _verdict_code()
    deactivated = code.find("DEACTIVATED")
    post = code.find("gh pr comment")
    assert deactivated != -1, "gate 6 must branch on DEACTIVATED"
    assert post != -1 and deactivated < post, (
        "the deactivation branch must be decided before the create fallback"
    )
    assert "inactive" in code[deactivated:post].lower(), (
        "the deactivation branch must rewrite the comment as an inactive stub, "
        "or the positive verdict survives the label's removal"
    )
    assert "may_create=false" in code[deactivated:post], (
        "the deactivation branch must forbid creating a comment, or a pull "
        "request that was labelled and unlabelled gets a stub it never earned"
    )
    assert '"$may_create" = "true"' in code[:post], (
        "the `gh pr comment` fallback must be gated on that flag, or the "
        "deactivation branch creates the very comment it must not"
    )
    tree = code[deactivated : code.find("changed=$(git diff")]
    assert "git " not in tree, (
        "neither the inactive stub nor the refusal may read the worktree: a "
        "deactivated run never checked anything out, and a failed gate 2 or "
        "vulnix extra leaves the tree on the base ref, so a file list there "
        "would come out empty"
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


def test_opener_sources_the_retry_helper_before_using_it() -> None:
    """Any step calling `retry` must first source the helper.

    `retry` is a bash FUNCTION exported through `BASH_ENV` by the `setup-env`
    composite action. The opener deliberately skips `setup-env` (it needs no
    toolchain — `gh` is preinstalled), so the function is simply absent and the
    call dies with `retry: command not found`, exit 127. That is precisely how
    the lane's first live dispatch failed (run 36054453452).

    `prepare-hotfix.yml` already solved this the same way: source the canonical
    helper straight out of the checkout.
    """
    for step in steps_of_job(_opener(), next(iter(jobs(_opener())))):
        run = str(step.get("run", ""))
        if "retry " not in run:
            continue
        assert ".github/scripts/retry.sh" in run, (
            f"step {step.get('name')!r} calls `retry` without sourcing "
            ".github/scripts/retry.sh — the function is only in scope after "
            "setup-env, which this job does not run"
        )


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
