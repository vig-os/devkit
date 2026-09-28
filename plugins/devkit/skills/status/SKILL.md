---
name: status
description: >-
  Read-only vigOS devkit state report for the current repository: pinned DEVKIT_VERSION vs the latest devkit
  release, scaffold drift, release branches and release PRs in flight, pre-release tags and whether a GitHub
  Release is attached, the pending-promote gate, the hotfix lane, DEVKIT_WORKFLOW vs the actual branch topology,
  legacy-tag hazards, and whether the required GitHub App secrets exist. Use before any release-train action, when
  asked "where is the release", "what state is the train in", "are we behind on devkit", or when another devkit
  skill asks for a state lookup. Never mutates anything.
---

# devkit status

Pure read-only. This skill runs `git`, `gh` and `sed` queries and prints a report. It never writes a file, never
pushes, never dispatches a workflow. Every other `/devkit:*` skill delegates its step 1 to this one, so keep the
output stable: one `##` heading per axis, one `key: value` line per fact.

If a query fails (no network, no `gh` auth, insufficient token scope), print `unknown — <reason>` for that axis and
carry on. A partial report is useful; a report that lies is not. Never infer a fact you could not read.

## 1. Scope — which repo is this

```bash
git rev-parse --show-toplevel
git remote get-url origin
test -f .vig-os && echo "scaffolded" || echo "no .vig-os — not a devkit-scaffolded repo"
```

Two shapes behave differently and the rest of this report depends on which one you are in:

- **devkit itself** (`origin` is `vig-os/devkit`) — the reference implementation. Its train publishes GHCR images,
  and its promote gate waits on a cross-repo smoke test.
- **a consumer** — carries the scaffolded copies of the same workflows. No GHCR gate, no smoke-test gate; the
  floating-tag guard takes the place of the `:latest` guard.

If `.vig-os` is absent, stop after this section and hand off to `/devkit:adopt`.

## 2. Pin — DEVKIT_VERSION and the rest of the manifest

```bash
sed -n 's/^DEVKIT_VERSION=//p'   .vig-os
sed -n 's/^DEVKIT_WORKFLOW=//p'  .vig-os
sed -n 's/^DEVKIT_MODE=//p'      .vig-os
sed -n 's/^DEVKIT_TAG_PREFIX=//p' .vig-os
sed -n 's/^DEVKIT_FLOATING_TAGS=//p' .vig-os
sed -n 's/^DEVKIT_FEATURES_DISABLED=//p' .vig-os
```

An empty value means "the default applies": `DEVKIT_WORKFLOW=` is `gitflow`, `DEVKIT_TAG_PREFIX=` is no prefix.
Report the resolved value and say it came from the default.

Compare the pin against the latest devkit release:

```bash
gh release view --repo vig-os/devkit --json tagName,publishedAt --jq '"\(.tagName) (\(.publishedAt))"'
```

