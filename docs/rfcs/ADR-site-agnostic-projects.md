---
rfc: ADR-site-agnostic-projects
date: 2026-10-26
title: Site-agnostic projects — fork-safe CI runner selection via variables, gitignored site config
status: proposed
authors:
  - Lars Gerchow (gerchowl)
---

# ADR: Site-agnostic projects and fork-safe CI runner selection

**Decision (TL;DR):** A project repo carries **no site or infrastructure
settings**. Where it runs is configured outside git: by GitHub variables for CI,
and by a gitignored `.site/` directory for everything else.

- **CI runners** come from the GitHub variables `CI_RUNNER_SMALL`,
  `CI_RUNNER_LARGE` and `CI_RUNNER_XLARGE` (repository or organization level),
  never from repo content. Every managed lane belongs to one **size class**.
  Unset or empty means the hosted default, **`ubuntu-26.04`**.
- **Fork-safe on every path:** a pull request from another repository never
  requests a self-hosted label. This holds for the variables, for the legacy
  `.vig-os` key and for the legacy resolve variable. The check is explicit even
  though GitHub gives fork PRs no variables.
- **One compatibility release:** `.vig-os` `DEVKIT_CI_RUNNER` and
  `vars.DEVKIT_CI_RESOLVE_RUNNER` keep working in release N with a
  `::warning::`. `devkit-upgrade` migrates scaffolded repos and says what to
  set. Release N+1 removes both. A leftover key then **fails CI loudly**; it
  never degrades silently to hosted runners.
- **`.site/`** (gitignored, with `.aws/`) holds per-clone site bindings: the
  site name, logical dataset → location bindings, the output location and
  optional hints. It never holds credentials. `just site-init` runs a
  site-provided initialiser found on `PATH`, or falls back to a template.
  devkit ships no site.
- **Env-only runtime config**, enforced by a lint against hard-coded endpoints.
  A **site leak-check hook point** loads extra patterns from a site-provided
  file. A **going-public checklist** covers full-history scans, fork-safe
  workflows and credential rotation.

