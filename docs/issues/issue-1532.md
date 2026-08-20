---
type: issue
state: closed
created: 2026-08-17T08:36:48Z
updated: 2026-08-17T12:09:21Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1532
comments: 1
labels: bug, priority:medium, area:ci, effort:small, semver:patch, security
assignees: none
milestone: 1.11.0
projects: none
parent: none
children: none
synced: 2026-08-18T03:02:14.466Z
---

# [Issue 1532]: [[BUG] devkit-upgrade fetches install.sh from main while installing a pinned $TARGET](https://github.com/vig-os/devkit/issues/1532)

## Description

The scaffolded `devkit-upgrade.yml` fetches `install.sh` from the **`main`**
branch while installing a **pinned** `$TARGET` version:

```yaml
# .github/workflows/devkit-upgrade.yml (managed)
curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh \
  | bash -s -- --force --version "$TARGET" --skip-preflight --docker . \
  | tee "$RUNNER_TEMP/install.log"
```

Two problems, one line:

1. **Version inconsistency.** The installer comes from `main` tip; the payload
   it scaffolds comes from `$TARGET`. Nothing guarantees the two agree. A
   `main`-tip installer paired with an older release's scaffold is an untested
   combination, and it is the combination every consumer's *scheduled* upgrade
   run gets whenever `main` is ahead of the latest release — i.e. most of the
   time.

2. **Unpinned remote code with write access.** Any push to devkit's `main`
   immediately changes what runs in every consumer repo's upgrade job, which
   holds `contents: write` on a branch it creates and opens a PR from. There is
   no review gate between a `main` commit and execution across all consumers.

Found via a Scorecard `Pinned-Dependencies` alert (`downloadThenRun not pinned
by hash`) on `vig-os/commit-action`, but the finding is upstream — the file is
devkit-managed and regenerated on upgrade, so consumers cannot fix it locally.

## Steps to Reproduce

1. In any devkit consumer, let `devkit-upgrade.yml` run (schedule or dispatch)
   while devkit's `main` is ahead of the latest release tag.
2. Observe the `Run the devkit upgrade (install.sh --force)` step.
3. The installer executed is `main`'s, not `$TARGET`'s.

Equivalently, read the managed workflow: the URL is hardcoded to `/main/`
while `--version "$TARGET"` is resolved from the release poll.

## Expected Behavior

The installer and the scaffold payload come from the same ref — fetch
`install.sh` from the target release tag:

```yaml
curl -sSfL "https://raw.githubusercontent.com/vig-os/devkit/refs/tags/${TARGET}/install.sh" \
  | bash -s -- --force --version "$TARGET" --skip-preflight --docker .
```

## Actual Behavior

`install.sh` is always fetched from `main`, decoupled from `$TARGET`.

## Environment

- **OS**: `ubuntu-24.04` GitHub-hosted runner
- **Container Runtime**: n/a (host, `--docker`)
- **Image Version/Tag**: observed from `commit-action` @ `DEVKIT_VERSION=1.10.0`, `DEVKIT_MODE=direnv`
- **Architecture**: AMD64

## Additional Context

- Consumer alert: `vig-os/commit-action` code-scanning alert #28, Scorecard
  `PinnedDependenciesID`, `.github/workflows/devkit-upgrade.yml:231`.
- Note the tag fix does **not** clear the Scorecard alert — Scorecard wants a
  commit SHA, and a tag is not a hash. SHA-pinning a *self-upgrading* installer
  is circular by construction (the pin would itself need bumping by the thing it
  pins), so the alert is expected to stay and be dismissed on the consumer side.
  The value here is version consistency and removing the `main`-tip execution
  window, not the score.
- Tags are mutable in principle; if that matters, `--version` verification
  inside `install.sh` (assert the fetched installer's own version equals
  `$TARGET`) is the stronger follow-up.

## Possible Solution

Change the hardcoded `/main/` in the managed `devkit-upgrade.yml` template to
`/refs/tags/${TARGET}/`, and keep a `main` fallback only if a target predates
the tag layout. `$TARGET` is already in the step's `env:` block, so no new
plumbing is needed.

## Changelog Category

Security

---

# [Comment #1]() by [c-vigo]()

_Posted on August 17, 2026 at 12:09 PM_

Fixed in #1540 (merged to dev): the managed devkit-upgrade.yml now fetches install.sh from refs/tags/${TARGET} instead of main, so installer and scaffold payload always move together and the main-tip execution window is gone. No main fallback: verified across all 61 tags that every version the resolve regex admits carries a root-level install.sh (sole miss 0.1 is unreachable). SHA-pinning and installer self-verification stay out of scope per the issue — the Scorecard alert on consumers is expected to remain and be dismissed there. Ships with 1.11.0; consumers pick it up one train later.

