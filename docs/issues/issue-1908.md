---
type: issue
state: open
created: 2026-10-25T10:21:43Z
updated: 2026-10-25T12:27:51Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1908
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-26T07:40:28.928Z
---

# [Issue 1908]: [Site-agnostic projects: site init hook, gitignored .site/, CI runner via org variables](https://github.com/vig-os/devkit/issues/1908)

**Goal:** a project repo carries no site or infrastructure settings. Where it runs (HPC, cloud, laptop) is configured at clone time or by the runtime environment, so publishing a repo or running it at another site inherits nothing.

**Proposal**
1. **`.site/` convention:** gitignored by the template. Its schema is a site name, logical-dataset → location bindings (matching the repo's `data.toml` names), the output location, and optional runner/scheduler hints. No credentials in it.
2. **`site init` hook:** a devkit command that runs site-specific initialisers when present (e.g. a `<site> site init` on PATH writes `.site/<site>.toml`). With no site detected, it falls back to an interactive or empty template. Documented contract only; devkit ships no site.
3. **CI runner selection via variables, fork-safe:**
   ```yaml
   runs-on: ${{ (github.event.pull_request.head.repo.fork && 'ubuntu-latest') || vars.CI_RUNNER_LARGE || 'ubuntu-latest' }}
   ```
   Org/repo variables are visible to fork-PR workflows, so the explicit fork check is required. A repo or fork without the variables runs hosted.
4. **Env-only runtime config:** code reads endpoints and credentials only from the environment (`AWS_ENDPOINT_URL`, `AWS_*`, `<SITE>_*`); there is a lint against hard-coded endpoints.
5. **Leak-check hook point:** the pre-commit/CI leak check loads extra patterns from a site-provided file if present (patterns are site-private, so they don't ship in devkit).
6. **Publish checklist** in the docs: history scan (gitleaks over all commits), fork-safe workflows, credential rotation if anything is found.

**Acceptance:** a fresh clone with no `.site/` and no org variables passes CI on hosted runners; the template's `.gitignore` covers `.site/` and `.aws/`; the docs explain both the site and the fork paths.

Related: #1907 (NIX_CONFIG on self-hosted runners).
---

# [Comment #1]() by [gerchowl]()

_Posted on October 25, 2026 at 12:27 PM_

Test results for item 3 (CI runner via variables), 2026-10-25. Throwaway repos (private and public, a fork, an org on GitHub Free and one on Team), all deleted afterwards.

Expression: `runs-on: ${{ (github.event.pull_request.head.repo.fork && 'ubuntu-latest') || vars.CI_RUNNER_LARGE || 'ubuntu-latest' }}` (same for SMALL/XLARGE).

| case | result |
|---|---|
| push, same-repo PR, `workflow_dispatch` in a private repo with the variables | the self-hosted label from the variable, every job |
| matrix `runs-on: ${{ … \|\| vars[format('CI_RUNNER_{0}', matrix.size)] \|\| … }}` | resolves per matrix entry |
| reusable workflow (`workflow_call`), same repo and **cross-repo** (callee in a public repo with no variables) | `vars` resolve from the **caller**; `github.event` is the caller's, so the fork check works inside the called workflow |
| fork PR into a public repo whose org has the variables | `ubuntu-latest`, every job |
| repo with no variables | `ubuntu-latest`, every job |
| **private repo in a GitHub Free org, org variables only** | **`ubuntu-latest`**: org variables are not available to private repos on GitHub Free. Team orgs resolve them. |

Findings:
1. **GitHub Free:** organization variables do not reach private repositories. The expression degrades silently to hosted runners. Free-plan orgs need repo-level variables (settings, still nothing in git). The docs should say so.
2. **Fork PRs got no variables at all**, neither org nor repo level (a hosted-only control job printed `vars.X != ''` = false for the fork and true for a same-repo PR). Keep the explicit fork check anyway: it states the intent, it covers `pull_request_target` (base context, variables present), and it doesn't depend on that GitHub behaviour.
3. **devkit's `runner-json` path can adopt this without breaking `DEVKIT_CI_RESOLVE_RUNNER`.** Emulated and tested:
   - resolve-toolchain: `runs-on: ${{ (github.event.pull_request.head.repo.fork && 'ubuntu-26.04') || vars.DEVKIT_CI_RESOLVE_RUNNER || vars.CI_RUNNER_SMALL || 'ubuntu-26.04' }}`
   - `runner-json`: fork → the hosted default; else the `.vig-os` key `DEVKIT_CI_RUNNER` if set; else `vars.CI_RUNNER_SMALL` (passed in through `env:`); else the hosted default.
   - The lanes keep `runs-on: ${{ fromJSON(needs.resolve-toolchain.outputs.runner-json) }}`.

   Then a consumer needs no site label in `.vig-os` at all. Today a fork PR into a public consumer that sets `DEVKIT_CI_RUNNER` (in git) or an org-wide `DEVKIT_CI_RESOLVE_RUNNER` has its lanes target the self-hosted label, so add the fork check there as well.
4. Templates should pin actions to full SHAs: some orgs enforce it (`sha_pinning_required`), and a tag-pinned action fails at "Set up job".
5. `schedule` was not observed: GitHub fired no run of a `*/10` cron on the default branch in about 2 h, across 3 new repos. A scheduled run has the same context as `workflow_dispatch` on the default branch (base repo, variables present, no PR), which passed. So schedule is covered by equivalence, but this was not proven empirically.


