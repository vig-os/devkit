---
type: issue
state: closed
created: 2026-09-24T11:53:58Z
updated: 2026-09-24T20:05:57Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1676
comments: 0
labels: feature, priority:medium, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-25T07:32:56.884Z
---

# [Issue 1676]: [Release-neutral lane: merge to main without cutting a release](https://github.com/vig-os/devkit/issues/1676)

## Problem Statement

`main` can only be written by a release. Gitflow gives it no other lane: `prepare-release` and `prepare-hotfix` are the only paths, and both cut a tag, publish a GHCR image and trigger `devkit-upgrade` adoption PRs across every consumer repo.

But plenty of changes belong on `main` while changing **nothing a consumer receives**:

- devkit's **own** `.github/workflows/**` — devkit's CI, not the scaffolded copy under `assets/workspace/`
- `tests/**`, `packages/*/tests/**`
- most of `docs/**`
- the scan-time registers (`.vulnixignore`, `.trivyignore`, `.github/dependency-review-allow.txt`)

For each of these, cutting a release republishes a **functionally identical** artifact — the only bytes that differ are the version string baked into `/root/assets/VERSION` and the scaffolded `.vig-os` (`flake.nix:1452`/`:1459`), `DEVKIT_VERSION` in the repo `.vig-os` (`release.yml:573`), and the changelog. Every consumer then gets an adoption PR that bumps a pin and changes nothing they run.

Today the only options are to wait for the next real release (up to a week) or to inflate the version for a no-op. Two concrete instances already in hand:

1. A workflow that must exist on `main` to be dispatchable at all (`workflow_dispatch` only registers from the default branch) — it changes no consumer asset, yet currently needs a release or an admin bypass to get there.
2. A `.vulnixignore` amendment. `main` and `dev` each run their own nightly vulnix leg against their own closure and register, so an amendment on `dev` leaves `main`'s lane red until the next train. The register moved **32 times in 90 days** (~one per 3 days) against a roughly **weekly** release cadence, so that lane is stale more often than current — and a permanently-red security lane teaches the maintainer to ignore it.

## Proposed Solution

A **release-neutral lane**: merge to `main` without a release, admitted only when a machine proof shows no published artifact changes.

"Release-neutral" is the whole contract, and it is checkable rather than a matter of judgement.

### Constraint: who may write to `main`

`main`'s ruleset (`13444364`):

| Rule | Value |
|---|---|
| Required approving reviews | **1** |
| `dismiss_stale_reviews_on_push` | true |
| `require_extra_approval_for_unattributed_changes` | true |
| Required checks (**strict**) | `CodeQL Analysis (actions)`, `CodeQL Analysis (python)`, `Test Summary` |
| **Bypass actors** | **`OrganizationAdmin` only — no App** |

Plus a `~ALL`-ref `required_signatures` rule with no bypass.

Two consequences:

