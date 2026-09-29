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
PINNED="$(sed -n 's/^DEVKIT_VERSION=//p' .vig-os)"
LATEST="$(gh release view --repo vig-os/devkit --json tagName --jq .tagName)"
echo "pinned: ${PINNED:-unset}  latest: ${LATEST:-unknown}"
```

Every snippet in this skill sets the variables it uses. Shell state does not survive between commands, so a
snippet that reads `$PINNED` without assigning it silently expands to the empty string and produces a confident,
wrong answer.

Report `pinned: X.Y.Z`, `latest: A.B.C`, and how many releases behind. Being behind is invisible to the drift check
by construction (#1497) — it resolves its comparison image from the pin itself, so it compares the pin to itself.
This line is the only place the staleness axis is observable, so always print it.

## 2b. Plugin version vs the pin

This plugin is versioned with devkit, but that is a property of the **tag**, not of the install. A marketplace
added without a ref tracks devkit's default branch, so the skills running right now may be newer than the scaffold
this repo pins. Read the running plugin's own manifest and compare:

```bash
PLUGIN_VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' \
  "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json" 2>/dev/null || echo unknown)"
PINNED="$(sed -n 's/^DEVKIT_VERSION=//p' .vig-os)"
echo "plugin version: ${PLUGIN_VERSION}   pinned devkit: ${PINNED:-unset}"
```

Report `plugin version` on its own line, always. When it differs from the pin, say so explicitly as a **plugin
version mismatch** and name the consequence: a skill may describe a verb, a flag or a refusal that this repo's
pinned scaffold does not have. The fix is to repoint the marketplace at the pinned tag. A plain re-add does **not** do it: adding a marketplace
that is already on disk prints `already on disk` and exits 0, and `marketplace update` refreshes the ref it was
added with rather than moving to a new one. Remove first, then add at the tag:

```text
/plugin marketplace remove vigos-devkit
/plugin marketplace add vig-os/devkit@<DEVKIT_VERSION> --sparse .claude-plugin plugins
/plugin install devkit@vigos-devkit
```

The re-install is required, not optional: removing a marketplace from its last scope uninstalls the plugins
installed from it.

A mismatch is a warning, not a refusal — tracking the newest devkit deliberately is a legitimate choice. The point
is that it is visible rather than assumed away.

## 3. Drift — does the scaffold still match the pin

The installer's preview is the non-mutating form of the upgrade. **Fetch devkit's installer at the pinned tag** —
never run a repo-local installer script from the repo you are inspecting. A consumer does not ship devkit's
installer, so that path is either absent or somebody else's script, and this skill runs against repositories it
did not write:

```bash
VERSION="$(sed -n 's/^DEVKIT_VERSION=//p' .vig-os)"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "refusing: DEVKIT_VERSION '$VERSION' is not X.Y.Z — it is interpolated into a URL that is piped to bash"
  exit 1
}
curl -fsSL "https://raw.githubusercontent.com/vig-os/devkit/refs/tags/${VERSION}/install.sh" \
  | bash -s -- --preview --version "$VERSION" .
```

**Validate the version before it reaches the URL, every time.** It comes from the manifest of a repository you are
inspecting, not from the operator, and `curl` collapses `..` in a path before it sends the request — so an
unvalidated `DEVKIT_VERSION` of `../../someone/else/refs/heads/main` fetches and executes *that* repository's
script. The `refs/tags/` prefix is the second half: it resolves the tag explicitly, so a branch of the same name
cannot shadow it.

`--preview` prints the add/overwrite/preserve/delete report and exits without touching a file. It does not need
`--force`: a preview is by definition a preview of an upgrade, so it rides the force report path already. In a consumer, the
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
shipped in #1746): the default `rc{N}` still renders `X.Y.Z-rcN`, but `alpha.{N}`, `beta`, and `{YYYYMMDD}`
date-stamped forms are all valid. Match a pre-release as `<base>-<anything>` and read the label out of what you
find:

```bash
git ls-remote --tags origin \
  | sed -n 's#.*refs/tags/##p' | grep -v '\^{}' | sort -V
sed -n 's/^DEVKIT_PRERELEASE_FORMAT=//p' .vig-os   # empty means the rc{N} default
```

For the base version of the train found in section 4, report every `X.Y.Z-*` tag, the highest one, and whether a
GitHub Release object is attached to each:

```bash
gh release list --limit 50 --json tagName,isDraft,isPrerelease,publishedAt
```

By default a candidate creates the **git tag only**. A candidate run with `create-release: true` also creates a
**draft** GitHub pre-release; `promote-release.yml` is the only step that ever publishes one. So report the draft
state rather than assuming absence, and flag a *published* pre-release loudly — publishing locks the tag.

Report any stray `X.Y.Z-*` tag too: candidate discovery lists every pre-release of the version, not only `-rc*`,
so a leftover such as `1.2.3-test` sorting above the next counter blocks further candidates for that version.

## 6. Promote gate — is the version ready to promote

`promote-release.yml` refuses unless all of these hold. Report each as pass/fail rather than a single verdict:

- a **draft** GitHub Release exists for the bare `X.Y.Z` tag (not published, not missing);
- promoting would not move `:latest` backwards (#1626) — compare `X.Y.Z` against the highest published final
  Release with `sort -V`;
- the release PR is out of draft, approved, and CI is green;
- **devkit only:** the downstream smoke-test repo has a **published, non-prerelease** Release for the same tag.

Read the **current** repository's release series, not devkit's — `{owner}/{repo}` is substituted by `gh` from the
checkout, so the same line is correct in devkit and in a consumer. Hard-coding devkit's series would judge a
consumer against the wrong versions:

```bash
VERSION=1.2.3   # the in-flight base version from section 4
gh release view "$VERSION" --json isDraft,isPrerelease,url
gh api repos/{owner}/{repo}/releases --paginate \
  --jq '.[] | select(.draft == false and .prerelease == false) | .tag_name' \
  | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1
