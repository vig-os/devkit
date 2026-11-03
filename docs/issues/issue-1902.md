---
type: issue
state: open
created: 2026-10-18T22:56:41Z
updated: 2026-10-18T22:56:41Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1902
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-19T07:36:16.466Z
---

# [Issue 1902]: [ci.yml branch-name gate has no bot-author exemption: a bot's PR (e.g. release-plz) fails commit-checks](https://github.com/vig-os/devkit/issues/1902)

## Problem

The scaffolded `ci.yml` `commit-checks` job's **Validate branch name** step checks every PR's head ref, including PRs opened by bot accounts that name their own branches. `validate-commit-range` already exempts `[bot]` commit authors (COMMIT_MESSAGE_STANDARD.md "Exemptions"), but the branch gate has no matching exemption, so a bot's PR fails `commit-checks` (and the CI Summary) before its commits are even looked at.

Concrete case: vig-os/tessera#626, a release PR opened by a GitHub App (`tessera-release-plz[bot]`, `user.type` `Bot`):

```text
##[error]Branch name 'release-plz-2026-10-18T13-31-15Z' does not follow the convention <type>/<issue>-<summary> (types: chore,feat,…) or chore/<summary>.
```

release-plz names its branch `<pr_branch_prefix><RFC 3339 timestamp>` (`crates/release_plz_core/src/pr.rs` `release_branch`, unchanged in 0.3.169 through 0.3.172). The prefix is configurable, but the timestamp is not, and its uppercase `T`/`Z` fit no slug (`[a-z0-9]+(-[a-z0-9]+)*`). Probed against the gate's regex: `chore/release-plz-2026-10-18T13-31-15Z` and `chore/629-release-plz-2026-10-18T13-31-15Z` both fail (exit 1). Upstream release-plz has open requests for templated branch names (release-plz/release-plz#1991, #2000), but nothing has shipped. The same applies to any bot or App whose branch shape a consumer cannot configure; Dependabot was the earlier instance (#1755).

## Proposed change

Exempt PRs whose author is a bot account, keyed on `github.event.pull_request.user.type == 'Bot'`. GitHub sets that type, a human account cannot claim it, and it is never derived from the branch name. Route it through env (zizmor template-injection gate). Against the current main step (`validate-branch-name`):

```diff
       - name: Validate branch name
         env:
           HEAD_REF: ${{ github.head_ref }}
           BRANCH_TYPES: ${{ needs.resolve-toolchain.outputs.branch-types }}
           ISSUELESS_BRANCH_TYPES: ${{ needs.resolve-toolchain.outputs.issueless-branch-types }}
+          PR_AUTHOR_LOGIN: ${{ github.event.pull_request.user.login }}
+          PR_AUTHOR_TYPE: ${{ github.event.pull_request.user.type }}
         run: |
           set -euo pipefail
+          # A PR opened by a bot account is exempt, matching validate-commit-range's
+          # `[bot]` commit-author exemption. Keyed on the author, never the branch name.
+          if [ "${PR_AUTHOR_TYPE}" = "Bot" ]; then
+            echo "Branch name not checked: '${HEAD_REF}' belongs to a PR opened by bot account ${PR_AUTHOR_LOGIN}."
+            exit 0
+          fi
           # The validator's last stderr line is its verdict; surface it as the
```

Plus a line in `assets/workspace/docs/COMMIT_MESSAGE_STANDARD.md` "Exemptions", next to the bot-authored-commits bullet. Alternatively, a `--author-type` argument on `validate-branch-name` would keep the rule in the one validator (#1760).

Once this lands, the `Dependabot` local patch class (#1755) goes away too: a bot's PR is exempt whatever its namespace.

## Consumer status

tessera carries this as a local patch in its managed `ci.yml` and `docs/COMMIT_MESSAGE_STANDARD.md` (vig-os/tessera#629), commented with a link to this issue, so a devkit upgrade does not drop it silently.

