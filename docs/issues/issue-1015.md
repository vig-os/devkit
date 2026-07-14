---
type: issue
state: closed
created: 2026-07-13T12:24:24Z
updated: 2026-07-13T16:17:31Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1015
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T04:57:29.449Z
---

# [Issue 1015]: [fix(workspace): install.sh "Next steps" message is not mode-filtered for direnv](https://github.com/vig-os/devkit/issues/1015)

Found during 1.1.0-rc1 validation (PR #1014).

`install.sh` only special-cases `bare` when printing the post-install "Next steps":

```sh
if [ "$MODE" = "bare" ]; then
    echo "  2. Run 'just help' ..."
else
    echo "  2. Open in VS Code - it will detect .devcontainer/ and offer to reopen in container"
fi
```

`direnv` therefore falls into the `else` branch and tells the user to open a
`.devcontainer/` that the direnv scaffold never created (and that
`--prune-devcontainer` may have just removed).

**Expected:** a `direnv` deploy points the user at the direnv entrypoint
(`direnv allow` / `nix develop`), not at VS Code + `.devcontainer/`.

Cosmetic (nothing breaks), but the upcoming `commit-action` pilot runs in
direnv mode and will hit this on first install.

Refs: #988
---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 04:17 PM_

Fixed by #1018 (commit `e129112f` — `fix(workspace): mode-filter the install.sh next-steps message`), released in [1.1.0](https://github.com/vig-os/devkit/releases/tag/1.1.0).

A `direnv` install now prints the direnv entrypoint (`direnv allow` / `nix develop`) instead of pointing at a `.devcontainer/` the scaffold never created. Covered by the RED test in `0778aa8d`.

