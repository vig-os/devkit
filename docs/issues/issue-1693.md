---
type: issue
state: closed
created: 2026-09-25T07:49:12Z
updated: 2026-09-25T09:57:12Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1693
comments: 2
labels: refactor, priority:low, area:image, area:workspace, effort:medium, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:46.056Z
---

# [Issue 1693]: [[REFACTOR] Retire the image-only placeholder manifest in favour of the batched substitution path](https://github.com/vig-os/devkit/issues/1693)

### Description

`assets/init-workspace.sh` has two code paths for placeholder substitution
(`{{SHORT_NAME}}`, `{{ORG_NAME}}`, `{{GITHUB_REPOSITORY}}`):

1. The **manifest fast path**: `flake.nix` (around line 1476) greps the
   template at image build time and bakes the file list into
   `/root/assets/.placeholder-manifest.txt`; the script then runs one
   `sed -i` **per manifest entry** (~117 forks). `test_image.py::
   test_placeholder_manifest_baked` pins that the file exists.
2. The **fallback** (manifest absent): since #1687 one batched
   `grep -rl --null --exclude-dir=.git … | xargs -0 -r sed -i …`.

The fast path exists only inside the image (its path translation hardcodes
`/root/assets/workspace`), consumers reach it through `install.sh` → the
container, and BATS never exercises it (host-side runs hit the fallback).
Measured in #1687: 117 per-file `sed -i` ≈ 2.6s vs ≈ 0.15s for the batched
form — the "fast" path is 15-20x **slower** than the fallback it was meant
to beat, and it is the one code path the suite does not cover.

Retiring it leaves one substitution routine that is faster than both,
covered by 300 BATS tests, and identical on host and in the image. Deleted
with it: the flake build step, the manifest test, and the host/image
divergence.

### Acceptance Criteria

- [ ] `init-workspace.sh` has one substitution path (the batched
      `grep -rl | xargs sed -i` form); the `MANIFEST_FILE` branch, the
      `MANIFEST_FILE` variable and the "Using build-time manifest" /
      "Manifest not found" messages are gone
- [ ] The `.placeholder-manifest.txt` build step is removed from `flake.nix`
      and the image no longer ships the file (`test_placeholder_manifest_baked`
      inverted or replaced by a negative pin)
- [ ] A scaffold rendered in the container (`install.sh` / `test_integration`)
      is byte-identical to one rendered by the previous image, permissions
      included — the #1687 WP2 proof method (`diff -r` + `find -printf
      '%m %y %p'`) applied across the old/new **image**, not just host-side
- [ ] `init-workspace.bats` 300/300, `install.bats` 95/95, `test_image.py`
      and `test_integration.py` green in CI
- [ ] CHANGELOG `Changed` entry (consumer-visible: the image changes and the
      substitution log lines change)

### Implementation Notes

- The batched form's selection semantics (regular files, `.git/` excluded,
  symlinks inside the tree not followed, binaries matched) are documented
  inline at the fallback since #1687 — keep that comment as the routine's
  contract.
- `grep -r` walks the whole workspace, not just the template tree; in the
  image that is the consumer's repo. The manifest path only touched files the
  template shipped. Confirm the batched walk cannot rewrite a *consumer* file
  that happens to contain a `{{…}}` token — the old fallback had the same
  reach and no report ever came, but a scoped walk (`$TEMPLATE_DIR`-derived
  paths, like `sweep_scaffold_writable` does) would be the conservative
  choice and is also cheaper. Decide and record it.
- Check `docs/` and the `#718` / `#802` history for prose that describes the
  manifest so it does not go stale.

### Related Issues

- Follows #1687 (WP2 notes flagged this as the follow-up); PR #1690
- Introduced by #718 / #802

### Priority

Low

### Changelog Category

Changed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 09:47 AM_

Correcting the premise before the fix lands, because the numbers in the issue do
not survive measurement.

**The manifest has 13 entries, not ~117.** `assets/workspace/` is 117 files, but
only 13 of them carry a substitution token, and the manifest is grepped from that
tree — so the "~117 forks" figure counted the template, not the manifest.

**Speed is noise.** Timed on a clean tree: manifest path **31 ms**, batched
fallback **16 ms**. Both are irrelevant against a ~270 ms scaffold. The
"15-20x slower" framing came from applying #1687's 117-file `sed -i` measurement
to a list that is 13 entries long. The fast path is not the disaster the issue
describes, and "it is slower than the fallback" is not a reason to retire it.

**The real defect is scope, and it is in the survivor.** The batched fallback
greps `$WORKSPACE_DIR`. In the image that is the consumer's mounted repo,
`.venv` and `node_modules` included. Any consumer-owned file carrying a literal
`{{SHORT_NAME}}`, `{{ORG_NAME}}` or `{{GITHUB_REPOSITORY}}` is rewritten in
place — on the first scaffold, and again on **every upgrade**. Reproduced with
seeded files: a `docs/*.tmpl` holding all three tokens comes back as
`name: testproj / org: test / repo: test/repo`. The manifest path never had that
reach, so retiring it and keeping the fallback as-is would have made the
consumer-facing behaviour strictly worse, not better.

So the change is not "delete the fast path" but **one routine, scoped to the
files devkit ships**, derived exactly as `sweep_scaffold_writable` derives its
`chmod` set (template tree → workspace destinations), plus the smoke overlay
when one was applied. That answers the implementation note's open question:
the scoped walk is the conservative choice *and* the cheaper one — on a
7.4k-file consumer tree, **405 ms → 38 ms**.

Acceptance criteria are otherwise unchanged and all met, except criterion 3
(old-image vs new-image `diff -r` + `%m %y %p`), which needs the PR's image
built; the host-side equivalent is clean across all four modes, `--smoke-test`,
and a Node scaffold with `DEVKIT_LICENSE=proprietary`, and the image-level run
follows on the CI artifact.

One scope note for the record: `docs/` carries no prose about the manifest. The
only mentions are in `docs/issues/issue-718.md`, `docs/issues/issue-1687.md`,
`docs/pull-requests/pr-802.md` and `pr-813.md` — historical records of those
changes — and the released `CHANGELOG` entry for #718. None are rewritten.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 09:57 AM_

Shipped to `dev` in #1707 with the old/new image byte-identity proof in the PR comments. Follow-ups: #1700 (the chmod sweep walks the baked .venv), #1703 (trailing-slash walks).

