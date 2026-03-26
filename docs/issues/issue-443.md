---
type: issue
state: closed
created: 2026-03-25T17:15:30Z
updated: 2026-03-26T07:32:48Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devcontainer/issues/443
comments: 1
labels: bug, area:ci
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-26T17:53:32.306Z
---

# [Issue 443]: [Release 0.3.1 failed -- automatic rollback](https://github.com/vig-os/devcontainer/issues/443)


Release 0.3.1 encountered an error during the automated release workflow.

**Failed Jobs:** publish

**Workflow Run:** [View logs](https://github.com/vig-os/devcontainer/actions/runs/23553565067)

**Release PR:** #342

**Rollback Results:**
- Branch rollback: success
- Tag deletion: success

**Actions Taken:**
- Release branch rolled back to pre-finalization state
- Release tag deleted (if created)
- This issue created for investigation

**Manual Cleanup May Be Needed:**
- If images were pushed to GHCR before the failure, they are **not** automatically deleted. Check `ghcr.io/vig-os/devcontainer:0.3.1-*` and remove any orphaned images manually.

**Next Steps:**
1. Review the workflow logs to identify the root cause
2. Check rollback results above; fix any partial rollback manually
3. Fix the issue on the release branch
4. Re-run the workflow when ready

For details, check the workflow run linked above.

---

# [Comment #1]() by [c-vigo]()

_Posted on March 25, 2026 at 06:28 PM_

## Investigation

### Root cause

Root cause **not conclusively identified**. The `Publish final GitHub Release` step failed because `gh release view 0.3.1` returned success, meaning a GitHub Release object for `0.3.1` already existed before this run attempted to create one.

However:
- No prior workflow run published a final `0.3.1` release (the last successful run [`23548412415`](https://github.com/vig-os/devcontainer/actions/runs/23548412415) was a **candidate** producing `0.3.1-rc23`)
- The GitHub Events API no longer retains a `CreateEvent` for the `0.3.1` tag (only the `DeleteEvent` at `2026-03-25T17:15:30Z` from rollback is visible)
- The org audit log is unavailable (free plan)

**Likely culprit:** a stale GitHub Release for `0.3.1` existed from a previous manual action or partial run, which was then cleaned up by the rollback job -- removing the tag but not the release, causing the guard to trip.

### Timeline (2026-03-25)

| Time (UTC) | Event |
|---|---|
| 17:00:31 | Workflow run [`23553565067`](https://github.com/vig-os/devcontainer/actions/runs/23553565067) started (`release-kind: final`) |
| ~17:11 | `Create annotated tag` + `Push tag` steps succeeded (tag `0.3.1` pushed) |
| ~17:12-17:14 | Images pushed to GHCR, signed with cosign, provenance + SBOM attested |
| 17:14:47 | `Publish final GitHub Release` step runs `gh release view 0.3.1` → **succeeds** (release already exists) |
| 17:14:53 | Step exits with `ERROR: GitHub Release already exists for tag 0.3.1` |
| 17:15:30 | Rollback job deletes tag `0.3.1`, rolls back release branch |

### Current state

| Artifact | Status |
|---|---|
| Git tag `0.3.1` | Does not exist (deleted by rollback) |
| GitHub Release `0.3.1` | Does not exist (deleted by rollback or was transient) |
| GHCR image `ghcr.io/vig-os/devcontainer:0.3.1` | **Exists** (orphaned -- pushed before the failure, not cleaned up by rollback) |
| GHCR attestation index `sha256-8e925ffe...` | **Exists** (cosign signature + build provenance + SBOM, 3 artifacts) |
| GHCR `latest` tag | **Points to `0.3.1` images** (incorrect -- should point to `0.3.0`) |

Digests:
| Tag | amd64 | arm64 |
|---|---|---|
| `0.3.1` / `latest` | `sha256:20541c4955...` | `sha256:30b626c290...` |
| `0.3.0` | `sha256:2ccefe1781...` | `sha256:5a0d2e760f...` |

## Manual cleanup

> **Prerequisites:** These commands require a token with `read:packages`, `write:packages`, and `delete:packages` scopes.
>
> ```bash
> gh auth refresh --scopes read:packages,write:packages,delete:packages
> ```

### Step 1 -- Retag `latest` to `0.3.0`

This must happen **before** deleting `0.3.1`, since deleting the underlying manifest would leave `latest` dangling.

```bash
docker buildx imagetools create \
  --tag ghcr.io/vig-os/devcontainer:latest \
  ghcr.io/vig-os/devcontainer:0.3.0
```

### Step 2 -- Delete orphaned `0.3.1` artifacts from GHCR

```bash
PKG="orgs/vig-os/packages/container/devcontainer/versions"

# List all versions with their tags to identify IDs to delete
gh api "$PKG" --paginate \
  --jq '.[] | {id, tags: .metadata.container.tags, created: .created_at}' \
  | jq -s '.' \
  | jq '.[] | select(
      (.tags | any(. == "0.3.1")) or
      (.tags | any(startswith("sha256-")))
    ) | select(
      (.tags | any(. == "latest" or startswith("0.3.0"))) | not
    )'

# For each version ID returned above, delete it:
# gh api --method DELETE "$PKG/<VERSION_ID>"
```

### Step 3 -- Validate

```bash
# 1. Confirm latest now matches 0.3.0
echo "--- latest ---"
docker manifest inspect ghcr.io/vig-os/devcontainer:latest \
  | jq '[.manifests[] | {arch: .platform.architecture, digest: .digest}]'

echo "--- 0.3.0 ---"
docker manifest inspect ghcr.io/vig-os/devcontainer:0.3.0 \
  | jq '[.manifests[] | {arch: .platform.architecture, digest: .digest}]'
# → digests must be identical

# 2. Confirm 0.3.1 is gone
docker manifest inspect ghcr.io/vig-os/devcontainer:0.3.1
# → expected: "manifest unknown"

# 3. Confirm attestation index is gone
docker manifest inspect ghcr.io/vig-os/devcontainer:sha256-8e925ffefc85d5b705f72a788e2cc37233460bc8c0b9619aa8aa35c244f50d69
# → expected: "manifest unknown"
```

## Mitigation

The Validate job currently checks for an existing **git tag** ([`release.yml:321-328`](https://github.com/vig-os/devcontainer/blob/main/.github/workflows/release.yml#L321-L328)) but not for an existing **GitHub Release**. Adding a `gh release view` guard in the Validate step (for final releases) would catch this before the expensive build/sign/publish pipeline runs.

Will open a separate issue to track this.


