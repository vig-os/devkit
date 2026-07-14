---
type: issue
state: closed
created: 2026-07-14T08:06:32Z
updated: 2026-07-14T10:23:41Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1036
comments: 3
labels: feature, priority:medium, area:workspace, effort:medium, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:31.570Z
---

# [Issue 1036]: [[FEATURE] Ship a provenance banner in scaffolded assets (managed-vs-yours + where to file issues)](https://github.com/vig-os/devkit/issues/1036)

### Description

Ship a provenance banner in every comment-capable file the scaffold writes into a
downstream repo, stating (a) that devkit manages the file, (b) whether an upgrade
will overwrite it, (c) where to customize instead, and (d) where to file issues.

The banner must be **generated from `PRESERVE_FILES`**, not hand-written per file.

### Problem Statement

A downstream repo (and especially an *agent* working in one) has no in-band signal
that devkit exists. The scaffold ships no `CLAUDE.md`. It ships a `justfile`, 13
workflows, `.githooks/`, `.devcontainer/scripts/`, and ~30 `.claude/skills/**/SKILL.md`
files — all of which `rsync` silently clobbers on the next `--force` upgrade, and
none of which say so.

Two consequences, both already observed:

1. **Edits to managed files are silently destroyed.** This is not hypothetical — it
   is the root cause of #878 (`.pre-commit-config.yaml`: a template overwrite
   "silently destroyed" repo-specific `exclude:` patterns, so the hook suite then
   rewrote files it must never touch) and #913 (`.typos.toml`: overwrite destroyed
   curated spell-check exceptions). Both were fixed by *demoting the file into
   `PRESERVE_FILES`* — i.e. we bought safety by giving up managed-ness. That is an
   expensive, reactive fix; a banner is the cheap preventive one.
2. **Bugs never flow back upstream.** A downstream agent that hits a broken recipe or
   a missing tool patches it locally. The patch dies on the next upgrade *and* devkit
   never learns. Devkit's entire value is that N repos share one substrate; if defect
   reports don't route back to the substrate, every consumer diverges.

The existing state also shows hand-written banners rot. `assets/workspace/.devcontainer/justfile.devc:1-4` is the only downstream asset with one:

```
# DEVCONTAINER RECIPES - DO NOT EDIT
# Managed by vigOS devcontainer. Customizations go in root justfile.
```

It is stale (`vigOS devcontainer`; the product is devkit and the manifest keys are
`DEVKIT_*`) and **actively wrong**: the root `justfile` is *not* in `PRESERVE_FILES`,
so it is overwritten on upgrade — `init-workspace.sh:1007` says so in a comment. The
banner points users at a file that will destroy their work. The correct target is
`justfile.project`.

### Proposed Solution

**1. Two banner variants, ~2 lines, a pointer and not a policy restatement.**

Managed (overwritten on upgrade):

```
# Managed by vigOS devkit — regenerated on upgrade; local edits are lost.
# Customize in justfile.project. Bugs / missing tools: https://github.com/vig-os/devkit/issues
```

Preserved (seeded once, consumer owns it):

```
# Seeded by vigOS devkit — yours to edit; upgrades never overwrite this file.
# Bugs / missing tools: https://github.com/vig-os/devkit/issues
```

Reuse the existing house style — devkit's own generated docs already carry a banner
(`README.md:1`, `<!-- Auto-generated from ... DO NOT EDIT DIRECTLY -->`), round-tripped
through the `.j2` source. This applies that proven convention to the downstream assets,
where it was never applied.

**2. Deliberately omit the version.** It already lives in `.vig-os` as `DEVKIT_VERSION`
(SSoT). Stamping it per-file would churn every banner on every release, flooding upgrade
diffs and polluting the preserved-file-vs-template diff report (`init-workspace.sh:481`).
Banners stay byte-stable across releases.

**3. Generate, don't duplicate — a `Banner` transform in `scripts/transforms.py`.**
`scripts/sync_manifest.py` already rewrites `assets/workspace/` on every commit behind a
`pass_filenames: false` pre-commit gate that fails the commit on drift. Deriving the
banner (and its managed/preserved variant) from `PRESERVE_FILES` there makes divergence
*structurally impossible* rather than merely detectable — and satisfies the SSoT rule. A
banner hand-typed into 30 files would be a second copy of the managed/preserved
classification and would rot exactly the way `justfile.devc` did.

