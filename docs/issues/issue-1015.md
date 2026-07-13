---
type: issue
state: open
created: 2026-07-13T12:24:24Z
updated: 2026-07-13T12:24:24Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1015
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-13T15:17:51.531Z
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
