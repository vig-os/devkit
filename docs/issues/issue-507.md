---
type: issue
state: open
created: 2026-04-08T12:43:58Z
updated: 2026-04-08T13:51:18Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/507
comments: 1
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-09T04:39:38.631Z
---

# [Issue 507]: [[BUG] promote-release validate step uses API endpoint that cannot find draft releases](https://github.com/vig-os/devcontainer/issues/507)

### Description

The "Verify draft GitHub Release exists" step in `promote-release.yml` uses `gh api "repos/${GITHUB_REPOSITORY}/releases/tags/${VERSION}"` to check for the draft release. The GitHub API endpoint `GET /repos/{owner}/{repo}/releases/tags/{tag_name}` [does not return draft releases](https://docs.github.com/en/rest/releases/releases#get-a-release-by-tag-name) — it returns 404 for them.

The draft release exists (confirmed via `gh release list` and the list releases API), but this specific endpoint cannot find it.

**Two files are affected:**

1. **Upstream** — `.github/workflows/promote-release.yml` line 163 (validate job, "Verify draft GitHub Release exists" step)
2. **Downstream template** — `assets/workspace/.github/workflows/promote-release.yml` line 99 (identical step, identical bug)

Additionally, both files use the same endpoint in the cleanup job to decide whether RC tags have a GitHub Release before deleting them (upstream line 589, downstream line 405). In practice RC tags don't have draft releases, so this is not a blocking failure, but it is the same incorrect API call and should be corrected for robustness.

### Steps to Reproduce

1. Complete the `release.yml` workflow for version `0.3.2` (creates GHCR images + draft GitHub Release)
2. Run `just promote-release 0.3.2`
3. Observe the "Validate promote prerequisites" job fails at step "Verify draft GitHub Release exists"

### Expected Behavior

The validate step should find the existing draft release and proceed to the promote phase.

### Actual Behavior

The step returns `ERROR: No GitHub Release for tag 0.3.2` with a 404 from the API, even though the draft release exists.

Failed run: https://github.com/vig-os/devcontainer/actions/runs/24131664402

### Environment

- **Workflow:** `.github/workflows/promote-release.yml`
- **Runner:** ubuntu-22.04
- **GitHub Actions runner:** 2.333.1

### Affected Lines

| File | Line | Step | Severity |
|---|---|---|---|
| `.github/workflows/promote-release.yml` | 163 | Verify draft GitHub Release exists | Blocks promote |
| `assets/workspace/.github/workflows/promote-release.yml` | 99 | Verify draft GitHub Release exists | Blocks promote |
| `.github/workflows/promote-release.yml` | 589 | Delete git RC tags without GitHub Release | Low (cleanup correctness) |
| `assets/workspace/.github/workflows/promote-release.yml` | 405 | Delete git RC tags without GitHub Release | Low (cleanup correctness) |

### Possible Solution

Replace the per-tag API call with a query that can find draft releases, e.g.:
- `gh api "repos/${GITHUB_REPOSITORY}/releases" --jq ".[] | select(.tag_name == \"${VERSION}\")"`, or
- `gh release view "$VERSION" --json draft,tagName`

### Changelog Category

Fixed

- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)
---

# [Comment #1]() by [c-vigo]()

_Posted on April 8, 2026 at 01:51 PM_

**Manual promote completed for 0.3.2**

The \`promote-release\` workflow failed earlier due to the draft-release API bug described in this issue. The promote steps were executed manually:

1. **Validated remaining prerequisites** — draft release existed; downstream smoke-test \`0.3.2\` was already published (not draft, not prerelease).
2. **Promoted GHCR \`:latest\`** — manifest updated to \`0.3.2-amd64\` / \`0.3.2-arm64\` (digest \`sha256:b59c4b5ee13f06729400516309255f011b456e1e2001ca11fabb0ebefa4e2416\`).
3. **Published GitHub Release** — \`0.3.2\` undrafted: https://github.com/vig-os/devcontainer/releases/tag/0.3.2
4. **Merged PR #486** — \`release/0.3.2\` merged to \`main\` (mergedAt 2026-04-08T13:50:42Z).
5. **Cleanup (partial)** — remote git tags \`0.3.2-rc1\` and \`0.3.2-rc2\` deleted (no GitHub Release on those tags). **GHCR RC package versions** for \`0.3.2-rc*\` were **not** deleted here: org package DELETE requires \`delete:packages\` (and \`read:packages\`) on the token; they can be removed later via UI, a PAT with those scopes, or the \`promote-release\` cleanup job once #507 is fixed and the workflow is run.

The workflow bug (using \`/releases/tags/{tag}\` which returns 404 for draft releases) is still open for a code fix in \`promote-release.yml\`.