Report `pinned: X.Y.Z`, `latest: A.B.C`, and how many releases behind. Being behind is invisible to the drift check
by construction (#1497) — it resolves its comparison image from the pin itself, so it compares the pin to itself.
This line is the only place the staleness axis is observable, so always print it.

## 3. Drift — does the scaffold still match the pin

Devkit's own preview is the non-mutating form of the upgrade:

```bash
./install.sh --preview --force --version "$PINNED" .
```

`--preview` prints the add/overwrite/preserve/delete report and exits without touching a file. In a consumer, the
scheduled `devkit-upgrade.yml` and the scaffold-drift lane in `ci.yml` report the same axis; read their latest runs
instead of re-running the installer when the repo is not yours to dirty:

```bash
gh run list --workflow devkit-upgrade.yml --limit 3 --json conclusion,createdAt,url
```

Report `drift: clean` or the list of files that would change.

## 4. Trains in flight — release branches and release PRs

```bash
git ls-remote --heads origin 'refs/heads/release/*'
gh pr list --state open --base main --json number,headRefName,isDraft,reviewDecision,url \
  --jq '.[] | select(.headRefName | startswith("release/"))'
```

Report one line per branch: `release/X.Y.Z — PR #N, draft|ready, <reviewDecision>`. A branch with no PR, or a PR
with no branch, is itself a finding: say so rather than smoothing it over.

**This is the single-train axis.** Devkit's policy is one train at a time: `prepare-release.yml` and
`prepare-hotfix.yml` both refuse while any other `release/*` exists (#1627). If this section lists anything, a new
train cannot be cut until it is promoted or abandoned.

## 5. Pre-release tags and their Releases

Do **not** assume the `-rc` label. The pre-release format is a per-repo setting (`DEVKIT_PRERELEASE_FORMAT`,
landing with #1746); today's default renders `X.Y.Z-rcN`, but `alpha.N`, `beta.N` and date-stamped forms are the
point of that change. Match a pre-release as `<base>-<anything>` and read the label out of what you find:

```bash
git ls-remote --tags origin \
  | sed -n 's#.*refs/tags/##p' | grep -v '\^{}' | sort -V
sed -n 's/^DEVKIT_PRERELEASE_FORMAT=//p' .vig-os   # absent until #1746 lands; empty means the rc default
```

For the base version of the train found in section 4, report every `X.Y.Z-*` tag, the highest one, and whether a
GitHub Release object is attached to each:

```bash
gh release list --limit 50 --json tagName,isDraft,isPrerelease,publishedAt
```

Candidates create the **git tag only** — no Release object. A pre-release tag that *does* carry a Release is
unusual here and worth reporting loudly, because a published one locks the tag.

## 6. Promote gate — is the version ready to promote

`promote-release.yml` refuses unless all of these hold. Report each as pass/fail rather than a single verdict:

- a **draft** GitHub Release exists for the bare `X.Y.Z` tag (not published, not missing);
- promoting would not move `:latest` backwards (#1626) — compare `X.Y.Z` against the highest published final
  Release with `sort -V`;
- the release PR is out of draft, approved, and CI is green;
- **devkit only:** the downstream smoke-test repo has a **published, non-prerelease** Release for the same tag.

```bash
gh release view "$VERSION" --json isDraft,isPrerelease,url
gh api repos/vig-os/devkit/releases --paginate \
  --jq '.[] | select(.draft == false and .prerelease == false) | .tag_name'
gh api repos/vig-os/devkit-smoke-test/releases/tags/"$VERSION" --jq '{draft, prerelease}'
```

In a consumer, skip the last query and read the floating-tag guard instead (`DEVKIT_FLOATING_TAGS` from section 2).

## 7. Hotfix lane

A hotfix is a `release/X.Y.Z` branch cut from `main` rather than `dev`. Distinguish it by merge base:

```bash
git fetch origin main dev
git merge-base --is-ancestor origin/"$BRANCH" origin/dev && echo "from dev" || echo "from main (hotfix)"
```

Report `hotfix in flight: yes/no`. When yes, no regular train may be cut (#1627), and the eventual promote order
decides whether `:latest` moves forward (#1626).

## 8. Workflow model vs the actual topology

```bash
git ls-remote --heads origin dev main
```

`DEVKIT_WORKFLOW=gitflow` (the default) expects both `dev` and `main`, with topic branches based on `dev`.
`DEVKIT_WORKFLOW=trunk` expects `main` only. Report a mismatch explicitly — a model switch leaves the preserved
`.pre-commit-config.yaml` carrying the other model's branch guard (#1642), so also check:

```bash
grep -n 'no-commit-to-branch' -A3 .pre-commit-config.yaml
```

Under `gitflow`, the guard must still name `dev`. If it does not, the repo says gitflow and behaves like trunk.

Also report whether `dev` is behind `main`: `prepare-release.yml` refuses when it is, because the frozen changelog
section would silently omit whatever `main` carries.

```bash
git rev-list --count origin/main ^origin/dev
```

## 9. Legacy-tag hazards

Tag discovery sorts; a tag from an older or foreign version series that sorts above the current one poisons "find
the highest pre-release". Report any tag that does not belong to the current series:

```bash
git ls-remote --tags origin | sed -n 's#.*refs/tags/##p' | grep -v '\^{}' | sort -V | tail -20
```

Flag: tags with a different prefix than `DEVKIT_TAG_PREFIX`, `v`-prefixed tags in an unprefixed repo (and the
reverse), and any published Release whose tag name is now unusable. A published Release that was **deleted**
tombstones its tag name org-wide and permanently (#1301) — the name can never be re-created. If a version in the
current series has no Release and no tag but the changelog says it shipped, say "possible tombstone" and stop; the
recovery is always to cut the next version, never to retry the burnt one.

## 10. Required Apps and secrets

The release workflows mint App tokens; without these the train fails partway, after it has already moved refs:

```bash
gh secret list --json name --jq '.[].name'
```

Report present/absent for each: `RELEASE_APP_CLIENT_ID`, `RELEASE_APP_PRIVATE_KEY`, `COMMIT_APP_CLIENT_ID`,
`COMMIT_APP_PRIVATE_KEY`. In devkit itself also report `CACHIX_AUTH_TOKEN`. Absent secrets are a hard blocker for
every release skill in this plugin; say so in the report rather than leaving the reader to infer it.

## 11. Print the report

Print every section, in order, even the boring ones — the value of this skill is that the same axes appear every
time in the same place. Close with the single most useful next step, drawn from what you actually read:

- nothing in flight, `dev` ahead of `main` → `/devkit:release-prepare X.Y.Z`
- a draft PR with green CI → `/devkit:release-candidate`
- a ready PR and an accepted candidate → `/devkit:release-finalize`
- a draft Release plus a passed downstream gate → `/devkit:release-promote`
- a train you no longer want → `/devkit:release-abandon`
- pinned version behind latest → `/devkit:upgrade`
