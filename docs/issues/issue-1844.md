---
type: issue
state: open
created: 2026-10-06T22:33:35Z
updated: 2026-10-06T22:33:35Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1844
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-07T08:29:20.590Z
---

# [Issue 1844]: [[BUG] install.sh preflight treats GitHub 404 JSON as the default branch name when origin does not exist yet](https://github.com/vig-os/devkit/issues/1844)

## Description

`install.sh` preflight takes the **GitHub API error body** as the default branch
name when `origin` points at a repo that does not exist (yet), then refuses to
scaffold with a nonsensical remediation hint.

## Steps to reproduce

```bash
mkdir /tmp/x && cd /tmp/x && git init -b main
git remote add origin https://github.com/<org>/<not-yet-created>.git
curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh \
  | bash -s -- --mode direnv --workflow trunk .
```

## Actual behavior

```text
Error: preflight: refusing to scaffold — the default branch is '{"message":"Not Found","documentation_url":"https://docs.github.com/rest/repos/repos#get-a-repository","status":"404"}', not 'main'.
  ...
    git branch -m {"message":"Not Found",...} main && git push -u origin main
```

## Expected behavior

A non-2xx from the default-branch lookup is treated as "unknown" (fall back to
the local branch / skip the remote check, or say "origin repo not found"), never
as a branch name. Creating the remote *after* scaffolding is a normal order —
e.g. orgs that provision repos declaratively (org-config/otterdog) where the
repo only exists once `apply` runs.

## Related adoption friction (same session, devkit 1.18.0)

1. **Stale registry creds → hard fail on a public image.** With an old
   `ghcr.io` entry in `~/.config/containers/auth.json`, the pull 403s
   (`Requesting bearer token: invalid status code from registry 403`) although
   the image is public (anonymous token works). install.sh reports "check your
   internet connection". Suggest: on 403, retry with an empty authfile
   (`--authfile <(echo '{}')` for podman / `DOCKER_CONFIG=$(mktemp -d)`), or at
   least name the stale-credential cause.
2. **Adopting into an existing dir with only `.git` + a data folder** fails
   with "Workspace is not empty. Use --force", while `--force` then requires the
   upgrade preflight (non-main branch, clean tree). A first adoption of a
   directory that has no scaffold files yet has no clean path; the workaround
   was moving `.git` and the folder out and back. The scaffold also creates a
   fresh `.git` (dropping a configured `origin`).

## Environment

- devkit install.sh @ main, image `ghcr.io/vig-os/devcontainer:1.18.0`
- Linux, podman 4.9.3 (as `docker`), gh 2.x

## Possible solution

Check the HTTP status of the default-branch probe (`gh api ... --jq
.default_branch` exits non-zero on 404; the error JSON is on stdout); treat
failure as unknown.

