---
name: release-candidate
description: >-
  Publish the next vigOS devkit release candidate for the release branch you are on: run the read-only state
  lookup, infer the version from the branch, refuse when CI is red, when a pre-release is open on a different base
  version, when the tree is dirty or when a Release object already exists for the tag, then dispatch the canonical
  candidate verb and verify the tag and the cross-repo dispatch. Use when asked to publish or cut an RC.
argument-hint: "[X.Y.Z]"
disable-model-invocation: true
---

# devkit release-candidate

Phase 3 of the release cycle: build, test and publish `X.Y.Z-<pre-release>` from the release branch, then fire the
cross-repo validation dispatch. The PR stays a **draft** throughout — the draft gate is the final-release gate, not
the candidate gate.

## 1. State lookup

Run `/devkit:status`. You need sections 4 (trains in flight), 5 (pre-release tags and their Releases) and 10
(secrets). Then infer the version:

```bash
git rev-parse --abbrev-ref HEAD    # expect release/X.Y.Z
git status --porcelain
```

If the operator passed a version, it must equal the branch's. If it does not, that disagreement is the finding —
report it and stop.

### Validate the inferred version before anything uses it

This is the one skill that takes its version from **repository data** rather than from the operator — a branch
name is attacker-influenceable in a way a typed argument is not, and the `just` recipes interpolate their argument
straight into a shell command. Validate what you parsed, and quote `"$VERSION"` at every use afterwards:

```bash
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
VERSION="${BRANCH#release/}"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "refusing: '$VERSION' is not X.Y.Z"; exit 1; }
```

## 2. Refuse

| State | Why | Offer instead |
|---|---|---|
| Not on a `release/X.Y.Z` branch, and no version given | The candidate is cut from the release branch; there is nothing to infer | `git switch release/X.Y.Z` |
| A pre-release tag exists for a **different base version** than this branch's | Two trains' candidates would interleave, and the highest-tag scan that picks the next number would read the wrong series | Promote or abandon the other train (#1627) |
| Working tree is dirty | The workflow builds the pushed ref; local edits would not be in the artifact you then accept | Commit and push, then retry |
| The release PR has failing CI | The candidate would be built from a tree that does not pass | Fix CI on the release branch first |
| A GitHub Release object already exists for the computed pre-release tag | The workflow refuses; a **published** one has locked the tag name permanently (#1301) | Let the next number be computed, or fix the stray Release |
| A malformed pre-release tag exists in this series | Tag discovery cannot compute the next number and the workflow refuses | Delete the malformed tag (it carries no Release) |
| `RELEASE_APP_*` / `COMMIT_APP_*` missing | The publish fails partway | Provision the Apps first |

Do **not** refuse because the PR is still a draft. Candidates are published from a draft PR by design.

Do not hard-code the `-rc` label when you scan: the pre-release format is configurable
(`DEVKIT_PRERELEASE_FORMAT`, #1746). Match `<base>-<anything>` and read the label from what is there.

## 3. Dry run first

Echo the line and the observed state, then confirm. The underlying workflow takes a `dry-run` input, but
**`publish-candidate`'s signature differs between devkit and a consumer**, so read it before you pass positional
placeholders — in a consumer the third positional is `create-release`, and a flag passed there lands in it:

```bash
just --show publish-candidate
```

Devkit (`version ref *flags`):

```bash
just publish-candidate 1.2.3 "" -f dry-run=true
```

Consumer (`version ref create-release *flags`):

```bash
just publish-candidate 1.2.3 "" false -f dry-run=true
```

## 4. Dispatch

```bash
just publish-candidate 1.2.3
```

The recipe dispatches `release.yml` with `release-kind=candidate`. Never call `gh release create` yourself:
candidate mode deliberately creates the **git tag only**, with no Release object, so the tag stays unlocked.


## 5. Verify

```bash
gh run list --workflow release.yml --limit 1 --json status,conclusion,url
git ls-remote --tags origin | sed -n 's#.*refs/tags/##p' | grep -v '\^{}' | sort -V | tail -5
```

Confirm the run succeeded, the new pre-release tag exists, no Release object was attached to it, and the cross-repo
smoke-test dispatch fired (`docs/CROSS_REPO_RELEASE_GATE.md` describes the contract; in a consumer repo there is no
such gate and this check does not apply).

Print the pre-release number the operator now has to accept downstream — that acceptance is what unblocks promote.

## 6. Hand off

- Candidate accepted downstream, PR marked ready by a human → `/devkit:release-finalize`
- Candidate rejected → fix on the release branch and run this skill again for the next number
- Train no longer wanted → `/devkit:release-abandon`
