---
type: issue
state: closed
created: 2026-10-05T06:56:38Z
updated: 2026-10-05T07:30:41Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1817
comments: 1
labels: bug, priority:low, effort:small, area:testing, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-05T08:48:20.502Z
---

# [Issue 1817]: [clean-test-containers misses leftover test-devcontainer-* image-test containers](https://github.com/vig-os/devkit/issues/1817)

### Description

`just clean-test-containers` only removes containers matching `name=workspace-devcontainer`, which are the ones the devcontainer fixtures create. The image-test fixture `test_container` (`tests/conftest.py:246`) names its containers `test-devcontainer-<epoch>`. When a `test_image.py` run is killed before fixture teardown, those containers are left behind and the recipe never matches them.

### Steps to Reproduce

1. Start `just test-image` (or `uv run pytest tests/test_image.py`) and kill it before teardown.
2. `podman ps -a` shows an exited `test-devcontainer-<epoch>` container.
3. `just clean-test-containers` prints `[*] No lingering test containers found`.

### Expected Behavior

The recipe removes leftover containers from every test fixture, `test-devcontainer-*` included.

### Actual Behavior

Four exited (137) `test-devcontainer-*` containers, 5 weeks to 2 months old, survived the recipe and had to be removed by hand with `podman rm`.

### Environment

Local, rootless podman.

### Possible Solution

Also collect `podman ps -a --filter "name=^test-devcontainer-"` in the `clean-test-containers` recipe (`justfile`).

### Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on October 5, 2026 at 07:30 AM_

Fixed by #1818 (merged to `dev` as 6ee5d27d); reaches `main` with the next release train.

