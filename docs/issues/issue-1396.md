---
type: issue
state: closed
created: 2026-08-08T19:56:03Z
updated: 2026-08-10T12:38:03Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1396
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-11T03:50:28.082Z
---

# [Issue 1396]: [[BUG] smoke-test failure-notify job cannot mint its upstream App token (404)](https://github.com/vig-os/devkit/issues/1396)

Split from #1391 (its only unresolved part). The listener's `Notify upstream on smoke-test dispatch failure` job fails at **Generate release app token for upstream issue creation**:

```
RequestError [HttpError]: Not Found
```

Observed on every listener failure in the 1.7.0 train (runs 31207370105, 31217441944, 31275371280), so no upstream failure issue is ever filed in devkit. Likely the `create-github-app-token` mint requests `owner: vig-os`/`repositories: devkit` with an App that is not installed on devkit, or the wrong client-id secret is wired for the cross-repo case. Asset: `assets/smoke-test/.github/workflows/repository-dispatch.yml` (notify job).

Refs: #1391
---

# [Comment #1]() by [c-vigo]()

_Posted on August 10, 2026 at 12:38 PM_

Fixed and live-proven.

**Root cause:** the listener's `notify-failure` job minted its App installation token for the pre-rename `vig-os/devcontainer` repository (`assets/smoke-test/.github/workflows/repository-dispatch.yml`, notify job). The App-installation lookup (`GET /repos/{owner}/{repo}/installation`) does not follow repo-rename redirects, so every mint failed with 404 and no upstream failure issue was ever filed. No secrets were miswired — `vig-os-release-app` is installed org-wide; only the repo name was stale.

**Fix:**
- Asset fixed on `dev` via #1398 (merged): `repositories: devcontainer` → `repositories: devkit` (+ stale header comment).
- Hot-deployed to `devkit-smoke-test` `main` via vig-os/devkit-smoke-test#353 (merged), since the listener executes from the default branch. `dev` intentionally not patched — the next train's deploy PR converges it with identical content from the release tag.

**Live proof:** synthetic dispatch with nonexistent tag `9.9.9-rc1` → [run 31388831771](https://github.com/vig-os/devkit-smoke-test/actions/runs/31388831771): deploy failed as intended, `Notify upstream on smoke-test dispatch failure` **succeeded**, and #1401 was auto-filed by `app/vig-os-release-app` — the first successful upstream failure notification. #1401 closed as synthetic.