**4. Fix the `justfile.devc` banner** to point at `justfile.project`.

**5. Explicit skip-list for strict JSON** (`renovate.json`, `.github/renovate-default.json`,
`.claude/worktrees.json`, `.pymarkdown`) — no comment syntax. `devcontainer.json` and
`.vscode/settings.json` are JSONC and take `//` fine. Coverage is knowingly partial.

### Alternatives Considered

- **Checksum/hash manifest for real downstream drift detection.** Today consumer drift is
  wholly invisible: no `devkit update`, no hash check, nothing until `--force` clobbers.
  A manifest would genuinely *detect* drift, but it is a large mechanism and still only
  helps at upgrade time, *after* the bad edit. Complementary, not competing — the banner
  prevents the edit; do it first, and open the manifest separately if drift persists.
- **Ship a `CLAUDE.md` downstream carrying the policy.** Weaker: one file is easy to miss,
  it doesn't travel with the file being edited, and it doesn't tell you *which* files are
  managed. Also collides with #927 (retiring per-repo `.claude/` copies).
- **A banner in the capability modules (`nix/modules/`).** Rejected — see below.

### Additional Context

**Modules need a runtime pointer, not a header — file separately.** The capability modules
(#884, `nix/modules/`) contribute **zero files** to a consumer repo; they fold into the
dev-shell via `mkProjectShell`. A downstream agent never opens `nix/modules/native.nix`;
it hits `command not found`. The pointer must therefore live where the failure surfaces —
the module contract already exposes a `shellHook` field, and `flake.nix:246` already
defaults it to an `echo`. Follow-up issue, not this one.

The governing principle: **banner the things that land in the consumer's tree; runtime-pointer
the things that stay upstream.**

Related: #878, #913 (the two silent-clobber bugs this prevents), #927 (per-repo `.claude/`
copies — interacts with bannering the `SKILL.md` files).

### Impact

- **Who benefits:** every downstream consumer, and specifically coding agents working in one —
  the banner is the only in-band channel they have.
- **Backward compatible.** Comment-only change to scaffold assets; no behaviour change. Consumers
  see the banners appear on their next `--force` upgrade.
- ~30 files gain two comment lines. On a short workflow file that is a visible fraction of the
  content — accepted cost.

### Acceptance Criteria

- [ ] `Banner` transform in `scripts/transforms.py`, driven by `PRESERVE_FILES` as the single
      source of truth for the managed/preserved variant
- [ ] Banner applied to all comment-capable files under `assets/workspace/`, both variants correct
- [ ] Strict-JSON skip-list is explicit and documented
- [ ] `justfile.devc` banner corrected to point at `justfile.project` (not the root `justfile`)
- [ ] Banner contains no version string (`.vig-os` remains the version SSoT)
- [ ] `sync-manifest` pre-commit hook fails on a hand-edited or missing banner
- [ ] TDD compliance (see .claude/skills/tdd/SKILL.md)

### Changelog Category

Added

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 09:31 AM_

Implemented in #1043 (merged to dev): 94 files bannered (86 managed + 8 preserved), variant derived from PRESERVE_FILES via the Banner transform + sync-manifest (drift structurally impossible, tamper-verified), justfile.devc banner corrected, explicit strict-JSON/JSONC skip-list documented in _BANNER_SKIP. Follow-up candidates noted in the PR: JSONC coverage via a check-json exclude, justfile.local PRESERVE_FILES reclassification, banner for the node justfile.project seed.

---

# [Comment #2]() by [c-vigo]()

_Posted on July 14, 2026 at 09:34 AM_

Reopening — closure was premature: PR #1043 is implemented and fully green but awaits the required code-owner review from @gerchowl (CODEOWNERS: .claude/skills/). Will close when it merges.

---

# [Comment #3]() by [c-vigo]()

_Posted on July 14, 2026 at 10:23 AM_

Now truly merged to dev in #1043 (code-owner approved): 94+ files bannered with the PRESERVE_FILES-derived Banner transform, sync-manifest tamper gate, corrected justfile.devc banner, documented skip-list. The newly scaffolded docs/DOWNSTREAM_RELEASE.md (#1046/#1051) picked up its banner in the same merge.