Proposed in [#1908](https://github.com/vig-os/devkit/issues/1908). The CI part
rests on the owner's empirical test of 2026-10-25
([comment on #1908](https://github.com/vig-os/devkit/issues/1908)), summarised
in [Evidence](#evidence-the-2026-10-25-variable-tests). Five decisions are left
to the owner in [Open decisions](#open-decisions-for-the-owner).

## Problem statement

Today a consumer moves its CI onto self-hosted runners by writing runner
**labels into git**:

- `.vig-os` `DEVKIT_CI_RUNNER=<labels>`
  ([#1173](https://github.com/vig-os/devkit/issues/1173)) feeds
  `resolve-toolchain`'s `runner-json`. Every toolchain lane, the summary gate,
  `sync-issues`, `sync-main-to-dev` and the release train
  ([#1863](https://github.com/vig-os/devkit/issues/1863)) take their runner
  from it.
- `vars.DEVKIT_CI_RESOLVE_RUNNER`
  ([#1796](https://github.com/vig-os/devkit/issues/1796)) moves the
  `resolve-toolchain` jobs, which cannot read `.vig-os` before they have a
  runner, and the seeded extension hooks.

This has three defects:

1. **A site leaks into the project.** The label names the site's runner pool.
   Publishing the repo, forking it, or running it at another site inherits a
   label that means nothing there, or points somewhere it must not. devkit's
   own docs and templates repeat a real site label as their example.
2. **Fork PRs can reach self-hosted runners.** `resolve-toolchain` reads
   `.vig-os` from the **PR's merge checkout**. A fork PR into a public consumer
   that sets `DEVKIT_CI_RUNNER` therefore runs its lanes on the self-hosted
   label. Worse, a fork PR can **add or change** the key and request any label
   the repo's runner groups admit. Running untrusted code on a persistent
   runner can compromise the runner host, its Nix store and its network.
3. **One knob for every job.** Lanes of very different weight share one label
   list, so a consumer cannot put `resolve-toolchain` on a small pool and
   `test` on a large one.

Runtime configuration has the same shape outside CI. Data locations, output
locations and endpoints get hard-coded into project code or committed config.
Nothing stops site patterns (hostnames, bucket names, internal paths) from
being committed, and nothing documents what to check before a private repo
goes public.

## Evidence: the 2026-10-25 variable tests

The owner tested the variable expression on throwaway repos (private and
public, a fork, an org on GitHub Free and one on GitHub Team):

```yaml
runs-on: ${{ (github.event.pull_request.head.repo.fork && 'ubuntu-latest') || vars.CI_RUNNER_LARGE || 'ubuntu-latest' }}
```

| Case | Result |
|---|---|
| push, same-repo PR, `workflow_dispatch` in a private repo with the variables | the self-hosted label from the variable, every job |
| matrix `vars[format('CI_RUNNER_{0}', matrix.size)]` | resolves per matrix entry |
| reusable workflow, same repo and **cross-repo** (callee in a public repo without variables) | `vars` resolve from the **caller**; `github.event` is the caller's, so the fork check works in the callee |
| fork PR into a public repo whose org sets the variables | hosted, every job |
| repo with no variables | hosted, every job |
| **private repo in a GitHub Free org, org variables only** | **hosted**: org variables do not reach private repos on Free; Team orgs resolve them |

Findings this ADR builds on:

1. **GitHub Free:** organization variables do not reach private repositories,
   and the expression silently degrades to hosted runners. Free-plan orgs need
   **repository-level** variables.
2. **Fork PRs got no variables at all**, neither org nor repo level. The
   explicit fork check stays anyway (see [Security analysis](#security-analysis)).
3. The `runner-json` path can adopt variables without breaking
   `DEVKIT_CI_RESOLVE_RUNNER` (emulated and tested). The lanes keep
   `runs-on: ${{ fromJSON(...) }}`.
4. Templates should pin actions to full SHAs. devkit's managed workflows
   already do.
5. `schedule` was not observed firing during the test window. A scheduled run
   has the same context as `workflow_dispatch` on the default branch (base
   repo, variables present, no PR), which passed. Schedule is covered by
   equivalence, not empirically.

## Decision

### 1. Variables, size classes and the hosted default

| Variable | Meaning |
|---|---|
| `CI_RUNNER_SMALL` | one runner label for short orchestration jobs (resolve, gates, release-train steps) |
| `CI_RUNNER_LARGE` | one runner label for toolchain lanes (dev-shell realisation, lint, tests) |
| `CI_RUNNER_XLARGE` | one runner label for lanes a project declares heavier than LARGE |

- Set at **repository** or **organization** level. On GitHub Free, private
  repos must use repository-level variables (Evidence, finding 1).
- **The value is exactly one label.** The direct `runs-on` expression reads a
  variable as a single label, so the `runner-json` path must not read it any
  other way. A value that is empty after trimming means **unset**. A value with
  a comma or with leading or trailing whitespace is an **error** in
  `resolve-toolchain` (§3), because the direct expressions would request a
  label no runner carries and queue forever. A pool that needs several labels
  gets one unique custom label. Runner scale sets already work that way.
- **The classes are independent. There is no cross-class fallback.** A lane
  whose class variable is unset runs hosted, even when another class is set.
  Falling back to a smaller pool would put a heavy lane on a runner sized for
  orchestration and fail by OOM. Falling back to a larger pool would spend
  capacity the org did not allocate. `resolve-toolchain` reports each class's
  source (§3), so a partial setup is visible, not silent.
- **Hosted default: `ubuntu-26.04`**, not `ubuntu-latest`. It is the label
  every managed workflow already uses. A pinned image keeps CI reproducible,
  and moving to the next image is a deliberate devkit release, not a silent
  GitHub flip. `devkit-upgrade.yml`'s two `ubuntu-latest` jobs converge on it
  (§5).

The variables carry no secrets, but label names appear in job logs ("Requested
labels"). Those logs are public in a public repo, so a label must not encode
anything the site considers private.

### 2. Fork predicate

A run is treated as **foreign** when it carries a pull request whose head is
not this repository:

```text
github.event.pull_request && (github.event.pull_request.head.repo.fork || github.event.pull_request.head.repo.full_name != github.repository)
```

- `head.repo.fork` is the owner-tested clause.
- The `full_name` clause adds a PR whose head repository was deleted
  (`head.repo` is null) and a cross-repository PR whose head is not flagged as
  a fork. It can only turn a self-hosted result into a hosted one, so it
  cannot weaken the tested behaviour.
- The `github.event.pull_request &&` guard keeps `push`, `schedule`,
  `workflow_dispatch` and `workflow_call` from a non-PR caller out of the
  predicate. Without it, `null != github.repository` would be true.

The predicate covers `pull_request` and `pull_request_target`, which carry the
same `pull_request` payload. It does **not** cover `workflow_run`, whose
payload has no `pull_request` object. No managed workflow uses `workflow_run`
today, and a test forbids it in scaffolded workflows until the predicate is
extended (sub-issue S1).

### 3. Resolution order per job class

There are two job classes: jobs whose `runs-on` is a **direct expression**,
and jobs that consume `resolve-toolchain`'s outputs (**runner-json lanes**).

#### Direct-expression jobs

These are the `resolve-toolchain` jobs (SMALL), which produce the outputs and
cannot consume them, and the seeded extension hooks (LARGE, §5), whose callers
pass them no runner input.

Compatibility release N, under Recommended decision (a):

```yaml
runs-on: ${{ (github.event.pull_request && (github.event.pull_request.head.repo.fork || github.event.pull_request.head.repo.full_name != github.repository) && 'ubuntu-26.04') || vars.CI_RUNNER_SMALL || vars.DEVKIT_CI_RESOLVE_RUNNER || 'ubuntu-26.04' }}
```

Release N+1 and later:

```yaml
runs-on: ${{ (github.event.pull_request && (github.event.pull_request.head.repo.fork || github.event.pull_request.head.repo.full_name != github.repository) && 'ubuntu-26.04') || vars.CI_RUNNER_SMALL || 'ubuntu-26.04' }}
```

New seeded hooks use the same expression with `CI_RUNNER_LARGE` and never
reference `DEVKIT_CI_RESOLVE_RUNNER`. GitHub expressions treat `''` as false,
so an empty variable falls through. A whitespace-only value is truthy and
requests a bogus label. The resolve job cannot catch that for its own runner,
because it is not scheduled. It catches it for every other class (below), and
the docs state the limit.

If decision (a) goes to the legacy-wins option, the compatibility-release
expression swaps the two `vars.` terms. Nothing else changes.

#### runner-json lanes

`resolve-toolchain` computes every class once and emits it. Its new inputs are
`runner-small`, `runner-large`, `runner-xlarge` and `legacy-resolve-runner`.
Each calling job passes them from `vars.*`, because composite actions do not
read `vars` themselves. The action evaluates the fork predicate itself from
the `github` context, so a caller cannot skip it by omission.

Algorithm for each class `S` in `small`, `large`, `xlarge`:

```text
H = "ubuntu-26.04"
F = fork predicate (§2)
V = trim(input runner-<S>)                       # from vars.CI_RUNNER_<S>
L = labels(.vig-os DEVKIT_CI_RUNNER)             # release N only: comma-split,
                                                 # each label trimmed, empties dropped
if   F:                 runners[S] = [H];  source[S] = "fork"
elif V != "":           validate V (one label, no comma, no surrounding whitespace) else ::error:: + exit 1
                        runners[S] = [V];  source[S] = "variable"
elif L != []:           runners[S] = L;    source[S] = "legacy-key"     # release N only
else:                   runners[S] = [H];  source[S] = "default"
```

The precedence shown is the Recommended option of decision (a): the variable
wins over the legacy key. The legacy-wins option swaps the `V` and `L` arms.

Lane entries are then resolved from the lane → class map: built-in defaults
(§5), plus the `.vig-os` `DEVKIT_CI_LANE_SIZES` override if decision (b) adopts
it. Each lane gets `runners[<lane>] = runners[<class>]`.

**Outputs:**

- `runners` is a JSON object that maps each class and each overridable lane to
  a label array, for example
  `{"small":["ubuntu-26.04"],"large":["pool-l"],"xlarge":["ubuntu-26.04"],"lint":["pool-l"],"test":["pool-l"],"extension":["pool-l"],"release-test":["pool-l"]}`.
  Lanes declare `runs-on: ${{ fromJSON(needs.resolve-toolchain.outputs.runners).large }}`,
  or `.test`, or `['release-test']`.
- `runner-sources` is a JSON object that maps each class to `fork`, `variable`,
  `legacy-key` or `default`. It is printed as a table in the step summary. It
  is also the signal [#1891](https://github.com/vig-os/devkit/issues/1891)'s
  cache profile reads instead of `DEVKIT_CI_RUNNER`.
- `runner-json` is kept in release N as a **deprecated alias** of
  `runners.large`, for consumer-written jobs that reference it. It is removed
  in N+1. A removed output reaches `fromJSON('')`, which fails the job loudly.

**Diagnostics.** None of them can be silenced:

- If `L` is non-empty: `::warning::` that `DEVKIT_CI_RUNNER` is deprecated,
  will be removed in N+1, and which variables to set. Under (a)-Recommended,
  the warning also names each class whose variable already overrides the key.
- If `legacy-resolve-runner` is non-empty: `::warning::` that
  `DEVKIT_CI_RESOLVE_RUNNER` is deprecated in favour of `CI_RUNNER_SMALL`.
- If a variable is malformed: `::error::` and exit 1, before any lane is
  scheduled.
- If the run is not foreign, at least one class came from `variable` and
  another came from `default`: `::notice::` naming the unset classes. This is
  the partial-setup case.
- If the repo is private and every class came from `default`: a step-summary
  line, not an annotation, saying that on GitHub Free organization variables do
  not reach private repos and repository-level variables are needed. It is a
  summary line because every hosted-only private consumer would otherwise see a
  warning on every run.

**Release N+1** deletes the `L` arm and keeps two **permanent tombstones**:

- A non-empty `DEVKIT_CI_RUNNER` in `.vig-os` is an `::error::` that names the
  removal release and the variables to set. CI goes red. It never silently
  moves to hosted runners. The check also fires on foreign runs, because the
  base repository's own runs fail the same way.
- A non-empty `legacy-resolve-runner` with an empty `runner-small`, on a run
  that is not foreign, is an `::error::`. The consumer clearly meant
  self-hosted resolve jobs, which now run hosted. With `CI_RUNNER_SMALL` set,
  it is only a `::warning::`, because the variable may still serve pre-N
  seeded hook copies (decision (d)).

The tombstones are a few lines each and are never removed, so a repo that
skips the compatibility release still gets a loud failure, not a silent
degrade.

### 4. Inventory: every job that selects a runner

Classes: **S** = SMALL, **L** = LARGE (the default class of an overridable
lane), **hosted** = literal `ubuntu-26.04`, unchanged. "runner-json" means
`fromJSON(needs.<resolver>.outputs.runner-json)` today. "resolve var" means
`vars.DEVKIT_CI_RESOLVE_RUNNER || 'ubuntu-26.04'`. Every target row that is not
hosted uses the fork predicate.

#### Scaffolded workflows (`assets/workspace/.github/workflows`)

| Workflow (triggers) | Job | Today | Target |
|---|---|---|---|
| `ci.yml` (pull_request, workflow_dispatch) | `resolve-toolchain` | resolve var | S, direct expression |
| | `lint` | runner-json | L, lane `lint` |
| | `test` | runner-json | L, lane `test` |
| | `commit-checks` | runner-json | S |
| | `scaffold-drift` | runner-json | S |
| | `devkit-staleness` | runner-json | S |
| | `dependency-review` | hosted | hosted (public repos only) |
| | `extension` → `ci-extension.yml` | passes `runner-json` | passes lane `extension` (L) as `runner-json` |
| | `summary` | runner-json | S |
| `ci-extension.yml` (workflow_call, seeded) | `extension` | `fromJSON(inputs.runner-json)` | unchanged; the caller now passes the `extension` lane |
| `sync-issues.yml` (schedule, workflow_dispatch) | `resolve-toolchain` / `sync` | resolve var / runner-json | S / S |
| `sync-main-to-dev.yml` (push, workflow_dispatch) | `resolve-toolchain` / `check`, `sync` | resolve var / runner-json | S / S |
| `prepare-release.yml` (workflow_dispatch) | `validate` (is the resolver) | resolve var | S, direct expression |
| | `prepare`, `open-pr`, `rollback` | `needs.validate` runner-json | S |
| | `extension` → `prepare-release-extension.yml` | (no input) | (no input) |
| `prepare-hotfix.yml` (workflow_dispatch) | `resolve-toolchain` / `validate`, `prepare`, `open-pr`, `rollback` | resolve var / runner-json | S / S |
| `release.yml` (workflow_dispatch) | `resolve-toolchain` / `rollback` | resolve var / runner-json | S / S |
| | `core` → `release-core.yml`, `publish` → `release-publish.yml` | pass `runner-json` | pass `runners` |
| `release-core.yml` (workflow_call, managed) | `validate`, `finalize` | `fromJSON(inputs.runner-json)` | S from `fromJSON(inputs.runners)` |
| | `test` | `fromJSON(inputs.runner-json)` | L, lane `release-test` |
| `release-publish.yml` (workflow_call, managed) | `publish` | `fromJSON(inputs.runner-json)` | S from `fromJSON(inputs.runners)` |
| `promote-release.yml` (workflow_dispatch) | `resolve-toolchain` / `validate`, `promote`, `merge`, `cleanup`, `floating-tags` | resolve var / runner-json | S / S |
| `abandon-release.yml` (workflow_dispatch) | `resolve-toolchain` / `validate`, `abandon` | resolve var / runner-json | S / S |
| `prepare-release-extension.yml` (workflow_call, seeded) | `extension` | resolve var | new scaffolds: L, direct expression; existing copies: decision (d) |
| `release-extension.yml` (workflow_call, seeded) | `extension` | resolve var | same as above |
| `publish-release-extension.yml` (release, workflow_dispatch; seeded) | `resolve`, `publish` | resolve var | same as above |
| `devkit-upgrade.yml` (schedule, workflow_dispatch) | `upgrade`, `report` | `ubuntu-latest` | decision (e): S (Recommended), or hosted `ubuntu-26.04` |
| `codeql.yml` (pull_request, push, schedule) | `analyze` | hosted | hosted (public repos only) |
| `scorecard.yml` (schedule, push) | `analysis` | hosted | hosted (public repos only) |

The `release-core` and `release-publish` input changes from `runner-json` to
`runners`. Both files are managed, so caller and callee always ship together.
The seeded hooks' inputs do **not** change: the
`test_callers_pass_only_inputs_the_oldest_seeded_hook_declares` contract holds.

**Public-only jobs stay hosted.** `dependency-review`, `codeql` and `scorecard`
skip on private repos. Public repos get hosted minutes free, and public repos
are where fork PRs come from, so there is nothing to gain from a variable and
an attack surface to lose.

#### devkit's own workflows (`.github/workflows`)

devkit is public, and hosted minutes are free for it. Every job keeps its
literal label. **None adopts the variables.**

| Workflow | Jobs | Today and target |
|---|---|---|
| `ci.yml` | `build-image`, `test-image`, `test-integration`, `project-lint`, `project-tests`, `project-bats`, `project-flake`, `consumer-matrix`, `commit-checks`, `python-security`, `security-scan`, `dependency-review`, `summary` | hosted `ubuntu-26.04` |
| `release.yml` | `validate`, `finalize`, `vulnix-gate`, `publish`, `smoke-test`, `rollback` | hosted `ubuntu-26.04` |
| `release.yml`, `nix-image.yml` | `build-and-test` | hosted matrix `ubuntu-24.04` / `ubuntu-24.04-arm` |
| `nix-image.yml` | `multi-arch-index` | hosted `ubuntu-26.04` |
| `home-matrix.yml` | `home-aarch64-darwin` / `home-aarch64-linux` | hosted `macos-latest` / `ubuntu-26.04-arm` |
| `prepare-release.yml`, `prepare-hotfix.yml` | `validate`, `prepare`, `open-pr`, `rollback` | hosted `ubuntu-26.04` |
| `promote-release.yml` | `validate`, `promote`, `merge`, `cleanup` | hosted `ubuntu-26.04` |
| `abandon-release.yml` | `validate`, `abandon` | hosted `ubuntu-26.04` |
| `prepare-release-extension.yml` | `sync-manifest` | hosted `ubuntu-26.04` |
| `sync-main-to-dev.yml` | `check`, `sync` | hosted `ubuntu-26.04` |
| `codeql.yml`, `scorecard.yml`, `ghcr-cleanup.yml`, `nix-cachix.yml`, `renovate-validate.yml`, `security-scan.yml`, `sync-issues.yml`, `update-nixpkgs.yml`, `update-nixpkgs-unstable.yml`, `release-neutral-guard.yml`, `release-neutral-open.yml` | one job each | hosted `ubuntu-26.04` |

### 5. Lane classes

Default map, subject to decision (b):

| Class | Lanes |
|---|---|
| LARGE | `lint`, `test`, `extension` (`ci-extension`), `release-test` (`release-core` `test`), seeded release hooks |
| SMALL | everything else that routes: resolve jobs, `commit-checks`, `scaffold-drift`, `devkit-staleness`, `summary`, `sync-*`, release-train orchestration, `devkit-upgrade` (decision (e)) |
| XLARGE | no default lane; reachable through the decision (b) override |

`lint` and `test` both realise the dev-shell, which is the dominant cost, so
both are LARGE. A container-mode consumer's runners already need a container
runtime for the `container:` lanes, so any class it routes is container-capable.

### 6. Migration

#### What `devkit-upgrade` does (release N)

`init-workspace.sh` already reads `DEVKIT_CI_RUNNER` before the template
overwrite and writes it back (#1173). In release N it also:

1. Reads `CI_RUNNER_SMALL`, `CI_RUNNER_LARGE` and `CI_RUNNER_XLARGE` from its
   **environment**. `devkit-upgrade.yml` passes `${{ vars.CI_RUNNER_* }}` into
   the install step, so the values are what CI will see. On GitHub Free, org
   variables are invisible there too, which is correct. A local
   `install.sh --force` sees nothing unless the maintainer exports the
   variables.
2. Applies decision (c) to a non-empty legacy key.
3. Prints exactly one `ci-runner-migration:` line per finding. This uses the
   established install-log channel (`flake-bump:`, `preserved-hook-*:`), and
   `devkit-upgrade.yml` lifts the lines into the step summary and the adoption
   PR body under a **"CI runner migration"** heading.

The PR-body text, per case:

| Legacy key | Visible variables | PR body says |
|---|---|---|
| set | all three | key removed, or kept under (c)-warn-only; runners now come from the variables; nothing to do |
| set | some or none | which `CI_RUNNER_*` to set, at **repository level** if the repo is private on GitHub Free; the example command `gh variable set CI_RUNNER_LARGE --body <label>`; the key keeps working until N+1 |
| unset, `vars.DEVKIT_CI_RESOLVE_RUNNER` visible | n/a | rename the variable to `CI_RUNNER_SMALL`, then delete the old one after decision (d)'s hook migration |
| unset | n/a | nothing (no line printed) |

The PR body never repeats the label itself. It names variables, not values,
even though the value is already in git, so the adoption PR does not spread
the label further.

#### Deprecation timeline

- **Release N (compatibility):** variables plus the fork predicate everywhere.
  Legacy key and legacy variable keep working with warnings. The migration
  runs. `MIGRATION.md` gets the new section, and CHANGELOG `### Deprecated`
  names both legacy knobs.
- **Release N+1 (removal):** the legacy arms are deleted, the tombstones (§3)
  stay, the `runner-json` alias output is removed, and the template `.vig-os`
  drops the `DEVKIT_CI_RUNNER=` line. `init-workspace.sh` still recognises a
  leftover key: it strips it when all three variables are visible, and
  otherwise keeps it and prints the migration line, so the adoption PR's own CI
  goes red with the tombstone error next to an explanation. CHANGELOG
  `### Removed`.

This follows the existing precedent of deprecating in one minor and removing
in the next (`DEVKIT_UPGRADE_APP_ID`,
[#1366](https://github.com/vig-os/devkit/issues/1366)). The tombstones keep
the removal from ever being silent.

#### Failure mode after removal

A repo still holding `DEVKIT_CI_RUNNER` in N+1 with no variables gets a red
`Resolve toolchain` job with:

```text
::error::DEVKIT_CI_RUNNER in .vig-os was removed in devkit <N+1>; CI runners now come from the variables CI_RUNNER_SMALL/LARGE/XLARGE (repository level on private GitHub Free repos). Set them, delete the key, and re-run. See MIGRATION.md#run-ci-on-self-hosted-runners.
```

It is never a silent move to hosted runners. For a billing-blocked org, a
silent move would turn into queued or rejected jobs that point at nothing.

### 7. Security analysis

- **Fork PRs (`pull_request`).** The threat is code from an untrusted author
  executing on a self-hosted runner: persistence on non-ephemeral hosts,
  poisoning the shared Nix store or caches, and reach into the site network.
  Today `DEVKIT_CI_RUNNER` is read from the PR's merge checkout, so a fork can
  set the label it runs on. After this ADR, the fork predicate resolves every
  class to `ubuntu-26.04` in both the direct expressions and the action. The
  legacy key is **ignored** for foreign runs, not just overridden.
- **`pull_request_target`.** It runs in the base context, where variables
  **and secrets are present**. GitHub's no-variables-for-forks behaviour does
  not apply here. The predicate does, because the payload carries
  `pull_request.head.repo`. No managed workflow uses this trigger today. A
  test pins that every scaffolded `runs-on` that is not literally hosted
  contains the predicate (S1), so a future `pull_request_target` workflow
  cannot route around it.
- **`workflow_run`** carries no `pull_request` payload, so the predicate cannot
  see a fork. Scaffolded workflows must not use it until the predicate is
  extended to `github.event.workflow_run.head_repository`. A test enforces this
  (S1).
- **Reusable workflows, same repo and cross-repo.** `vars` and `github.event`
  resolve from the **caller** (Evidence, row 3), so a callee's predicate sees
  the caller's PR. `runners` and `runner-json` passed as inputs were computed
  fork-safe by the caller's resolver. A reusable workflow in a public devkit
  repo without variables still resolves the consumer's variables, which is
  intended.
- **Why the explicit check stays** (owner's finding 2): GitHub gave fork PRs no
  variables in the test, but
  1. the check states the intent in the file a reviewer reads;
  2. `pull_request_target` has variables;
  3. it does not depend on a platform behaviour that is not a documented
     security guarantee;
  4. the legacy key comes from repo content, which a fork controls, so the
     variables' behaviour does nothing for it in release N.
- **Out of scope here:** trusted same-repo PRs. Writers are trusted by repo
  permission. Separating trusted main-branch runs from PR runs is
  [#1876](https://github.com/vig-os/devkit/issues/1876). Its event-scoped
  lookup slots into the algorithm's `V` step, for example as a
  `CI_RUNNER_<S>_MAIN` consulted first on default-branch events, without
  changing the predicate.
- **Defence in depth** (documented in the checklist, not enforced by devkit):
  self-hosted runner groups not available to public repositories, "require
  approval for fork PR workflows", ephemeral runners.

### 8. `.site/` convention

- **Location.** `.site/` at the repo root, gitignored by the template
  `.gitignore` together with `.aws/` (project-local AWS CLI profiles). One file
  per site: `.site/<site>.toml`. A site initialiser may also write
  `.site/leak-patterns.toml` (§10).
- **Active site.** `$DEVKIT_SITE` if set (error if `.site/$DEVKIT_SITE.toml` is
  missing). Otherwise the only `.site/*.toml` other than `leak-patterns.toml`.
  Otherwise none. Several files without `DEVKIT_SITE` is an error that lists
  them. `check-site-config --print-path` is the one implementation of this
  lookup. Project code calls it or follows the documented rule.
- **Schema v1:**

  ```toml
  schema = 1                     # required, integer; unknown versions are an error
  site = "example"               # required; [a-z0-9][a-z0-9-]*; equals the file stem

  [datasets.raw-scans]           # one table per logical dataset; names match data.toml
  location = "s3://bucket/prefix/raw"   # required: URI or absolute path

  [output]
  location = "/srv/project/out"        # optional

  [hints]                        # optional; string values; devkit never interprets them
  runner = "large"
  scheduler = "slurm"
  ```

- **`data.toml`** is repo-owned. devkit reads only the **names**: the keys of
  its top-level `[datasets]` table. A binding for a name absent from
  `data.toml` is a warning, because a site file may outlive a renamed dataset.
  A dataset with no binding is a warning, because a site may not host every
  dataset. Without a `data.toml`, names are unchecked.
- **Never credentials.** `check-site-config` rejects any key, at any depth,
  matching `(secret|token|password|passwd|credential|private[_-]?key|access[_-]?key)`
  (case-insensitive), and any URI with userinfo (`scheme://user[:pw]@`).
  Credentials come from the environment or the tool's own store (§9).

### 9. `site init` hook contract

- **Recipe:** `just site-init [site] [--force]` in the managed root `justfile`,
  the one layer present in every delivery mode, like `doctor`. It calls the
  vig-utils console script `site-init`.
- **Discovery:** executables on `PATH` named `devkit-site-init-<site>`, with
  `<site>` matching `[a-z0-9][a-z0-9-]*`. With an argument, that initialiser
  runs. Without one: exactly one found runs; several is an error that lists
  them; none uses the fallback.
- **Invocation:** cwd is the repo root, and stdin, stdout and stderr are
  inherited, so an initialiser may prompt. Environment:
  - `DEVKIT_SITE=<site>`
  - `DEVKIT_SITE_DIR=<abs staging dir>`, a fresh `.site/.staging-<random>/`
  - `DEVKIT_DATA_MANIFEST=<abs path to data.toml>`, or empty

  No arguments.
- **Initialiser obligations:**
  - write `$DEVKIT_SITE_DIR/<site>.toml` (schema v1), and optionally
    `$DEVKIT_SITE_DIR/leak-patterns.toml`;
  - write nothing else in the repo;
  - put no credentials in either file;
  - exit 0 on success.

  It may configure credentials **outside** the repo (its own store, `~/.aws`)
  or in the gitignored `.aws/`.
- **devkit then:**
  - validates the staged files with `check-site-config`;
  - on success, moves them into `.site/`; existing files are refused without
    `--force`;
  - on a non-zero exit or an invalid file, deletes the staging directory and
    fails with the initialiser's exit code or the validation error, so nothing
    is left half-written.
- **Fallback (no initialiser):** on a TTY, prompt for the site name (default
  `local`), one location per `data.toml` dataset and the output location. Off a
  TTY, write `.site/local.toml` with empty locations and comments, and print
  the path. Both paths are validated the same way.
- devkit **ships no site initialiser** and names none in code, docs or tests.
  Tests use a fixture initialiser on a temporary `PATH`.

### 10. Env-only runtime config, lint and leak-check hook point

- **Rule:** project code reads endpoints and credentials only from the
  environment (`AWS_ENDPOINT_URL*`, `AWS_*`, `<SITE>_*`), and data locations
  from the active site file. Nothing committed carries a site endpoint.
- **Lint `no-hardcoded-endpoints`** (vig-utils `check-hardcoded-endpoints`, a
  hook on the consumer generation surface in `nix/hooks.nix`, **enabled by
  default**, and in devkit's own config). v1 rules:
  1. an `endpoint_url` / `endpoint-url` / `endpointUrl` keyword or key whose
     value is a string literal starting with `http://` or `https://`;
  2. a literal value assigned to `AWS_ENDPOINT_URL*`, `AWS_ACCESS_KEY_ID`,
     `AWS_SECRET_ACCESS_KEY` or `AWS_SESSION_TOKEN`, in shell, dotenv, YAML,
     TOML, JSON or Python (`os.environ[...] = "..."`). A reference
     (`$VAR`, `${VAR}`, `${{ ... }}`) is not a literal.

  Exempt: hosts `localhost`, `127.0.0.1`, `[::1]`, and the RFC 2606 names
  (`example.com`, `*.example`, `*.test`, `*.invalid`), plus any line carrying
  the pragma `devkit: allow-endpoint`. The rules are deliberately narrow, so
  default-on costs no false-positive triage. Broader site patterns belong to
  the leak check.
- **Leak-check hook point `site-leak-check`** (vig-utils `site-leak-check`,
  enabled by default):
  - **Pattern file:** `$DEVKIT_LEAK_PATTERNS` (absolute path, for site hosts
    and self-hosted runner service environments), else
    `.site/leak-patterns.toml`, else none.
  - **Format:** a gitleaks config (`[[rules]]`, `[allowlist]`), so the same
    file drives the full-history scan in the checklist.
  - **Runs** `gitleaks` with `--config <file> --redact`. Locally it scans the
    staged changes; under `pre-commit run --all-files` (CI) it scans the
    working tree. `--redact` keeps the site's patterns and matches out of
    public logs.
  - **No pattern file** means exit 0 with no output. That is not a fallback:
    without a site there is nothing site-private to find. Hosted and fork runs
    therefore never see site patterns, which is the point. The patterns are
    themselves site-private.
  - **Error** if the pattern file is tracked by git, or lies inside the
    worktree outside `.site/`, because the check would leak its own patterns.
  - **Independent** of the opt-in repo-level `gitleaks` hook (#1172), which
    keeps its own `.gitleaks.toml`.
- **Going-public checklist** (`docs/GOING_PUBLIC.md`, linked from
  `MIGRATION.md` and `SOLO_ADOPTION.md`):
  1. Run `gitleaks git --redact` over **all refs**, with default rules and
     then with the site pattern file.
  2. Run `check-hardcoded-endpoints` over the tree.
  3. Check that `git log --all -- .site .aws` is empty.
  4. Confirm the managed workflows are on a fork-safe devkit (≥ N) and that no
     repo-owned workflow requests a self-hosted label without the predicate.
  5. Confirm the runner groups do not admit public repos and fork-PR approval
     is required.
  6. Confirm label names in public logs reveal nothing.
  7. **If anything is found: rotate first.** A history rewrite does not
     unpublish what a clone or cache already holds. Then rewrite and re-scan.

## Open decisions for the owner

Each option names its honest cost. The Recommended option is the one this ADR
considers correct in the long term.

**(a) Precedence in release N when both the legacy `.vig-os` key and
`CI_RUNNER_*` are set.**

1. **Variable wins; the key is reported as overridden (Recommended).** Setting
   the variable is the migration act, and the end state takes effect at once.
   The key, which is the thing being removed, cannot override it. *Cost:* a
   consumer whose org already sets `CI_RUNNER_*` (Team plan, or repository
   level) moves runners when it adopts release N, if the variable names a
   different label than its key. The adoption PR body and the
   `runner-sources` summary name every overridden class.
2. **Legacy key wins** (the owner's emulated order). Release N changes nothing
   for an existing self-hosted consumer. *Cost:* setting a variable has no
   visible effect until the key is deleted, which is the confusing state the
   migration is meant to end. Decision (c) can then never strip the key safely
   in N, because stripping changes behaviour.
3. **Both set is an error.** *Cost:* CI turns red for every such consumer on
   adoption, in exactly the population that already did half the migration.

**(b) Size class per lane, and whether a consumer can override it.**

1. **Defaults as in §5, plus a per-lane override in `.vig-os`:
   `DEVKIT_CI_LANE_SIZES=test=xlarge,lint=large` (Recommended).** It covers the
   lanes `lint`, `test`, `extension` and `release-test`, and the sizes
   `small`, `large` and `xlarge`. Anything else is an error at the write path
   (`init-workspace.sh`) and in `resolve-toolchain`. How heavy a project's
   lanes are is a property of the **project**, not of the site, so it may live
   in git. Which label serves each size stays in variables. A fork can only
   change sizes, never labels, and foreign runs go hosted anyway. *Cost:* one
   more manifest key (template comment, persistence, two validators), and the
   `runners` object grows lane keys.
2. **Fixed classes, no override.** It is the least surface. *Cost:* a project
   whose tests need XLARGE cannot get there without a devkit change. XLARGE
   exists but is unreachable.
3. **Per-lane variables** (`CI_RUNNER_TEST`, …). *Cost:* it puts a project
   property into org or repo settings, makes the variables sprawl, and an
   org-level per-lane variable applies to every repo.

**(c) In release N, does `devkit-upgrade` strip the legacy key or only warn?**

1. **Strip it when it is inert, otherwise keep it and explain
   (Recommended).** Inert means all three `CI_RUNNER_*` are visible to the
   upgrade job, so under (a)-1 the key decides nothing. Then removing it
   changes no runner, and the repo reaches the end state one release early.
   Otherwise the key stays, and the PR body names the variables to set.
   *Cost:* the upgrade's behaviour depends on variables the maintainer may not
   know are set. It is reported in the PR body. A local `install.sh --force`
   never strips, because it sees no variables.
2. **Warn only in N, strip in N+1.** *Cost:* every self-hosted consumer
   carries a dead key through N, and N+1's adoption PR must do the strip and
   explain it in one step.
3. **Always strip in N**, writing the needed settings into the PR body.
   *Cost:* a consumer that merges before setting the variables silently moves
   to hosted runners, the one outcome the design forbids. Rejected unless (a)
   changes.

**(d) Existing copies of the seeded release hooks** (`prepare-release-extension`,
`release-extension`, `publish-release-extension`), which are consumer-owned
and never overwritten.

1. **Reconcile the exact stock line (Recommended).** When a copy's `runs-on`
   is byte-identical to the stock
   `${{ vars.DEVKIT_CI_RESOLVE_RUNNER || 'ubuntu-26.04' }}`, the upgrade
   rewrites that line to the new LARGE direct expression and prints a
   `preserved-hook`-style reconcile line into the PR body. Any other content is
   left alone and reported as drift. This is the same precedent as the
   pre-commit reconcile ([#1654](https://github.com/vig-os/devkit/issues/1654)):
   a known-stock block may be folded, nothing else. *Cost:* a second
   reconcile implementation for workflow files, and a consumer-owned file
   changes in an adoption PR.
2. **Notice only.** *Cost:* existing copies keep reading
   `DEVKIT_CI_RESOLVE_RUNNER` forever, without the fork predicate. They run
   only on `workflow_call` from dispatch-only trains or on `release`, so there
   is no fork exposure, but the legacy variable can never be deleted.

**(e) `devkit-upgrade.yml`'s runner.**

1. **SMALL with the predicate (Recommended).** The job that delivers the
   migration should run where the org runs CI. A billing-blocked private org
   otherwise never adopts. Container-mode consumers' runners already have a
   container runtime (§5). *Cost:* the job mints the upgrade App token on a
   self-hosted runner, as the release train already does. Splitting
   secret-bearing jobs from build-only pools is
   [#1876](https://github.com/vig-os/devkit/issues/1876)'s job.
2. **Stay hosted, normalised to `ubuntu-26.04`.** *Cost:* the job keeps paying
   hosted minutes on private repos, and fails outright in an org that cannot
   run hosted jobs.

## Alternatives considered

- **Keep labels in `.vig-os` and add only the fork check.** This fixes the fork
  exposure but not the site leak. It is defect 1 of the problem statement.
- **One `CI_RUNNER` variable for all jobs.** It cannot express "resolve on a
  small pool, test on a large one", which is defect 3.
- **A JSON array in the variable** (`fromJSON(vars.X)`). It allows label lists,
  but the direct expressions would need `fromJSON` around a value that may be
  empty or a plain label, and the owner-tested form would no longer apply.
  Single labels map cleanly onto runner scale sets.
- **Secrets instead of variables.** Labels are not secrets. Secrets cannot be
  used in `runs-on` and are masked in logs, which would make runner selection
  undebuggable.
- **Detecting the plan or the visibility of org variables via the API.** This
  needs an admin-scoped token in every run. The step-summary hint (§3) and the
  docs cover the GitHub Free case without one.

## Consequences

- A fresh clone with no `.site/` and no variables passes CI on hosted runners.
  This is the #1908 acceptance, pinned by S1's no-variables test.
- Fork PRs into public consumers can no longer reach self-hosted runners
  through any devkit-managed path.
- Consumers that already set `CI_RUNNER_*` at org level adopt with no repo
  change. GitHub Free private repos need repository-level variables, and the
  docs, the step summary and the adoption PR say so.
- The `runner-json` action output and both legacy knobs disappear in N+1. The
  tombstones stay permanently.
- `DEVKIT_DEV_PROFILE_PATH` ([#1601](https://github.com/vig-os/devkit/issues/1601))
  is still a runner-host path in `.vig-os`, which is the same class of site
  fact in git that this ADR removes for labels. Moving it to the runner side
  is a **follow-up** for the architect to file. This ADR does not decide it.
- [#1891](https://github.com/vig-os/devkit/issues/1891) keys its cache profile
  on `runner-sources` instead of `DEVKIT_CI_RUNNER`.
- [#1907](https://github.com/vig-os/devkit/issues/1907) (`NIX_CONFIG` on
  self-hosted runners) is independent and out of scope.
- The `docs/issues/` and `docs/pull-requests/` mirrors are regenerated from
  GitHub by `sync-issues`. Site names in them can only be scrubbed at the
  source issues. That is an owner action outside this ADR.

## Implementation

Ordered sub-issues. The architect files them; this ADR does not. Each is under
about 400 diff lines. Files are disjoint except where noted. S1 → S2 → S3 must
land in the same release N. S4–S6 are independent of S1–S3 and of each other.
S7 (docs) follows S1–S6, S8 gates release N, and S9 is release N+1.

**S1 — Runner selection core: `resolve-toolchain` and `ci.yml`.**

- *Scope:* the §3 algorithm; the inputs `runner-small`, `runner-large`,
  `runner-xlarge` and `legacy-resolve-runner`; the outputs `runners`,
  `runner-sources` and the deprecated `runner-json` alias; the predicate
  evaluated in-action; diagnostics; `DEVKIT_CI_LANE_SIZES` parsing if (b)-1;
  `ci.yml` wiring per §4; the `.vig-os` template comments, replacing the
  site-specific example label with `<label>`; init-workspace write-path guard
  and persistence for `DEVKIT_CI_LANE_SIZES`.
- *Files:* `assets/workspace/.github/actions/resolve-toolchain/action.yml`,
  `assets/workspace/.github/workflows/ci.yml`, `assets/workspace/.vig-os`,
  `assets/workspace/.github/actionlint.yaml` (comment),
  `assets/init-workspace.sh` (lane-sizes guard only),
  `tests/test_ci_runner.py`, `tests/bats/init-workspace.bats` (lane-sizes
  cases).
- *Acceptance:*
  - executed-bash tests for each class and source: fork, variable,
    legacy-key, default;
  - variable wins over the key, per (a);
  - a malformed variable fails (comma, surrounding whitespace);
  - no variables and no key gives `ubuntu-26.04` everywhere;
  - deprecation warnings appear;
  - the private-and-all-default step-summary line appears;
  - a shape test that every non-literal `runs-on` in scaffolded workflows
    contains the predicate;
  - a test that no scaffolded workflow declares `workflow_run`;
  - `ci.yml` lanes reference `runners` per §4.

**S2 — Remaining scaffolded workflows.**

- *Scope:* `sync-issues`, `sync-main-to-dev`, `prepare-release`,
  `prepare-hotfix`, `release`, `release-core`, `release-publish`,
  `promote-release`, `abandon-release` and their resolvers per §4; the
  `runner-json` → `runners` input on the managed reusables; new-scaffold seeded
  hooks on the LARGE direct expression; `devkit-upgrade.yml` per (e).
- *Files:* those workflow files under `assets/workspace/.github/workflows/`,
  and the release-train and hook tests in `tests/test_ci_runner.py`. Not
  disjoint from S1: different test functions in the same file.
- *Acceptance:*
  - each resolver passes all four inputs;
  - each job's class matches §4;
  - managed reusables declare `runners`;
  - the seeded-hook input contract is unchanged;
  - seeded hooks use the new expression.

**S3 — `devkit-upgrade` migration.**

- *Scope:* §6: the variable-visible environment into `install.sh`; the legacy
  key handling per (c); the `ci-runner-migration:` lines; the "CI runner
  migration" PR-body section; the seeded-hook reconcile per (d).
- *Files:* `assets/init-workspace.sh` (the persistence block, not S1's
  section), `assets/workspace/.github/workflows/devkit-upgrade.yml` (the
  install and PR-body steps; S2 touches only `runs-on`),
  `tests/bats/init-workspace.bats` (migration cases), and the devkit-upgrade
  workflow tests.
- *Acceptance:* bats cases for every row of the §6 table, the strip/keep
  outcome per (c), the reconcile/drift lines per (d), and the PR body
  containing the lines.

**S4 — `.site/` convention and site-init hook.**

- *Scope:* §8–§9: vig-utils `site_config.py` (`check-site-config` with
  `--print-path`, `site-init`); the managed-justfile recipe `site-init`; the
  template `.gitignore` gains `.site/` and `.aws/`.
- *Files:* `packages/vig-utils/src/vig_utils/site_config.py`,
  `packages/vig-utils/pyproject.toml`, `assets/workspace/justfile`,
  `assets/workspace/.gitignore`, and new tests.
- *Acceptance:*
  - schema validation, including credential-key and userinfo rejection;
  - active-site lookup, including the ambiguity error;
  - discovery with zero, one and several fixture initialisers;
  - a failing or invalid initialiser leaves no files;
  - `--force` semantics;
  - the non-TTY template;
  - `.site/` and `.aws/` are ignored in a rendered scaffold.

**S5 — Env-only lint.**

- *Scope:* §10 lint.
- *Files:* `packages/vig-utils/src/vig_utils/check_hardcoded_endpoints.py`,
  `pyproject.toml` (script entry; shared with S4, one line), `nix/hooks.nix`
  (hook entry), `.pre-commit-config.yaml` (devkit's own), and tests.
- *Acceptance:*
  - each rule fires on a positive fixture;
  - references, RFC 2606 hosts and the pragma pass;
  - devkit's own tree passes;
  - the hook is present and enabled on the consumer surface.

**S6 — Site leak-check hook point.**

- *Scope:* §10 leak check.
- *Files:* `packages/vig-utils/src/vig_utils/site_leak_check.py`,
  `nix/hooks.nix` (a separate entry from S5), and tests.
- *Acceptance:*
  - no pattern file: exit 0 and silent;
  - the `DEVKIT_LEAK_PATTERNS` and `.site/` lookup order;
  - a staged match fails, with redacted output;
  - a tracked or in-tree pattern file is an error;
  - `--all-files` mode scans the tree.

**S7 — Documentation and scrub.**

- *Scope:*
  - rewrite `docs/MIGRATION.md` "Run CI on self-hosted runners" around the
    variables: repository-level on GitHub Free, fork safety, size classes,
    lane override, deprecation timeline; replace the site-specific example
    label and `gh variable set` value with `<label>`;
  - update the manifest key table;
  - `docs/DOWNSTREAM_RELEASE.md` (both copies): `runner-json` → lanes;
  - `docs/WORKFLOW_SECURITY.md`: the predicate and the trigger rules;
  - a new `docs/GOING_PUBLIC.md` (§10 checklist);
  - `.site/` and site-init docs in `docs/SOLO_ADOPTION.md`;
  - scrub the site-specific label from the `tests/bats/init-workspace.bats`
    fixtures. The S1 `.vig-os` scrub lands there.
- *Files:* the docs named above and the bats fixture strings.
- *Acceptance:* a `git grep` for the site label scrubbed in S1 and S7 returns
  nothing outside `docs/issues/` and `docs/pull-requests/`; docs lint passes;
  the CHANGELOG `### Deprecated` entry for both legacy knobs.

**S8 — Release N gate.**

- *Scope:* verify S1–S7 on the consumer matrix and in one self-hosted consumer
  before cutting N.
- *Files:* `scripts/consumer-matrix/render-cell.sh` and
  `tests/bats/consumer-matrix.bats`. The self-hosted cell seeds variables
  instead of the key.
- *Acceptance:* the matrix is green with the key only (warning path) and with
  variables only.

**S9 — Removal (release N+1).**

- *Scope:* §6 N+1: delete the legacy arms, keep the tombstones, remove the
  `runner-json` alias, drop the template key, and switch the direct expressions
  to the N+1 form.
- *Files:* `resolve-toolchain`, the scaffolded workflows, `.vig-os`,
  `init-workspace.sh`, tests, `MIGRATION.md`, and CHANGELOG `### Removed`.
- *Acceptance:* tombstone errors are tested for the key and for the variable;
  no managed file references `DEVKIT_CI_RESOLVE_RUNNER` in `runs-on`.
- Blocked by release N shipping.