```

The cross-repo gate below is **devkit-only** and is the one place a fixed repository is correct, because the
downstream validator is a named repo rather than a property of the repo you are in:

```bash
VERSION=1.2.3   # the in-flight base version from section 4
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "refusing: '$VERSION' is not X.Y.Z"
  exit 1
}
gh api repos/vig-os/devkit-smoke-test/releases/tags/"$VERSION" --jq '{draft, prerelease}'
```

In a consumer, skip that query and read the floating-tag guard instead (`DEVKIT_FLOATING_TAGS` from section 2).

## 7. Hotfix lane

A hotfix is a `release/X.Y.Z` branch cut from `main` rather than `dev`.

**Do not infer this from topology.** An ancestry test looks conclusive and is not: `prepare-release.yml` pushes the
`Unreleased` reset to `dev` right after it cuts the branch, so `dev`'s tip stops being an ancestor of a branch that
was cut from `dev` minutes earlier. Use direct evidence instead — which workflow created the branch, and whether
the version is the next patch of `main`'s latest tag (which is exactly what the hotfix lane enforces):

```bash
gh run list --workflow prepare-hotfix.yml --limit 5 --json displayTitle,conclusion,createdAt,event
gh run list --workflow prepare-release.yml --limit 5 --json displayTitle,conclusion,createdAt
git fetch origin main dev
git describe --tags --abbrev=0 origin/main
```

Report `hotfix in flight: yes/no`, and say which of the two signals you used. If they disagree, report the
disagreement rather than picking one. When yes, no regular train may be cut (#1627), and the eventual promote order
decides whether `:latest` moves forward (#1626).

## 8. Workflow model vs the actual topology

```bash
git ls-remote --heads origin dev main
```

`DEVKIT_WORKFLOW=gitflow` (the default) expects both `dev` and `main`, with topic branches based on `dev`.
`DEVKIT_WORKFLOW=trunk` expects `main` only. An **absent** `DEVKIT_WORKFLOW` key means gitflow — the key is
written back only for trunk. Report a mismatch between the resolved model and the branches that actually exist.

A model switch also leaves the **preserved** `.pre-commit-config.yaml` carrying the other model's branch guard
(#1642), and an upgrade cannot fix a preserved file. Read the guard's `--pattern`, not its `--branch`:

```bash
grep -n 'no-commit-to-branch' -A8 .pre-commit-config.yaml
```

Under `gitflow` the pattern must still exclude `dev` (a `(?!dev$)` clause). If it does not, the manifest says
gitflow and the repo behaves like trunk — direct commits to `dev` are no longer blocked.

Scope this check to a **consumer** repo. Devkit's own config is deliberately a different shape: it passes
`--branch __none__` and does the whole job in `--pattern`, so a naive "does it name `dev`" test reports a false
finding here. Compare the pattern's clauses, never the argument list.

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

The release workflows mint App tokens; without these the train fails partway, after it has already moved refs.

**These are usually organization secrets, not repository secrets.** `gh secret list` shows the repo scope only, so
on its own it reports every App secret as missing — which is wrong, and wrong in the direction that blocks a
release that would have worked. Query both scopes:

```bash
gh secret list --json name --jq '.[].name'                      # repository scope
gh api repos/{owner}/{repo}/actions/organization-secrets \
  --jq '.secrets[].name'                                        # organization scope, inherited by this repo
```

Report present/absent for each: `RELEASE_APP_CLIENT_ID`, `RELEASE_APP_PRIVATE_KEY`, `COMMIT_APP_CLIENT_ID`,
`COMMIT_APP_PRIVATE_KEY`. In devkit itself also report `CACHIX_AUTH_TOKEN`.

If **either** query fails — no auth, a token without `secrets:read`, an org that does not expose the listing —
report `unknown`, not `absent`. A secret you could not see is not a secret that is missing, and the difference
decides whether a release skill refuses. Absent secrets are a hard blocker for every release skill in this plugin;
say so in the report rather than leaving the reader to infer it.

## 11. Print the report

Print every section, in order, even the boring ones — the value of this skill is that the same axes appear every
time in the same place. Close with the single most useful next step, drawn from what you actually read:

- nothing in flight, `dev` ahead of `main` → `/devkit:release-prepare X.Y.Z`
- a draft PR with green CI → `/devkit:release-candidate`
- a ready PR and an accepted candidate → `/devkit:release-finalize`
- a draft Release plus a passed downstream gate → `/devkit:release-promote`
- a train you no longer want → `/devkit:release-abandon`
- pinned version behind latest → `/devkit:upgrade`
