---
type: issue
state: closed
created: 2026-09-25T15:31:27Z
updated: 2026-09-25T18:08:15Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1716
comments: 2
labels: chore, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:40.626Z
---

# [Issue 1716]: [[CHORE] Derive the --preview walk's prunes from COPY_PRUNE_NAMES](https://github.com/vig-os/devkit/issues/1716)

### Chore Type

Refactoring / Technical debt

### Description

#1700 made `COPY_PRUNE_NAMES=(.git .venv)` in `assets/init-workspace.sh` the single source of truth for the copy step's prunes: both rsync copies and the shared `emit_template_candidates` emitter (the `u+w` sweep, the substitution pass, the `+x` sweep) derive from it. One template walk was deliberately left out: the `--preview` classifier (around line 2796), which still hardcodes

```bash
find -L "$TEMPLATE_DIR" -type f ! -path "*/.git/*" ! -path "*/.venv/*" ! -path "*/docs/issues/*" ! -path "*/docs/pull-requests/*" -print0
```

It was left out because it needs the *relative* path for destinations that do not exist yet (to classify ADDED vs OVERWRITTEN) and carries two extra report-only excludes, whereas the emitter emits workspace destination paths. It is nonetheless a second copy of the prune knowledge, and its semantics differ: `! -path "*/.venv/*"` skips only the *contents* of a `.venv` directory, while the emitter (like rsync) prunes any entry *named* `.venv` or `.git`, so a top-level file with one of those names is classified by the preview but never copied.

### Acceptance Criteria

- [ ] The preview walk derives its `.git`/`.venv` prunes from `COPY_PRUNE_NAMES` (basename prune, any depth), keeping its own `docs/issues` / `docs/pull-requests` report excludes
- [ ] A BATS test pins that a template entry named `.git` or `.venv` (file or directory, at any depth) is neither copied nor listed by `--preview`
- [ ] Existing preview tests (#1196 and the trailing-slash test from #1703) stay green

### Implementation Notes

Either give the emitter an optional mode that emits source-relative paths (so the preview can map to the destination itself), or factor only the prune-expression construction into a helper both walks call. Prefer whichever keeps `init-workspace.sh` smaller.

### Related Issues

- #1700 / #1703 (the emitter and the SSoT), noted in the #1715 review
- #1693 (the substitution routine's scope)

### Priority

Low

### Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 05:00 PM_

## Triage 2026-09-25: implement, smallest design (consume the emitter, derive `rel` from `dest`)

Checked the preview's exclude set pairwise against the copy step: `PRESERVE_FILES`, `MODE_CONFIG_EXCLUDES` and the trunk-excluded workflows are in sync; only the `.git`/`.venv` handling diverges (path form vs basename prune — a *file* named `.git` or `.venv` at any depth is reported ADDED but never copied). A second, undocumented divergence: `! -path "*/docs/issues/*" ! -path "*/docs/pull-requests/*"` came from #951 to mirror rsync excludes that #1466 later deleted; the template ships neither directory, so they are dead predicates with a stale rationale.

`dest → rel` is lossless (both sides glue with the same `"$WORKSPACE_DIR/"`), so the preview can consume `emit_template_candidates "$TEMPLATE_DIR" -type f …` directly and strip the prefix — no emitter mode, no prune-builder helper, and the `-L` / `-mindepth 1` / prune semantics come for free. Cost: the emitter is defined after the top-level report block, so it moves up next to `COPY_PRUNE_NAMES` (a pure move).

RED test modelled on the #951 `.venv` over-report test: template gets a file `.git` and a nested file `pkg/.venv`; `--preview --force` must not print `  +  .git` / `  +  pkg/.venv` (`refute_line`, never `--partial ".git"` — `.github/...` rows contain it), and after a real run neither exists in the workspace. Traversal order is unchanged, so the byte-asserted report rows stay identical; keep `-type f` (the emitter defaults to `-true`). ~1 h, no changelog.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 06:08 PM_

Fixed in #1722, merged to `dev` (307bb7d3): the `--preview` classifier now consumes `emit_template_candidates` and derives the relative path from the emitted destination, so its prunes are `COPY_PRUNE_NAMES` by construction; the report is byte-identical on the pristine template.

