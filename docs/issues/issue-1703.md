---
type: issue
state: closed
created: 2026-09-25T09:29:07Z
updated: 2026-09-25T15:31:04Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1703
comments: 2
labels: bug, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:42.895Z
---

# [Issue 1703]: [[BUG] Template-tree walks silently no-op when TEMPLATE_DIR carries a trailing slash](https://github.com/vig-os/devkit/issues/1703)

### Description

Three template-tree walks in `assets/init-workspace.sh` derive a workspace path with `rel="${src_path#"$src_dir"/}"` after `find -L "$src_dir" …`:

- `sweep_scaffold_writable` (the `chmod u+w` sweep)
- the `--preview` report walk
- the `+x` sweep near the end of the run

If `$src_dir` (`TEMPLATE_DIR` or the smoke overlay dir) carries a trailing slash, GNU `find` normalises its output to `/…/workspace/a.txt`, the prefix `/…/workspace//` never strips, `rel` stays absolute, the mapped destination never exists, and the walk silently does nothing: exit 0, no warning.

The #1693 substitution routine had the same latent bug; it was caught in review and fixed there with a one-line `local src_dir="${1%/}"` plus a trailing-slash BATS test. The other three walks still have it. No in-repo caller passes a trailing slash today (only `init-workspace.sh` reads `TEMPLATE_DIR`; BATS passes none), so this is latent, but the failure mode is silent.

### Steps to Reproduce

1. `TEMPLATE_DIR="$PWD/assets/workspace/"` (trailing slash), scaffold with the BATS helper env into an empty dir
2. Make a template-shipped destination read-only before an upgrade, or inspect `--preview` output

### Expected Behavior

Each walk strips a trailing slash from its source dir (`${1%/}`) and behaves identically with or without it; one BATS test per walk pins it.

### Actual Behavior

The walk maps every file to a non-existent absolute-under-absolute path and skips it.

### Environment

- **OS**: any
- **Container Runtime**: n/a
- **Image Version/Tag**: dev
- **Architecture**: any

### Additional Context

Found by the #1693 review. The cleanest fix is the shared "template-shipped candidates" emitter proposed in #1700, which would normalise the source dir once for every consumer of the walk.

### Possible Solution

Normalise once at the top of each walk (`src_dir="${src_dir%/}"`), or factor the walk into the shared emitter from #1700 and normalise there.

### Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 01:24 PM_

## Triage 2026-09-25: confirmed in all three walks; one-line root fix

Verified in a scratch dir: `find -L /a/src/ -mindepth 1 -type f` prints `/a/src/a.txt`, so `${p#"/a/src/"/}` (double slash) never strips, `rel` stays absolute, `dest="$WORKSPACE_DIR//a/src/a.txt"` never exists, and each walk exits 0 having done nothing.

The preview walk (~L2795) and the `+x` sweep (~L3739) read the global `TEMPLATE_DIR` directly, and `sweep_scaffold_writable` is called with it (~L3222/L3225), so normalising once at the single assignment site — `TEMPLATE_DIR="${TEMPLATE_DIR%/}"` right after L54 — fixes all three plus any future walk; `dirname` at ~L1555 and the rsync `"$TEMPLATE_DIR/"` source are unaffected. The shared emitter from #1700 additionally normalises its own `src_dir` argument (the smoke overlay path is passed explicitly).

**Disposition:** implemented together with #1700 in one PR. Red test: `TEMPLATE_DIR=".../assets/workspace/"` (trailing slash) → a read-only template-shipped file becomes writable, a template `*.sh` is `+x`, and `--preview` lists non-empty ADDED/OVERWRITTEN — mirrors the #1693 test at `init-workspace.bats` ("a TEMPLATE_DIR with a trailing slash still substitutes placeholders").


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 03:31 PM_

Fixed in #1715, merged to `dev` (ecb8f8d5): `TEMPLATE_DIR` is normalised once at its only assignment, and the shared emitter normalises its own source argument; a BATS test pins all three walks against a trailing slash.

