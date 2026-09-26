---
type: issue
state: closed
created: 2026-09-25T08:46:41Z
updated: 2026-09-25T15:31:01Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1700
comments: 2
labels: bug, priority:low, area:image, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:43.518Z
---

# [Issue 1700]: [[BUG] sweep_scaffold_writable walks the image's baked .venv and chmods colliding consumer paths](https://github.com/vig-os/devkit/issues/1700)

### Description

`sweep_scaffold_writable "$TEMPLATE_DIR"` in `assets/init-workspace.sh` walks the template tree with `find -L … -type f` and no path excludes, maps each file into `$WORKSPACE_DIR`, and `chmod u+w`s it. In the image, `flake.nix` bakes a `.venv` **inside** `/root/assets/workspace` (around line 1498) that the copy step's `rsync --exclude='.venv'` deliberately never ships. The sweep does not know that: it walks the baked venv (hundreds of paths) and, wherever a consumer's own `.venv` happens to have a file at the same relative path, `chmod u+w`s a consumer file.

Harmless as far as anyone has observed (a `u+w` on a venv file changes nothing that matters), but it is the same blind spot #1693 closed for placeholder substitution: a template-derived walk that does not apply the copy step's excludes reaches files devkit did not ship. It also does wasted work on every scaffold and upgrade in the container.

### Steps to Reproduce

1. In the image, `find /root/assets/workspace/.venv -type f | wc -l` (non-zero)
2. Scaffold into a workspace that has a `.venv` with a colliding path, e.g. `.venv/pyvenv.cfg` set `u-w`
3. Observe it is `u+w` after `init-workspace.sh`

### Expected Behavior

The sweep touches only files the template ships, i.e. it applies the same excludes as the copy step (`.venv`, and anything else `EXCLUDE_ARGS` carries).

### Actual Behavior

The sweep walks the baked `.venv` and chmods consumer paths that collide with it.

### Environment

- **OS**: any
- **Container Runtime**: podman
- **Image Version/Tag**: dev
- **Architecture**: AMD64

### Additional Context

Noted in the #1693 spike (risk register item 5). #1693's substitution walk excludes `.venv` explicitly; the sweep should share the derivation so the two cannot drift — a single "template-shipped candidates" emitter that both consume.

### Possible Solution

Factor the candidate walk (`find -L "$src_dir" -mindepth 1 -type f -not -path "$src_dir/.git/*" -not -path "$src_dir/.venv/*" -print0`, mapped into `$WORKSPACE_DIR`) into one helper used by both `sweep_scaffold_writable` and the #1693 substitution routine; derive the excludes from the copy step's `EXCLUDE_ARGS` rather than a second literal list.

### Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 01:24 PM_

## Triage 2026-09-25: confirmed, solved together with #1703 in one PR

Verified on `dev`:

- `sweep_scaffold_writable` (`assets/init-workspace.sh` ~L3203) walks `find -L "$src_dir" -mindepth 1 -print0` with **no excludes** — and deliberately **no `-type f`** either (it chmods directories too; the issue text's `-type f` is inaccurate and the directory entries must be kept).
- `flake.nix` bakes `$out/root/assets/workspace/.venv` (~L1480, `python3 -m venv` + `pyvenv.cfg`/`activate` rewrite), which the copy step excludes by literal flag: `rsync … --exclude='.git' --exclude='.venv'` in both the normal (~L3184) and the smoke (~L3112) branch.

**Design correction:** "derive the excludes from `EXCLUDE_ARGS`" does not work as written. `.git`/`.venv` — the actual bug — are literal rsync flags and never in `EXCLUDE_ARGS`; `EXCLUDE_ARGS` is built after the `--preview` walk runs and is unset in the smoke branch; and feeding the preserved-file / mode excludes into the chmod sweep would stop preserved consumer files getting `u+w`, an unrequested behaviour change. The SSoT worth having is a `COPY_PRUNE_NAMES=(.git .venv)` array consumed by both rsync calls and by one shared candidate emitter (`emit_template_candidates <src_dir> [find-predicates…]`, `-name … -prune` at any depth, NUL output, `${1%/}` normalisation) that `sweep_scaffold_writable` (no type predicate), `emit_substitution_candidates` (#1693, `-type f`) and the `+x` sweep (`-type f -name '*.sh'`) all consume. The `--preview` walk stays separate (it needs `rel` for absent destinations and carries extra `docs/issues|pull-requests` excludes); it only needs the trailing-slash fix from #1703.

Red tests first in `tests/bats/upgrade-atomicity.bats`: a template `.venv/pyvenv.cfg` (and a nested `pkg/.venv/…`) whose workspace twins are `0444` must stay `0444` after a run.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 03:31 PM_

Fixed in #1715, merged to `dev` (ecb8f8d5): one pruned candidate emitter shared by the writable sweep, the substitution pass and the +x sweep, with `COPY_PRUNE_NAMES` as the single source of truth for both rsync copies.

