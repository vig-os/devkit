---
type: issue
state: closed
created: 2026-09-18T21:34:54Z
updated: 2026-09-21T14:05:24Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1654
comments: 2
labels: feature, area:workspace, effort:large, semver:minor
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-22T07:36:31.177Z
---

# [Issue 1654]: [[FEATURE] Reconcile a preserved .pre-commit-config.yaml: fold retired blocks, insert hooks the consumer never received](https://github.com/vig-os/devkit/issues/1654)

> **Extended 2026-09-21** with a second case — a hook the template ships that the
> consumer's file *lacks entirely*. #1660 shipped the first real instance and
> proved the gap is not hypothetical. The original retired-block case is
> unchanged below; the new one is [Case 2](#case-2-a-hook-the-consumer-never-received).

## Problem

A preserved `.pre-commit-config.yaml` (#878/#913/#1099) protects the consumer's
customizations and, by the same token, blocks every kind of template evolution.
Two distinct divergences result, and neither self-heals.

### Case 1 — a retired block that breaks

[#1652](https://github.com/vig-os/devkit/issues/1652) makes a retired hook block in a **preserved** `.pre-commit-config.yaml` visible: the scaffold warns with `file:line` and the adoption PR body carries a `preserved-hook-drift:` marker. That helps every consumer who still gets an adoption PR.

It does not help the ones that need it most. The pre-#1170 pymarkdown hook breaks `prek`, and `devkit-upgrade.yml` commits **in the project shell with the hooks running** — so the upgrade fails at the commit step, before the branch is published and before any PR exists. Those repos see a red scheduled run and a failure-report issue, and the notice that would explain it never reaches a reviewer.

### Case 2 — a hook the consumer never received

A **new** hook added to the template reaches new scaffolds only. An existing repo's
preserved config is never rewritten, so the hook simply never arrives; the #878
template diff mentions it, and acting on that diff is manual and easy to skip.

#1660 is the motivating instance: `actionlint` had been on `PATH` in every
consumer environment since #995, but nothing ran it, so consumers' workflows were
linted by nothing. #1660 shipped the hook — and every *existing* consumer still
has no workflow linting until someone hand-folds the block. The capability was
delivered to the scaffold and not to the fleet.

That case was accepted deliberately when #1660 landed: it follows the split
#1652's own table documents (that table is for blocks the template retired
*because they break*, "never for ordinary drift", and it names the #878 diff as
the right tool for "a new hook was added"). This issue is where that decision
gets revisited if the diff proves too passive.

## Proposal

One reconciliation pass over the preserved hook config, with a separate safety
gate per case. Shared requirements: everything else in the consumer's file is
untouched (their global/per-hook `exclude:` patterns, ordering, comments), the
change is reported loudly on the existing machine-readable channel, and it shows
up as a normal reviewable hunk in the adoption diff.

### Case 1 — fold (replace)

Fold a known-bad block automatically when — and only when — it is unambiguously devkit's own retired output:

- the block matches the historical template shape **exactly** (byte-match against the retired block, not just the `repo:` line);
- the replacement is the current template's block for the same hook id;
- everything else in the consumer's file is untouched (their global/per-hook `exclude:` patterns, ordering, comments);
- the fold is reported loudly (a `preserved-hook-fold:` line alongside the existing `preserved-hook-drift:` channel) and shows up as a normal reviewable hunk in the adoption diff.

Precedent for surgically editing a consumer-owned file this way: `migrate_root_gitignore` ([#1145](https://github.com/vig-os/devkit/issues/1145)).

### Case 2 — insert

**Absence is ambiguous, and that is the whole difficulty.** Case 1's gate is a
byte-match proving the block is devkit's own output. Nothing equivalent exists
here: a missing hook may mean the consumer never received it, or that they
deliberately deleted it. Inserting unconditionally would re-add it on every
upgrade and make deleting a hook non-durable — exactly the defect #1651 fixed for
`LICENSE`/`CHANGELOG.md`, where "a deleted file stays deleted" needed a knob to
become true.

A version gate discriminates the two cases, and the machinery already exists.
`retired_prune_paths()` (#1348) gates on `version_lt "$PREVIOUS_PIN" "$ver"` —
"this tree was produced by a devkit older than the release that stopped shipping
path P". The mirror is: **insert only when `PREVIOUS_PIN` predates the release
that started shipping the hook**, i.e. the consumer's tree was generated before
the hook existed and they never had the chance to decline it. A repo pinned at or
after that release has seen the hook and its absence is a choice, so it is left
alone.

That needs a table like `retired_paths()`, keyed the other way: one
`<first release shipping it> <hook id>` row per hook. `actionlint` (#1660) is the
first row.

Durable opt-out is then the feature group, not a hand deletion:
`DEVKIT_FEATURES_DISABLED=actionlint` already excises the hook at render time
(#1660), so a consumer who wants it gone has a declaration that survives
upgrades — and the insert pass must honour it.

## Open questions

- Opt-in knob, or default-on for byte-exact matches only? Default-on is what unsticks the broken repos; an exact-match gate is what makes it safe.
- Does the fold belong in `install.sh`/`init-workspace.sh` (every upgrade path) or only in `devkit-upgrade.yml` (the automated lane that is actually blocked)?
- **Case 2: is the version gate enough?** It cannot distinguish "deleted the hook before upgrading past the introducing release" from "never had it" for a repo that skips several versions at once — a common shape for the consumers furthest behind. A conservative alternative is insert-on-opt-in only (a knob, or a one-shot `--adopt-hooks` flag).
- **Case 2: where does the hook block come from?** Case 1 replaces with the current template's block for a known id. Insertion needs the block extracted from the rendered scaffold config, which is itself generated from `nix/hooks.nix` — so the extractor must read the *rendered* template, not re-derive the YAML, or the two can drift.
- Should Case 2 insert at a defined position (after its template neighbour) or append? Position affects hook execution order, which is observable for formatter hooks that rewrite files.
- Do the two cases share one pass and one report, or ship independently? Case 1 unblocks broken repos and is the more urgent half.

## Scope note

Deliberately split out of #1652, which stays a read-only guard: rewriting a preserved consumer file is a different risk class and deserves its own issue, tests and review. Case 2 is the same risk class as Case 1 — writing into a file the consumer owns — which is why it belongs here rather than in a third issue, but it is strictly weaker on safety: Case 1 can prove what it is replacing, Case 2 can only infer what it is adding.

## Related

- #1652 — the read-only guard this builds on (and its table's documented boundary)
- #1660 — shipped the `actionlint` hook, creating the first Case 2 instance and the feature-group opt-out the insert pass must honour
- #1348 / `retired_paths()` — the `PREVIOUS_PIN` version-gate pattern Case 2 mirrors
- #1145 / `migrate_root_gitignore` — precedent for surgically editing a consumer-owned file
- #1651 — why non-durable deletion is a defect, not a convenience
- #878 / #913 / #1099 — the preservation this works around, and the template diff that is today's only Case 2 signal

---

# [Comment #1]() by [c-vigo]()

_Posted on September 21, 2026 at 11:38 AM_

## Design

Resolving the six open questions before implementation. Both cases ship in one
pass; every fork is decided toward "do nothing unless the evidence is
unambiguous".

### Framing: this file is already written to

`.pre-commit-config.yaml` is preserved, but it is not untouched: five renders
already `sed -i` it on every upgrade — `render_branch_guard_model` (#1642),
`render_refs_policy` (#1282/#1633), `render_commit_types` (#1431),
`render_branch_types` (#1432) and `render_actionlint_optout` (#1660). The
reconciliation pass is a sixth member of that family, not a new risk class. What
is new is that it rewrites *structure* rather than a knob value, which is why
each case carries its own evidence gate.

### Q1 — opt-in knob, or default-on for byte-exact matches only?

**Default-on, no new knob**, for both cases.

- Case 1: the byte-exact match *is* the gate. A knob would mean "keep the block
  that breaks `prek`", and it would have to be set by the very repos that cannot
  run the upgrade far enough to read the notice.
- Case 2: default-on, but triple-gated (version + feature group + absence), and
  its durable opt-out already exists — `DEVKIT_FEATURES_DISABLED=<group>`
  (#1660), checked before the insert. Adding a second knob for the same
  intention would split the opt-out surface.

### Q2 — `install.sh`/`init-workspace.sh`, or `devkit-upgrade.yml`?

**`assets/init-workspace.sh`**, as a post-copy render beside the five above;
`devkit-upgrade.yml` only lifts the report lines, exactly as it already does for
`flake-bump:` (#1497) and `preserved-hook-drift:` (#1652).

Decisive: `devkit-upgrade.yml` commits **in the project shell with the hooks
running**, so the broken block fails the commit step. A fix living in the
workflow would run at best after the failure and would miss every other upgrade
path (`install.sh --force`, `just upgrade`, a manual re-scaffold). One
implementation in the script covers all of them and lands before the commit.

### Q3 — Case 2: is the version gate enough?

**Yes — because it is paired with a one-shot property and a durable opt-out.**
The ambiguity the issue worries about does not actually arise:

- a repo pinned *before* the introducing release cannot have deleted a hook
  devkit never shipped it. "Skipped several versions at once" is precisely the
  "never had it" case, not an ambiguous one;
- the insert fires **at most once per repo**: the same run advances the pin past
  the introducing release, so a subsequent hand-deletion is permanent — no
  re-add on the next upgrade, which is the #1651 defect this must not repeat;
- the one residual shape — a consumer who hand-added the hook themselves and
  then removed it, while still pinned below the introducing release — is covered
  by `DEVKIT_FEATURES_DISABLED`, which the pass honours.

So no `--adopt-hooks` flag: the population furthest behind is the *automated*
lane, which runs no flags. Five gates in total, mirroring `retired_prune_paths()`
(#1348):

1. a pin exists and is semver-shaped (no pin ⇒ no evidence ⇒ no write);
2. `version_lt "$PREVIOUS_PIN" "$first_release_shipping_it"`;
3. the hook's feature group is not in `DEVKIT_FEATURES_DISABLED`;
4. the hook id is absent from the consumer's file (also makes an rc→final
   upgrade a no-op);
5. the template actually ships the block, and the anchor of Q5 is locatable in
   the consumer's file — otherwise skip.

Plus the shared refusal: `precommit_render_target` (#1640) — an absent config, or
a flake-hooks consumer's `/nix/store` symlink, is never touched (that consumer
gets the hook from `nix/hooks.nix` anyway).

### Q4 — where does the hook block come from?

**From the rendered template (`$TEMPLATE_DIR/.pre-commit-config.yaml`), never
re-derived**, via one extractor used for both cases and both files:

`hook_block_range <file> <hook-id>` prefers the `# >>> devkit:<id>` /
`# <<< devkit:<id>` sentinel region #1660 introduced, and falls back to the
structural `- repo:` entry containing `- id: <hook>` when a block carries no
sentinels (the current `pymarkdown` block does not).

Preferring the sentinel region is load-bearing beyond exactness: an inserted
`actionlint` block *without* its sentinels would be invisible to
`render_actionlint_optout`, so a later `DEVKIT_FEATURES_DISABLED=actionlint`
could not excise it — the opt-out would silently stop working for exactly the
repos the insert reached.

The pass runs as the **first** `.pre-commit-config.yaml` touch of the upgrade, so
anything it writes is then subject to the same knob renders as a template copy
would be; no block needs its rendered values re-derived.

### Q5 — insert position

**A defined position, never append.** The block goes immediately after the end of
the repo entry holding its *template predecessor* hook — derived from the
template (the last `- id:` above the block), not hardcoded, so it cannot drift
from a template reorder. For `actionlint` that anchor is `shellcheck`, which is
where the template puts it.

Hook order is observable for formatter hooks that rewrite files, and an append
would place a future formatter after every hook that reads what it rewrites. If
the anchor is absent from the consumer's file, the insert is **skipped** with a
notice rather than guessed; the #878 template diff stays the fallback.

### Q6 — one pass or two PRs?

**One pass, one PR, two gates, two markers.** They share the extractor, the write
path, the report channel and the test harness; splitting would ship the same code
twice. What stays separate is the evidence and the reporting:

```text
preserved-hook-fold: pymarkdown-pre-1170 in .pre-commit-config.yaml
preserved-hook-insert: actionlint in .pre-commit-config.yaml
```

Both ride the existing stdout channel beside `preserved-hook-drift:`;
`devkit-upgrade.yml` lifts them into the step summary and a PR-body section that
is deliberately distinct from the drift one — "the upgrade **rewrote** your
preserved config, review the hunk" versus "the upgrade **could not** deliver
this, fold it in by hand".

### Case 1, concretely

The retired-block table stores the historical template text **verbatim**, keyed
`<drift id>|<hook id>|<variant>`; the fold fires only on a byte-identical match
of the whole block and replaces exactly that line range with the current
template's block for the same hook id. Field check across the local consumer
fleet, which is what settled the strictness question:

- two repos carry the 0.3.0–1.3.x block byte-for-byte ⇒ folded;
- one repo added its own vendored-doc paths to the block's `exclude:` ⇒ **no
  match, no write**, and the #1652 warning stands. Folding it would have deleted
  their exception list — which is the whole reason the gate is a byte-match and
  not a `repo:`-line match.

A Renovate-bumped `rev:` also falls through to the warning. That is deliberate
under-folding: the block still gets a `file:line` notice, and no heuristic
decides what is devkit's text and what is the consumer's.

Only the first occurrence is folded; a second copy keeps warning.

### Preview honesty

`--preview` reports the planned fold/insert (like the `DEVKIT_LICENSE` and trunk
sections already do) and **suppresses** the `preserved-hook-drift:` line for a
block the fold will repair — otherwise the preview would tell the consumer to
hand-fold something the run fixes for them.

### Table seed rows

- fold: `pymarkdown-pre-1170` → the `jackdewinter/pymarkdown` block as shipped
  0.3.0 → 1.3.x (the shape every realistically-pinned consumer received);
- insert: `1.16.0 actionlint actionlint` — `<first release shipping it> <hook id>
  <feature group>`. The version is the next minor, since #1660 sits unreleased
  in `## Unreleased`; if the train renumbers, the row moves with it (a higher
  number only under-inserts, and gate 4 makes a wrong-direction miss a no-op).


---

# [Comment #2]() by [c-vigo]()

_Posted on September 21, 2026 at 02:05 PM_

Resolved by #1665 (merged to `dev` as 3c151544).

Both cases ship in one pass, `reconcile_preserved_hooks apply|plan` in `assets/init-workspace.sh`, run as the first `.pre-commit-config.yaml` touch of the upgrade — before `devkit-upgrade.yml` reaches its commit step, which is what the broken repos need.

**Fold** is gated on a byte-identical match against the historical template block. Field-tested against real consumer configs: two repos carrying the pre-#1170 `jackdewinter/pymarkdown` block folded cleanly; a third that had extended the block's `exclude:` with vendored-doc paths was **declined**, leaving the #1652 warning standing. Folding that third would have deleted their exception list — the concrete justification for the byte-match gate.

**Insert** mirrors the `retired_paths()` version gate (#1348): it fires only when the pin predates the release that first shipped the hook, at most once per repo, so a later hand-deletion stays durable (#1651). `DEVKIT_FEATURES_DISABLED` is honoured first, and the block is read from the *rendered* template preferring the `# >>> devkit:<id>` sentinels, so an inserted hook stays excisable by its own feature opt-out.

Both report on the machine-readable channel #1652 opened, as `preserved-hook-fold:` / `preserved-hook-insert:`.

**Release-time watch item:** the insert table's first row is `1.16.0 actionlint`, derived from "#1660 is an unreleased \`feat\`, so the next minor". If the next train is renumbered, that row must move with it. A too-high number only under-inserts, which is the safe direction, and the "hook already present" gate makes a wrong-direction miss a no-op.

Out of scope: no new `.vig-os` knob, and the two pre-0.3.0 pymarkdown shapes are not in the fold table (no consumer is pinned that far back) — they fall through to the #1652 warning.