1. **No workflow can merge to `main` without a human approval.** `promote-release.yml:672` merges with a plain `gh pr merge --merge` — the App merges an already-compliant PR, it never bypasses.
2. **GitHub forbids authors approving their own PRs.** With one maintainer, a human-authored PR to `main` is unapprovable and therefore unmergeable. Every release PR into `main` is authored by `app/vig-os-release-app` and approved by `c-vigo` (verified on #1672, #1648, #1620) — the protection model *depends* on App authorship.

So the App's role is narrow and specific: **author the PR so the human's approval is legal.** Nothing else about the lane is automated.

### Shape

| Step | Who | What |
|------|-----|------|
| 1 | Maintainer | Branch off `main`, cherry-pick the release-neutral commits, push |
| 2 | Workflow (`workflow_dispatch`) | Opens the PR **as the App**, labels it `release-neutral` |
| 3 | Workflow (`pull_request`) | Runs the gates, posts a verdict comment |
| 4 | Maintainer | Reads the verdict, approves (legal — App is author), merges |

Pushing to the App's PR is fine (approval is blocked only for the PR author), but never *after* approving.

### Gates

| # | Gate | Proves | Cost |
|---|------|--------|------|
| **1** | No release content | `CHANGELOG.md`, its mirror and `.vig-os` untouched — changing those *is* releasing | instant |
| **2** | **Derivations identical** | `devShells.default`, `packages.devkitImage`, `packages.devkitImageEnv` `.drv` paths equal to `main`'s | seconds (eval only) |
| **3** | Scaffold untouched | `assets/**` byte-identical — what consumers scaffold | instant |
| **4** | `## Unreleased` empty | `prepare-release` and `prepare-hotfix` both require it | instant |
| **5** | No train in flight | `main`'s checks are strict, so moving it mid-train dismisses the release PR's approval | instant |
| **6** | Verdict comment | What changed, and the proof it is release-neutral | instant |

**Gate 2 is the contract.** Equal `.drv` paths mean the published artifacts *cannot* differ, whatever the diff touched — a proof rather than an argument about which files are inputs. It covers both consumption modes: the image for devcontainer consumers, `devShells.default` for `direnv`/`bare` ones.

Gate 3 is formally subsumed by Gate 2 (the scaffold is copied into the image) but kept for diagnostics: "you changed `assets/workspace/.claude/skills/foo`" is a far more useful failure than two unequal store hashes.

**The gates genuinely discriminate** — this is not a rubber stamp:

| Change | Verdict | Why |
|---|---|---|
| devkit's own `.github/workflows/**` | **admitted** | not in the image, not in `assets/` |
| `tests/**` | **admitted** | same |
| `.vulnixignore` | **admitted** | not an image input |
| `docs/MIGRATION.md` | **refused** | baked into the image (`flake.nix:1433`) |
| `.claude/skills/**` | **refused** | manifest-synced into `assets/workspace/` |
| `nix/hooks.nix` | **refused** | changes `devShells.default` |

### Content-triggered extra

When the diff touches `.vulnixignore`, the guard additionally replays `main`'s own nightly gate — build `main`'s closure, run vulnix, require `vulnix-gate` exit 0.

This is **not** part of the lane's contract; it is one extra check that fires on content. It exists because the register is not append-only: a pin advance on `dev` *clears* exceptions (6 of those 32 commits) and `dev`'s pin advances first, so there is always a window where `dev` has correctly deleted an exception that `main`'s older, still-vulnerable closure depends on. Carrying that deletion to `main` would strand a real finding. The extra gate does not reason about whether a removal is safe — it runs the real gate and reads the exit code.

Fast path: `main`'s closure changes only when `main` changes, and `main` moves only on releases, so if the newest nightly scanned `main`'s current head its findings artifact is replayed in seconds instead of rebuilding.

### Edge cases

- **Release PRs must not trip the gates.** A release PR legitimately changes `CHANGELOG.md`, `.vig-os` and the scaffold. The guard must **skip to success** on any PR without the `release-neutral` label. Getting this wrong blocks every release — which is why the label, not the diff shape, is the trigger.
- **Required-check semantics.** If the guard is later made a required context on `main`, "skip" must mean "ran and passed", never "no report" — a skipped job would hang release PRs on a check that never arrives. Hence no job-level `if`.
- **The guard never writes.** `main` sets `dismiss_stale_reviews_on_push`, so a guard that pushed would discard the approval the lane depends on.
- **`main` will carry commits not in any release.** That is the deliberate change to the current invariant. Nothing checked depends on the strict form: the hotfix precondition is "PATCH+1 of the highest stable tag *reachable from* `main`", which extra commits do not disturb.
- **Reconvergence.** Cherry-picked content is identical to `dev`'s, so the next train's `dev`→`main` merge stays clean.
- **No changelog on a lane PR** (Gates 1 and 4). The entry, if any, lives on `dev` and ships with the next real release.
- **Unverified:** `require_extra_approval_for_unattributed_changes: true`. App-authored commits *should* be attributed to the app rather than counting as unattributed, but this is unproven. If it bites, a lane PR would silently demand a second approval that cannot be supplied. Confirm during the first live run.

### Bootstrap

`workflow_dispatch` only registers from the default branch, so the opener must exist on `main` before the lane can run — the lane cannot deliver itself. One time only:

1. Land the workflows on `dev` via the normal PR route.
2. Cherry-pick onto a branch off `main`, open a PR, merge with **`OrganizationAdmin` bypass**.

Both refs then hold identical content, so the next release merge is clean. After that the lane carries its own future changes, which is precisely instance (1) above.

## Alternatives Considered

- **A path allowlist as the primary gate.** Rejected as the contract: it encodes a guess about which files are published rather than proving it, and it would have to be extended for every new kind of release-neutral change. Kept only as the narrow "no release content" check (Gate 1), where the point really is the file identity.
- **Add an App to `main`'s bypass actors.** Rejected: that App could then merge *anything* to `main` — a blast radius far beyond this lane.
- **Routine `OrganizationAdmin` bypass.** Rejected as the default: near-invisible in audit, and it skips the step where the verdict is read. Reserved for the bootstrap.
- **Single-source the scan registers** so `main` never needs the file. Rejected: contradicts the deliberate per-ref design (`security-scan.yml:70`), and once pins diverge `dev`'s register can mask a finding real on `main`. Also solves only the register instance, not the general problem.

## Impact

Breaking change: no. New lane, opt-in per PR via label; existing release machinery untouched.

## Changelog Category

Added

---

## Revised plan (2026-09-24): `main` may carry unshipped changes

Decision taken: **supersede #590's invariant.** Today `main`'s `## Unreleased` is empty *by construction*. From now on it **describes changes that have landed on `main` but are not yet shipped.** Everything below follows from that sentence.

Two earlier objections were checked and dropped:

- **"`dev` would lack the content"** — `sync-main-to-dev.yml` triggers on `push: [main]`, not only post-promote, and opens a PR whenever `dev` is behind. Self-healing.
- **"the next release would conflict on `CHANGELOG.md`"** — because that sync reaches `dev` *before* the next freeze, `prepare-release` freezes the carried entries normally and the release→`main` merge applies cleanly.

A correction to the earlier text: `prepare-release` never inspects `main`'s `## Unreleased` — it runs on `dev` and requires *dev's* section to have content (`prepare-release.yml:145`). Only `prepare-hotfix` checks main's (`prepare-hotfix.yml:163`).

### Phase 3 — widen the lane to admit changelog entries (this issue)

The non-obvious blocker. `CHANGELOG.md` is mirrored to `assets/workspace/.devcontainer/CHANGELOG.md`, which is **baked into the image**. Measured: identical tree → `devkitImage d6ikbz96…`; add a changelog entry → `ffbgni7c…`. So under gate 2's own contract *any* change carrying a changelog entry fails the lane — which would force an `--admin` bypass every time and defeat the purpose.

Fix — **normalized derivation comparison**:

1. Revert `CHANGELOG.md` and its mirror to the base's version.
2. *Then* compare `drvPath`s.
3. Equal ⇒ the only published difference is changelog text, which the new model permits.

Accompanying changes:

- Gate 1 stops refusing `CHANGELOG.md` and its mirror; keeps refusing `.vig-os`.
- Gate 4 (main's `## Unreleased` empty) is **dropped** — superseded by the model change.
- The verdict reports the changelog drift explicitly, so it stays visible rather than silently tolerated.
- Docs record the superseded invariant.

### Phase 1 — `prepare-hotfix`: freeze instead of refuse

`prepare-hotfix.yml:163` refuses when main's Unreleased has content. Under the new model that is wrong: a hotfix cuts from main's head, so it *ships* those changes and their entries belong in its version section. Branch on content — present → `prepare-changelog prepare`, empty → `seed` as today. Main's Unreleased then self-clears when the release branch merges back.

**Decided:** the `release.yml` publish-time gate stands unchanged — no empty sections at release time, empty is acceptable at `prepare-hotfix` time. No compensating check.

### Phase 2 — `prepare-release`: guard the sync ordering

Refuse (or warn) when `git rev-list --count origin/main ^origin/dev` ≠ 0, so a release is never cut while `main` carries entries `dev` has not yet received.

### Sequencing

**Decided:** ship the lane first, then fix the hotfix lane *using* it — rather than fixing `prepare-hotfix` first.

1. Phase 3 lands on this issue's branch (#1678).
2. Bootstrap #1678 → `main` with **one `--admin` merge**. Unavoidable: `workflow_dispatch` registers only from the default branch, so the lane cannot deliver itself.
3. Phases 1 and 2 then reach `main` through the lane — its first real job.

**Caveat for Phases 1–2:** `prepare-hotfix.yml` also ships in the scaffold (`assets/workspace/.github/workflows/`). Devkit's **own** copy is release-neutral and can ride the lane; the **scaffold** copy is a published asset and still needs a release. Expect to split those.

