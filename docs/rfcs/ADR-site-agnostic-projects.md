---
rfc: ADR-site-agnostic-projects
date: 2026-10-26
title: Site-agnostic projects — fork-safe CI runner selection via variables, gitignored site config
status: accepted
authors:
  - Lars Gerchow (gerchowl)
---

# ADR: Site-agnostic projects and fork-safe CI runner selection

**Decision (TL;DR):** A project repo carries **no site or infrastructure
settings**. Where it runs is configured outside git: by GitHub variables for CI,
and by a gitignored `.site/` directory for everything else.

- **CI runners** come from the GitHub variables `CI_RUNNER_SMALL`,
  `CI_RUNNER_LARGE` and `CI_RUNNER_XLARGE` (repository or organization level),
  never from repo content. Every managed lane belongs to one **size class**,
  and **every lane defaults to SMALL**. A project opts a lane into LARGE or
  XLARGE with `DEVKIT_CI_LANE_SIZES` (decision (b)). Unset or empty means the
  hosted default, **`ubuntu-26.04`**.
- **Fork-safe on every path:** a pull request from another repository never
  requests a self-hosted label. This holds for the variables, for the legacy
  `.vig-os` key and for the legacy resolve variable. The check is explicit even
  though GitHub gives fork PRs no variables.
- **A two-release compatibility window:** `.vig-os` `DEVKIT_CI_RUNNER` and
  `vars.DEVKIT_CI_RESOLVE_RUNNER` keep working in releases N and N+1. Every CI
  run carries a `::warning::` with the full migration text, and that warning
  is the primary channel. `devkit-upgrade` cleans up whenever a ≥N copy of
  its workflow first runs from the default branch. Release N+2 removes both
  knobs. A leftover key that would still decide a runner then **fails CI
  loudly**. An inert one only warns. Nothing degrades silently to hosted
  runners.
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
in [Evidence](#evidence-the-2026-10-25-variable-tests). The owner took six
decisions on 2026-10-26, choosing a1, b1, c1, d1, e1 and f1; see
[Decisions](#decisions).

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
| `CI_RUNNER_SMALL` | one runner label for every lane by default: orchestration (resolve, gates, release-train steps), the toolchain lanes (lint, tests) and the seeded hooks |
| `CI_RUNNER_LARGE` | one runner label for the lanes a project moves to LARGE with `DEVKIT_CI_LANE_SIZES`; no lane uses it by default |
| `CI_RUNNER_XLARGE` | one runner label for the lanes a project moves to XLARGE with `DEVKIT_CI_LANE_SIZES`; no lane uses it by default |

- Set at **repository** or **organization** level. On GitHub Free, private
  repos must use repository-level variables (Evidence, finding 1).
- **The value is exactly one label.** That is the canonical form of every
  `CI_RUNNER_*` value, and no resolver path accepts anything else: a comma
  list or a JSON list is an error, not a tolerated spelling (the comma-split
  of the legacy `DEVKIT_CI_RUNNER` key in §3 is a property of that key, not of
  the variables). The direct `runs-on` expression reads a
  variable as a single label, so the `runner-json` path must not read it any
  other way. One whitespace rule applies everywhere, and a blank label is never
  emitted:
  - **empty** means unset;
  - **whitespace-only** means unset plus a `::warning::` (§3);
  - any value that is not a **valid label** is an `::error::` naming the
    variable, in `resolve-toolchain` (§3). A valid label matches
    `^[A-Za-z0-9][A-Za-z0-9._:/-]*$`: letters, digits and `. _ : / -`, starting
    with a letter or digit. That rejects a comma list, a JSON list
    (`["pool-l"]`, by `[`, `]`, `"` and `,`), leading or trailing whitespace
    and any inner whitespace. A direct expression would request a label no
    runner carries and queue forever.

  GitHub's own expressions are the one exception to the "never blank" rule:
  they treat a whitespace-only string as truthy. That affects only the
  direct-expression jobs, which read SMALL: the resolve jobs and the seeded
  hooks. For a whitespace-only SMALL, the resolve job never starts (the known
  limit below), so the run shows a job queued on a blank label, and
  `MIGRATION.md` names that symptom. For a whitespace-only LARGE or XLARGE,
  which no direct expression reads, the resolve job's warning names the
  variable to delete and the lanes that opted into that class treat it as
  unset. A pool that needs several labels
  gets one unique custom label. Runner scale sets already work that way.
  **Known limit:** `CI_RUNNER_SMALL` also selects the resolve job's own runner,
  so a malformed SMALL value is never validated. The resolve job queues on the
  bogus label instead, exactly like today's `DEVKIT_CI_RESOLVE_RUNNER`. The
  docs state this, and deleting the variable recovers with no commit.
- **The classes are independent. There is no cross-class fallback.** A lane
  whose class variable is unset runs hosted, even when another class is set.
  Falling back to a smaller pool would put a heavy lane on a runner sized for
  orchestration and fail by OOM. Falling back to a larger pool would spend
  capacity the org did not allocate. `resolve-toolchain` reports each class's
  source (§3), so a partial setup is visible, not silent. When the effective
  lane map opts a lane into a class whose variable is not visible on a
  non-fork run, the lane still runs hosted, and `resolve-toolchain` emits a
  `::warning::` naming the variable and the affected lanes (§3).
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
same `pull_request` payload. It does **not** cover two triggers:

- **`workflow_run`:** the payload has no `pull_request` object.
- **`merge_group`:** a queued fork PR runs in the base context, with
  variables, on a `gh-readonly-queue/...` ref of the base repository. The
  payload has no head-repository field from which the predicate could tell a
  fork apart.

No managed workflow uses either trigger today. A test forbids both in
scaffolded workflows (S1). Adding either one is a design change: it needs its
own predicate clause and evidence first, not just a trigger line.

### 3. Resolution order per job class

There are two job classes: jobs whose `runs-on` is a **direct expression**,
and jobs that consume `resolve-toolchain`'s outputs (**runner-json lanes**).

#### Direct-expression jobs

These are the `resolve-toolchain` jobs (SMALL), which produce the outputs and
cannot consume them, and the seeded extension hooks (SMALL, §5), whose callers
pass them no runner input.

Compatibility releases N and N+1, per decision (a)-1:

```yaml
runs-on: ${{ (github.event.pull_request && (github.event.pull_request.head.repo.fork || github.event.pull_request.head.repo.full_name != github.repository) && 'ubuntu-26.04') || vars.CI_RUNNER_SMALL || vars.DEVKIT_CI_RESOLVE_RUNNER || 'ubuntu-26.04' }}
```

Release N+2 and later: **unchanged**. The legacy term stays as the last term
before the hosted default, **only** to carry the tombstone (below). A consumer
left with only `DEVKIT_CI_RESOLVE_RUNNER` gets a resolve job on its own runner,
which then fails with an explanation. Dropping the term would send that
consumer's resolve job to a hosted runner. A billing-blocked org cannot run it
there, so the job would fail before any step and the explanation would never
print. The term never selects a runner when `CI_RUNNER_SMALL` is set.

New seeded hooks use
`${{ (github.event.pull_request && (github.event.pull_request.head.repo.fork || github.event.pull_request.head.repo.full_name != github.repository) && 'ubuntu-26.04') || vars.CI_RUNNER_SMALL || 'ubuntu-26.04' }}` and never
reference `DEVKIT_CI_RESOLVE_RUNNER`. They read SMALL, like every other lane
by default (§5), so the direct expression is the same class as the resolve
jobs'. GitHub expressions treat `''` as false, so an empty variable falls
through. A whitespace-only value is truthy there and requests a blank label
(§1). The resolve job cannot report that for its own runner (the §1 known
limit), and since it reads the same variable, a whitespace-only SMALL stops the
run before any seeded hook is reached. The runner-json lanes treat a
whitespace-only value of any class as unset.

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
raw = input runner-<S>                           # from vars.CI_RUNNER_<S>
V = trim(raw)
if raw != "" and V == "":  ::warning:: whitespace-only CI_RUNNER_<S>, treated as unset
if raw != "" and V != "" and not match(raw, r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"):
                           ::error:: naming CI_RUNNER_<S> + exit 1   # validate the RAW value
                           # rejects "," "[" "]" '"' and any surrounding or inner whitespace
L = labels(.vig-os DEVKIT_CI_RUNNER)             # releases N, N+1 only: comma-split,
                                                 # each label trimmed, empties dropped
if   F:                 runners[S] = [H];  source[S] = "fork"
elif V != "":           runners[S] = [V];  source[S] = "variable"
elif L != []:           runners[S] = L;    source[S] = "legacy-key"     # releases N, N+1 only
else:                   runners[S] = [H];  source[S] = "default"
```

The precedence shown is decision (a)-1: the variable wins over the legacy
key.

Lane entries are then resolved from the lane → class map: built-in defaults
(§5), plus the `.vig-os` `DEVKIT_CI_LANE_SIZES` override (decision (b)-1),
it. Each lane gets `runners[<lane>] = runners[<class>]`.

**Outputs:**

- `runners` is a JSON object that maps each class and each overridable lane to
  a label array, for example
  `{"small":["pool-s"],"large":["ubuntu-26.04"],"xlarge":["ubuntu-26.04"],"lint":["pool-s"],"test":["pool-s"],"extension":["pool-s"],"release-test":["pool-s"]}`
  for a consumer that sets only `CI_RUNNER_SMALL` and keeps the default lane
  map. With `DEVKIT_CI_LANE_SIZES=test=large` and `CI_RUNNER_LARGE=pool-l`,
  the `test` entry becomes `["pool-l"]`.
  Lanes declare `runs-on: ${{ fromJSON(needs.resolve-toolchain.outputs.runners).small }}`
  for an orchestration job, or `.test`, or `['release-test']`.
- `runner-sources` is a JSON object that maps each class to `fork`, `variable`,
  `legacy-key` or `default`. It is printed as a table in the step summary. It
  is also the signal [#1891](https://github.com/vig-os/devkit/issues/1891)'s
  cache profile reads instead of `DEVKIT_CI_RUNNER`.
- `runner-json` is kept in releases N and N+1 as a **deprecated alias** of
  `runners.small`, for consumer-written jobs that reference it. SMALL is the
  default class of every lane (§5), and a legacy-key consumer has one pool
  for all classes, so the alias keeps resolving to the pool those jobs used.
  It is removed in N+2. A removed output reaches `fromJSON('')`, which fails the job loudly.

**Diagnostics.** None of them can be silenced:

- If `L` is non-empty: `::warning::` carrying the **full, actionable migration
  text**. This is the primary migration channel (§6), because it reaches every
  consumer on every run, whatever their branch model and whenever their
  `devkit-upgrade.yml` updates. The text says:
  - `DEVKIT_CI_RUNNER` is deprecated and stops selecting runners in N+2;
  - which required classes have no visible variable, and that they should be
    set, at repository level on a private GitHub Free repo
    (`gh variable set CI_RUNNER_<S> --body <label>`);
  - each class whose variable already overrides the key, which per
    decision (a)-1 the key no longer decides;
  - once every required class is set, the key decides nothing and should be
    deleted from `.vig-os`;
  - the `MIGRATION.md` anchor.

  It never prints the label.
- If `legacy-resolve-runner` is non-empty: `::warning::` that
  `DEVKIT_CI_RESOLVE_RUNNER` is deprecated in favour of `CI_RUNNER_SMALL`.
- If a variable is malformed: `::error::` and exit 1, before any lane is
  scheduled.
- If the run is not foreign and the effective lane map **opts a lane into a
  class** (LARGE or XLARGE, through `DEVKIT_CI_LANE_SIZES`) whose
  `source` is `default`, so its variable is not visible: a `::warning::`
  that names the variable (`CI_RUNNER_LARGE`) and the affected lane(s), and
  says those lanes run on the hosted default until the variable is set. The
  hosted fallback stays, and there is no cross-class fallback (§1). A class
  that came from `legacy-key` is covered by the legacy-key warning above
  instead. This catches the case where the key was stripped under (c)-1 and a
  later opt-in lacks its variable.
- If the run is not foreign, at least one **required class** came from
  `variable` and another required class came from `default`: `::notice::`
  naming the unset classes. This is the partial-setup case (for an opted-in
  class the `::warning::` above fires as well). The required
  classes are **exactly the classes the effective lane map uses**: the §5
  default map (every lane SMALL, which includes the seeded hooks and the
  `runner-json` alias) plus the classes named by the repo's
  `DEVKIT_CI_LANE_SIZES` override. So SMALL is always required, and LARGE or
  XLARGE is required only when an override moves a lane there. A class no
  lane uses is never required, whether or not its variable is set. A consumer
  that keeps the default map and sets only SMALL is fully set up and sees no
  notice. With `DEVKIT_CI_LANE_SIZES=test=large`, SMALL and LARGE are
  required, and setting only SMALL gives the notice and the warning naming
  LARGE and the `test` lane.
- If the repo is private, the run is not foreign, and **no** `CI_RUNNER_*`
  variable is visible: a `::notice::` annotation on the run, plus a
  step-summary line. It says that CI runs on hosted runners, that on GitHub
  Free organization variables do not reach private repos, and that the fix is
  repository-level variables. This is the near-silent case of Evidence finding
  1, so it needs an annotation and not just a summary line. A private repo that
  runs hosted **on purpose** silences it by setting the variables to
  `ubuntu-26.04`. That is an explicit statement and not an opt-out knob, and it
  is never silenced by default. Only a private-and-unconfigured repo sees it,
  because a public repo has free hosted minutes.

  **Limit:** the notice is printed by the resolve job, which runs hosted in
  exactly this case. If the repo cannot run hosted jobs at all (a billing
  block, or a Free-plan private repo out of included minutes), GitHub rejects
  or never starts that job, so the notice never prints. What the consumer
  sees instead is GitHub's own message on the failed or queued `Resolve
  toolchain` job, which concerns billing or spending limits rather than
  devkit. The `MIGRATION.md` self-hosted section (S7) has a "CI never starts
  on a private repo" entry that maps that symptom to the cause: org variables
  do not reach private repos on Free, so set repository-level variables.

**Release N+2** deletes the `L` arm and keeps two **permanent tombstones**:

- A non-empty `DEVKIT_CI_RUNNER` in `.vig-os` is gated on the **consumer's
  own state**, not on which devkit-upgrade run happened:
  - **The key still decides something.** Some required class (§3) has no
    visible variable, on a run that is not foreign. That is an `::error::`
    carrying the same full migration text as the N/N+1 warning. CI goes red.
    It never silently moves to hosted runners.
  - **The key is inert.** Every required class has a visible variable, so
    per decision (a)-1 the key already decided nothing during the window.
    That is a `::warning::` asking to delete the key. Removing the legacy arm
    changes no runner here, so failing the run would be noise.
  - **Foreign runs.** Variables are hidden there, so inertness cannot be
    judged. The result is a `::warning::`, and the base repository's own runs
    give the verdict.

- A non-empty `legacy-resolve-runner` with an empty `runner-small`, on a run
  that is not foreign, is an `::error::`. The consumer clearly meant
  self-hosted runners, and the resolve job still runs on the legacy variable's
  label (see the N+2 expression), so the error is reachable. With
  `CI_RUNNER_SMALL` set, it is only a `::warning::`, because the variable may
  still serve pre-N seeded hook copies (decision (d)).

The tombstones are a few lines each and are never removed. A repo that skips
the compatibility releases, or whose migrating adoption never ran, still gets
a loud failure where one is due, and not a silent
degrade.

### 4. Inventory: every job that selects a runner

Classes: **S** = SMALL (the default class of every lane, including the
overridable ones; a project may move an overridable lane to LARGE or XLARGE,
§5), **hosted** = literal `ubuntu-26.04`, unchanged. "runner-json" means
`fromJSON(needs.<resolver>.outputs.runner-json)` today. "resolve var" means
`vars.DEVKIT_CI_RESOLVE_RUNNER || 'ubuntu-26.04'`. Every target row that is not
hosted uses the fork predicate.

#### Scaffolded workflows (`assets/workspace/.github/workflows`)

| Workflow (triggers) | Job | Today | Target |
|---|---|---|---|
| `ci.yml` (pull_request, workflow_dispatch) | `resolve-toolchain` | resolve var | S, direct expression |
| | `lint` | runner-json | S, lane `lint` |
| | `test` | runner-json | S, lane `test` |
| | `commit-checks` | runner-json | S |
| | `scaffold-drift` | runner-json | S |
| | `devkit-staleness` | runner-json | S |
| | `dependency-review` | hosted | hosted (public repos only) |
| | `extension` → `ci-extension.yml` | passes `runner-json` | passes lane `extension` (S) as `runner-json` |
| | `summary` | runner-json | S |
| `ci-extension.yml` (workflow_call, seeded) | `extension` | `fromJSON(inputs.runner-json)` | unchanged; the caller now passes the `extension` lane |
| `sync-issues.yml` (schedule, workflow_dispatch) | `resolve-toolchain` / `sync` | resolve var / runner-json | S / S |
| `sync-main-to-dev.yml` (push, workflow_dispatch) | `resolve-toolchain` / `check`, `sync` | resolve var / runner-json | S / S |
| `prepare-release.yml` (workflow_dispatch) | `validate` (is the resolver) | resolve var | S, direct expression |
| | `prepare`, `open-pr`, `rollback` | `needs.validate` runner-json | S |
| | `extension` → `prepare-release-extension.yml` | (no input) | (no input) |
| `prepare-hotfix.yml` (workflow_dispatch) | `resolve-toolchain` / `validate`, `prepare`, `open-pr`, `rollback` | resolve var / runner-json | S / S |
| | `extension` → `prepare-release-extension.yml` | (no input) | (no input) |
| `release.yml` (workflow_dispatch) | `resolve-toolchain` / `rollback` | resolve var / runner-json | S / S |
| | `extension` → `release-extension.yml` | (no input) | (no input) |
| | `core` → `release-core.yml`, `publish` → `release-publish.yml` | pass `runner-json` | pass `runners` |
| `release-core.yml` (workflow_call, managed) | `validate`, `finalize` | `fromJSON(inputs.runner-json)` | S from `fromJSON(inputs.runners)` |
| | `test` | `fromJSON(inputs.runner-json)` | S, lane `release-test` |
| `release-publish.yml` (workflow_call, managed) | `publish` | `fromJSON(inputs.runner-json)` | S from `fromJSON(inputs.runners)` |
| `promote-release.yml` (workflow_dispatch) | `resolve-toolchain` / `validate`, `promote`, `merge`, `cleanup`, `floating-tags` | resolve var / runner-json | S / S |
| `abandon-release.yml` (workflow_dispatch) | `resolve-toolchain` / `validate`, `abandon` | resolve var / runner-json | S / S |
| `prepare-release-extension.yml` (workflow_call, seeded) | `extension` | resolve var | new scaffolds: S, direct expression; existing copies: decision (d) |
| `release-extension.yml` (workflow_call, seeded) | `extension` | resolve var | same as above |
| `publish-release-extension.yml` (release, workflow_dispatch; seeded) | `resolve`, `publish` | resolve var | same as above |
| `devkit-upgrade.yml` (schedule, workflow_dispatch) | `upgrade`, `report` | `ubuntu-latest` | S, with the fork predicate (decision (e)-1) |
| `codeql.yml` (pull_request, push, schedule) | `analyze` | hosted | hosted (public repos only) |
| `assets/smoke-test/.github/workflows/ci-extension.yml` (workflow_call; the smoke-test fixture's hook) | `extension` | `fromJSON(inputs.runner-json)` | unchanged; receives the `extension` lane from the caller |
| `assets/smoke-test/.github/workflows/direnv-smoke.yml`, `repository-dispatch.yml` | all jobs | hosted | hosted (devkit's own smoke-test fixture) |
| `scorecard.yml` (schedule, push) | `analysis` | hosted | hosted (public repos only) |

The `release-core` and `release-publish` input changes from `runner-json` to
`runners`. Both files are managed, so caller and callee always ship together.
The seeded hooks' inputs do **not** change: the
`test_callers_pass_only_inputs_the_oldest_seeded_hook_declares` contract holds.

**Every seeded-hook job is S, including `publish-release-extension`'s short
`resolve` job.** One stock expression for every seeded job keeps the (d)
reconcile a byte-exact, per-line match with a single replacement. The hooks
take no lane override, because their callers pass them no runner input. The
files are consumer-owned, so a consumer whose hook needs a heavier pool edits
its own copy.

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

Default map, with the per-lane override of decision (b)-1:

| Class | Lanes |
|---|---|
| SMALL | **every lane**: `lint`, `test`, `extension` (`ci-extension`), `release-test` (`release-core` `test`), the seeded release hooks, `resolve-toolchain` jobs and resolvers (`prepare-release` `validate`), `commit-checks`, `scaffold-drift`, `devkit-staleness`, `summary`, `sync-*`, release-train orchestration, `devkit-upgrade` (decision (e)) |
| LARGE | no default lane; reachable only through the decision (b) override, e.g. `DEVKIT_CI_LANE_SIZES=test=large` |
| XLARGE | no default lane; reachable only through the decision (b) override |

**Why SMALL for everything.** Self-hosted pools usually hold far fewer large
runners than small ones. A real consumer pool has per-org capacity of
SMALL ≤ 4–6, LARGE ≤ 2 and XLARGE ≤ 1. With `lint`, `test`, `extension` and
`release-test` on LARGE by default, one PR occupies every LARGE slot, a second
PR queues, and the small slots sit idle. Most dev-shell realisation is
substituted from a binary cache, so `lint`, drift and the similar lanes are
light. SMALL is therefore the default, and a project opts a lane into LARGE or
XLARGE where its own tests need it. How heavy a project's tests are is a
project property, so the opt-in lives in `.vig-os` (decision (b)), while which
label serves each size stays in the variables.

A container-mode consumer's runners already need a container
runtime for the `container:` lanes, so any class it routes is container-capable.

### 6. Migration

#### Which adoption can migrate

`devkit-upgrade` runs the consumer's **own, already-installed**
`devkit-upgrade.yml`, from the **default branch**: scheduled and dispatched
runs use the default branch's copy of the workflow. Only `install.sh` comes
from the target tag. The pre-N workflow passes no `vars.CI_RUNNER_*` into the
install step, and it lifts only `flake-bump:` and `preserved-hook-*:` lines
into the PR body.

Adoption PRs target `dev` under gitflow (`main` under trunk), so N's
`devkit-upgrade.yml` reaches the default branch only when the consumer
releases `dev` to `main`. **The migrating adoption** is therefore defined as
*the first adoption run by a `devkit-upgrade.yml` of version N or later from
the default branch*. Under trunk that is N+1's adoption. Under gitflow it is
the first adoption after the consumer's own next release, which may come
after N+1, after N+2, or not before removal at all. **The design must not
depend on when, or whether, it runs.**

Rejected alternatives:

- **`install.sh` reads the variables through the API.** The pre-N install step
  exports no `GH_TOKEN`; its token appears only inside `NIX_CONFIG`. Reading
  variables also needs a token scope devkit cannot grant retroactively.
- **Emit the migration through a channel the old workflow already lifts.**
  `flake-bump:` keeps only one line, and the `preserved-hook-*:` lines land
  under headings that say "hook block". Smuggling a runner migration through
  them would put the wrong instruction in front of the maintainer.
- **Gate the removal itself on a migration marker** (keep the legacy arm
  until a migrating adoption has run). This leaves compat code alive
  indefinitely for any consumer that never releases, and it adds a persisted
  marker whose only job is bookkeeping. The consumer-state tombstone below
  reaches the same safety with no marker.

#### The chosen mechanism

1. **The per-run warning is the primary channel.** From N on, the scaffolded
   `ci.yml` emits the full actionable migration text on every run (§3
   diagnostics), starting with the N adoption PR's own CI, which already runs
   N's `ci.yml` and N's resolve action. No
   consumer depends on an adoption PR body to learn what to do.
2. **The N+2 tombstone is gated on the consumer's own state** (§3): an error
   only when the key would still decide a runner, and a warning when every
   required variable is set. A consumer whose migrating adoption never ran,
   but who acted on the warnings, stays green at N+2. One who did not act gets
   a red run carrying the full migration text, which is the loud failure the
   design requires.
3. **The migrating adoption is a convenience that cleans up**, whenever it
   happens. `init-workspace.sh`:
   1. reads the **migration environment** defined below. A ≥N
      `devkit-upgrade.yml` passes its visible `${{ vars.CI_RUNNER_* }}`
      values through `install.sh`, so they are what CI will see. On GitHub
      Free, org variables are invisible there too, which is correct. Under
      a pre-N workflow, or a local `install.sh --force`, the CI context is
      absent, so variables are unknown and nothing is stripped;
   2. applies decision (c) to a non-empty legacy key;
   3. prints exactly one `ci-runner-migration:` line per finding. A ≥N
      workflow lifts the lines into the step summary and the adoption PR body
      under a **"CI runner migration"** heading. A pre-N workflow drops them,
      which is harmless because of points 1 and 2.

The PR-body text a ≥N workflow shows, per case:

| Legacy key | Visible variables | PR body says |
|---|---|---|
| set | every required class (§3) | key removed (decision (c)-1); runners now come from the variables; nothing to do |
| set | some required classes or none | which `CI_RUNNER_*` to set, at **repository level** if the repo is private on GitHub Free; the example command `gh variable set CI_RUNNER_<S> --body <label>` with `<S>` each required class; until N+2 the key keeps working, and after that CI fails until the variables are set |
| unset, `vars.DEVKIT_CI_RESOLVE_RUNNER` visible | n/a | rename the variable to `CI_RUNNER_SMALL`, then delete the old one after decision (d)'s hook migration |
| unset, repo private, no `CI_RUNNER_*` visible | none | one informational line: CI runs hosted; organization variables do not reach private repos on GitHub Free; set repository variables, or set them to `ubuntu-26.04` to declare hosted on purpose (§3) |
| unset, any other case | n/a | nothing (no line printed) |

The PR body never repeats the label itself. It names variables, not values,
even though the value is already in git, so the adoption PR does not spread
the label further.

#### Migration environment

The upgrade job exports `DEVKIT_UPGRADE_CONTEXT=1`,
`DEVKIT_UPGRADE_CI_RUNNER_SMALL`, `DEVKIT_UPGRADE_CI_RUNNER_LARGE` and
`DEVKIT_UPGRADE_CI_RUNNER_XLARGE` from its visible `vars.CI_RUNNER_*`,
`DEVKIT_UPGRADE_LEGACY_RESOLVE_RUNNER` from `vars.DEVKIT_CI_RESOLVE_RUNNER`,
and `DEVKIT_UPGRADE_REPO_PRIVATE` from `github.event.repository.private`
(`true`/`false`). Invisible variables are empty. One explicit allow-list in
`install.sh` forwards these six names through both the direnv `env -i` and
container `-e` paths. Without context `1`, variables are unknown and the key
is always kept, including local force installs. With context `1`, stripping
requires a non-empty valid single label for every required class. Migration
text names variables and never repeats their values.

#### Deprecation timeline

- **Release N:** variables plus the fork predicate everywhere, the per-run
  migration warning, and the new `devkit-upgrade.yml`. The legacy key and the
  legacy variable keep working. `MIGRATION.md` gets the new section, and
  CHANGELOG `### Deprecated` names both legacy knobs and the removal release
  N+2.
- **Release N+1:** no new runner semantics. This gives a second release of
  per-run warnings, and gives trunk consumers (and gitflow consumers that
  released N) their migrating adoption.
- **Release N+2 (removal):** the legacy arms are deleted, the consumer-state
  tombstones (§3) stay, the `runner-json` alias output is removed, and the
  template `.vig-os` drops the `DEVKIT_CI_RUNNER=` line. Under a ≥N workflow,
  `init-workspace.sh` strips an inert key. Otherwise it keeps the key, which
  is harmless if inert (a warning) and red with the full text if not.
  CHANGELOG `### Removed`.

**Why stripping under (c)-1 stays safe.** Inertness is judged against the
effective lane map **at strip time**: every class a lane uses has a visible
variable, so removing the key moves no runner. A later change can add a lane
to a class with no variable, for example `DEVKIT_CI_LANE_SIZES=test=large`
without `CI_RUNNER_LARGE`. The key no longer exists to serve that lane, so it
runs hosted, which is a deliberate change by the project and not a silent
degrade: every non-foreign run emits the §3 `::warning::` naming
`CI_RUNNER_LARGE` and the `test` lane until the variable is set.

*Cost:*

- The window is two releases instead of the one in the
  `DEVKIT_UPGRADE_APP_ID` precedent
  ([#1366](https://github.com/vig-os/devkit/issues/1366)), which needed no
  workflow-side migration.
- Gitflow consumers that do not release between N and N+2 never get the
  convenience PR section. They rely on the per-run warnings, and they delete
  an inert key by hand, or let the next migrating adoption strip it.
- The tombstone needs the same variable inputs as the resolution algorithm,
  which it already has.

#### Failure mode after removal

A repo still holding a **non-inert** `DEVKIT_CI_RUNNER` in N+2 (some required
class without a visible variable) gets a red `Resolve toolchain` job with:

```text
::error::DEVKIT_CI_RUNNER in .vig-os stopped selecting runners in devkit <N+2>; CI runners now come from the variables CI_RUNNER_SMALL/LARGE/XLARGE (repository level on private GitHub Free repos). Unset here: <classes>. Set them, delete the key, and re-run. See MIGRATION.md#run-ci-on-self-hosted-runners.
```

**Limit:** the error comes from the resolve job. A repo that set **only** the
`.vig-os` key, with neither `CI_RUNNER_SMALL` nor `DEVKIT_CI_RESOLVE_RUNNER`,
has always resolved on hosted runners. If its org cannot run hosted jobs at
all, that job fails before any step in N+2, exactly as it did before, and the
message cannot print. For that population, the guarantee is the per-run
warnings of releases N and N+1. Those run on the same hosted resolve job, so
such a repo is in the §3 notice limit and is pointed at by the same
`MIGRATION.md` "CI never starts" entry. In every case the run is red, never
green.

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
     variables' behaviour does nothing for it in releases N and N+1.
- **Forks of private repos** are foreign too, so they run hosted. In a
  billing-blocked private org they get no CI. That cost, and its remedy, is
  decision (f).
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
  location = "s3://bucket/prefix/raw"   # required: empty (unbound), URI or absolute path

  [output]
  location = "/srv/project/out"        # optional

  [hints]                        # optional; string values; devkit never interprets them
  runner = "large"
  scheduler = "slurm"
  ```

- **Unbound locations.** Schema v1 accepts an empty location as unbound.
  Validation reports a notice listing unbound dataset names and exits 0;
  malformed bound locations (including relative paths) are errors. Bound
  locations are absolute paths or `scheme://location` URIs with schemes `s3`,
  `gs`, `az`, `abfs`, `http`, `https`, or `file`. A URI needs a non-empty
  authority for remote URIs. `file:///absolute/path` has no authority,
  query, fragment or `..` segment (including percent-encoded segments).
  `s3://bucket/key` accepts general-purpose bucket names following the
  [AWS naming rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html):
  3–63 lowercase letters, digits, dots or hyphens; alphanumeric ends; no
  adjacent dots, IP-address forms, reserved prefixes or alias/directory/table
  suffixes. Arbitrary `scheme:value` and bare `host:port` forms are rejected.
  Every location rejects whitespace, Unicode control characters (category Cc),
  and U+2028/U+2029 before parsing, including in absolute paths. Errors name
  the dataset or output field and never echo the location value. Consumers
  must refuse an unbound location with an actionable error naming the dataset
  key (future data recipes: #1921). S4 has no binding consumer.
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

- **Root and isolation:** resolve the repository root using
  `git rev-parse --show-toplevel` and resolve its symlinks, regardless of the
  caller's cwd. Outside a git work tree, both commands refuse with exit 2.
  All config paths, initializer cwd and discovery boundaries use this root.
  A linked worktree's toplevel is its root: `.site/` is per worktree, never
  shared via the common git directory.
- **Reserved names:** `leak-patterns` (case-insensitive) is reserved for the
  pattern file, and is refused with exit 2 in initializer selection/output,
  interactive fallback and `DEVKIT_SITE`.

- **Recipe:** `just site-init [site] [--force]` in the managed root `justfile`,
  the one layer present in every delivery mode, like `doctor`. It calls the
  vig-utils console script `site-init`.
- **Discovery:** executables on `PATH` named `devkit-site-init-<site>`, with
  `<site>` matching `[a-z0-9][a-z0-9-]*`. With an argument, that initialiser
  runs. Without one: exactly one found runs; several is an error that lists
  them; none uses the fallback. Only absolute PATH entries outside the repo
  working tree are searched. Resolved directories and executable targets
  inside the working tree are excluded, including symlinks into it.
- **Invocation:** cwd is the repo root, and stdin, stdout and stderr are
  inherited, so an initialiser may prompt. Environment:
  - `DEVKIT_SITE=<site>`
  - `DEVKIT_SITE_DIR=<abs staging dir>`, a fresh `.site/.staging-<random>/`
  - `DEVKIT_DATA_MANIFEST=<abs path to data.toml>`, or empty

  No arguments.
- **Initialiser obligations:**
  - write `$DEVKIT_SITE_DIR/<site>.toml` (schema v1), and optionally
    `$DEVKIT_SITE_DIR/leak-patterns.toml`;
  - write nothing else in the repo; writing outside staging is the
    initialiser's responsibility. devkit detects new or modified `.site/`
    entries recursively outside its staging directory, comparing relative
    paths, types, sizes, mtimes and inodes, reports their names and fails.
    Symlinks and special files anywhere under `.site/` are refused.
    It does not sandbox the initialiser or remove its out-of-contract writes;
  - put no credentials in either file;
  - exit 0 on success.

  **Known limit:** this detects changes after execution; it is not a sandbox
  or protection against a trusted initializer restoring metadata. Use only
  trusted initializers. devkit cannot undo arbitrary writes outside staging.

  It may configure credentials **outside** the repo (its own store, `~/.aws`)
  or in the gitignored `.aws/`.
- **devkit then:**
  - validates `<site>.toml` with `check-site-config`. For the optional
    `leak-patterns.toml`, uses the public
    `vig_utils.site_config.validate_patterns(path: Path) -> None` validator.
    Its self-contained pattern-file contract is the **S4 pattern-file
    clarification** in [Amendments](#decisions). Site-binding credential
    restrictions do not apply to pattern values; gitleaks validates remaining
    config semantics;
  - on success, moves them into `.site/`; existing files are refused without
    `--force`;
  - on a non-zero exit or an invalid file, deletes the staging directory and
    fails with the initialiser's exit code or the validation error, so nothing
    is left half-written. If this run created `.site/` and it is empty after
    cleanup, removes it; existing directories are preserved.
- **Fallback (no initialiser):** on a TTY, prompt for the site name (default
  `local`), one location per `data.toml` dataset and the output location. Off a
  TTY, write `.site/local.toml` with every declared dataset present, empty locations and comments, and print
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

## Decisions

Decided by the owner on 2026-10-26, on PR
[#1917](https://github.com/vig-os/devkit/pull/1917): **a1, b1, c1, d1, e1, f1**.
Each option chosen was the one this ADR considers correct in the long term.
The rejected options are kept with the costs that ruled them out.

**Amendments**

- **2026-10-29, architect, S4 pattern-file clarification (shared with S6):**
  `validate_patterns(path: Path) -> None` accepts a missing file as no check.
  Otherwise parse TOML and compare keys case-insensitively. Duplicate case
  variants at the same level (top level or within rules and nested tables)
  are an error naming the file and key, never values. A usable `[[rules]]`
  entry has a nonempty string `id` and at least one nonempty string `regex`
  or `path`. Zero usable rules (including an empty file, `[[rule]]` typo or
  `[rules]` table) is an error. `[extend]` in any case is forbidden: pattern
  files must be self-contained. Errors raise `ValueError` without pattern
  values. This is the single S4/S6 contract; no change to accepted decisions.

- **2026-10-29, architect clarification of (d)-1 while reviewing S3:**
  stock includes every runner value ever seeded by a release or dev build,
  not only the legacy resolve-variable expression originally named below.
  Fold only with a valid SMALL variable in the CI upgrade context; otherwise
  preserve and report pending. Classify values independently of layout,
  preserve indentation and line endings, and report custom or unclassified
  content as drift. Runner findings use the §6 migration channel so pre-N
  workflows do not mislabel them. Suggest deleting the legacy resolve variable
  only when every seeded hook job is reconciled.

- **2026-10-27, architect clarification found while implementing S3:**
  `install.sh` is in scope for forwarding the migration environment above;
  no change to accepted decisions.

- **2026-10-27, architect clarification found while implementing S1b:**
  duplicate lanes are an error; no change to accepted decisions.

- **2026-10-27, architect clarification:** resolve the §8/§9 contradiction
  found while implementing S4: empty locations are valid unbound bindings,
  reported as notices. No change to accepted decisions.

- **2026-10-26, owner: the default lane map puts every lane on SMALL**
  (§5, decision (b)-1). The map had `lint`, `test`, `extension`,
  `release-test` and the seeded hooks on LARGE. *Why:* self-hosted pools
  usually have far fewer large runners than small ones (a real consumer pool:
  SMALL ≤ 4–6, LARGE ≤ 2, XLARGE ≤ 1 per org), so those lanes let one PR occupy
  every LARGE slot while a second PR queued and the small slots sat idle, and
  most dev-shell realisation is a binary-cache substitution, which makes the
  lanes light. *Effect:* LARGE and XLARGE have no default lane and are reached
  only through `DEVKIT_CI_LANE_SIZES`. The required classes (§3, (c)-1) shrink
  to the classes the effective lane map uses, the (d)-1 rewrite target and the
  seeded-hook expression read `CI_RUNNER_SMALL`, and the deprecated
  `runner-json` alias follows `runners.small`. This narrows the default only.
  The (b)-1 override mechanism, its syntax, its validation and the variables'
  meaning are unchanged.

**(a) Precedence during the compatibility window (releases N and N+1) when both
the legacy `.vig-os` key and `CI_RUNNER_*` are set.**

1. **Variable wins; the key is reported as overridden.** **Chosen** (owner, 2026-10-26). Setting
   the variable is the migration act, and the end state takes effect at once.
   The key, which is the thing being removed, cannot override it. *Cost:* a
   consumer whose org already sets `CI_RUNNER_*` (Team plan, or repository
   level) moves runners when it adopts release N, if the variable names a
   different label than its key. The per-run legacy-key warning (§3) and the
   `runner-sources` step summary name every overridden class.
2. Rejected: **Legacy key wins** (the owner's emulated order). Release N changes nothing
   for an existing self-hosted consumer. *Cost:* setting a variable has no
   visible effect until the key is deleted, which is the confusing state the
   migration is meant to end. Decision (c) can then never strip the key safely
   during the window, because stripping changes behaviour.
3. Rejected: **Both set is an error.** *Cost:* CI turns red for every such consumer on
   adoption, in exactly the population that already did half the migration.

**(b) Size class per lane, and whether a consumer can override it.**

1. **Defaults as in §5 (every lane SMALL), plus a per-lane override in `.vig-os`:
   `DEVKIT_CI_LANE_SIZES=test=xlarge,lint=large`.** **Chosen** (owner, 2026-10-26;
   the default map was narrowed to all-SMALL on 2026-10-26, see Amendments). It covers the
   lanes `lint`, `test`, `extension` and `release-test`, and the sizes
   `small`, `large` and `xlarge`. Entries are comma-separated `lane=size`,
   whitespace around entries is trimmed, names are case-sensitive lowercase,
   an empty value means no override, and duplicate lane assignments are errors
   at both paths naming `DEVKIT_CI_LANE_SIZES` and the duplicated lane.
   Anything else is an error at the write path
   (`init-workspace.sh`) and in `resolve-toolchain`. How heavy a project's
   lanes are is a property of the **project**, not of the site, so it may live
   in git. Which label serves each size stays in variables. A fork can only
   change sizes, never labels, and foreign runs go hosted anyway. *Cost:* one
   more manifest key (template comment, persistence, two validators), and the
   `runners` object grows lane keys.
2. Rejected: **Fixed classes, no override.** It is the least surface. *Cost:* a project
   whose tests need XLARGE cannot get there without a devkit change. XLARGE
   exists but is unreachable.
3. Rejected: **Per-lane variables** (`CI_RUNNER_TEST`, …). *Cost:* it puts a project
   property into org or repo settings, makes the variables sprawl, and an
   org-level per-lane variable applies to every repo.

**(c) During the compatibility window, does `devkit-upgrade` strip the legacy
key or only warn?** Either way, only the **migrating adoption** (§6) can act:
the first adoption run by a ≥N `devkit-upgrade.yml` from the default branch.
That is N+1's adoption under trunk, and the first adoption after the
consumer's own next release under gitflow, possibly after N+2. The per-run
warnings and the consumer-state tombstone (§3) make the outcome correct
whenever it happens.

1. **Strip it when it is inert, otherwise keep it and explain.** **Chosen** (owner, 2026-10-26). Inert means the variable of every required class (§3:
   exactly the classes the effective lane map uses, which is SMALL alone under
   the default map and gains LARGE or XLARGE only through a
   `DEVKIT_CI_LANE_SIZES` override) is visible to the
   upgrade job, so under (a)-1 the key decides nothing. A class no lane uses is
   not required: the key may still name a pool for it, but no lane reads it. Then removing it
   changes no runner, and the repo reaches the end state at the migrating
   adoption. Otherwise the key stays, and the PR body names
   the variables to set. *Cost:* the upgrade's behaviour depends on variables
   the maintainer may not know are set. It is reported in the PR body. A local
   `install.sh --force` never strips, because it sees no variables. Nothing can
   be stripped before the migrating adoption. A gitflow consumer that does not
   release before N+2 keeps the key until it deletes it by hand, or until a
   later migrating adoption strips it (inert means a warning, not red, §3).
2. Rejected: **Explain only; never strip automatically.** *Cost:* every self-hosted
   consumer has to delete a dead key by hand. It is still safe, because an
   inert key only warns after N+2.
3. Rejected: **Always strip at the migrating adoption**, writing the needed settings into the
   PR body. *Cost:* a consumer that merges before setting the variables
   silently moves to hosted runners. That is the one outcome this design
   forbids, so this option is rejected unless (a) changes.

**(d) Existing copies of the seeded release hooks** (`prepare-release-extension`,
`release-extension`, `publish-release-extension`), which are consumer-owned
and never overwritten.

1. **Reconcile known stock runner values.** **Chosen** (owner, 2026-10-26;
   clarified by the S3 amendment). The upgrade classifies every job's `runs-on`
   value independently of indentation, job-header spelling, comments and line
   endings. The stock set includes every value seeded by a release or dev
   build: the hosted `ubuntu-22.04`, `ubuntu-24.04` and `ubuntu-26.04` labels,
   `${{ fromJSON(inputs.runner-json) }}` and
   `${{ vars.DEVKIT_CI_RESOLVE_RUNNER || 'ubuntu-26.04' }}`. Only with a valid
   `CI_RUNNER_SMALL` in the CI upgrade context does it rewrite a stock value to
   the new SMALL direct expression (§3, the same for every seeded job),
   preserving indentation, comments and line endings. Otherwise it preserves
   the value and reports pending, asking to set SMALL; local installs never
   fold. The current SMALL expression is already reconciled.
   The rewrite target is SMALL, not LARGE, so a reconciled hook agrees with
   "every lane SMALL by default" (§5) and needs only the class every consumer
   already sets. It prints reconcile, pending and drift findings through the
   §6 `ci-runner-migration:` channel; pre-N body builders drop that channel.
   Any other content is left alone and reported as drift, naming file and job.
   A delete-the-legacy-variable hint requires every seeded hook job to be
   reconciled. This is the same precedent as the
   pre-commit reconcile ([#1654](https://github.com/vig-os/devkit/issues/1654)):
   a known-stock block may be folded, nothing else. *Cost:* a second
   reconcile implementation for workflow files, and a consumer-owned file
   changes in an adoption PR.
2. Rejected: **Notice only.** *Cost:* existing copies keep reading
   `DEVKIT_CI_RESOLVE_RUNNER` forever, without the fork predicate. They run
   only on `workflow_call` from dispatch-only trains or on `release`, so there
   is no fork exposure, but the legacy variable can never be deleted.

**(e) `devkit-upgrade.yml`'s runner.**

1. **SMALL with the predicate.** **Chosen** (owner, 2026-10-26). The job that delivers the
   migration should run where the org runs CI. A billing-blocked private org
   otherwise never adopts. Container-mode consumers' runners already have a
   container runtime (§5). *Cost:* the job mints the upgrade App token on a
   self-hosted runner, as the release train already does. Splitting
   secret-bearing jobs from build-only pools is
   [#1876](https://github.com/vig-os/devkit/issues/1876)'s job.
2. Rejected: **Stay hosted, normalised to `ubuntu-26.04`.** *Cost:* the job keeps paying
   hosted minutes on private repos, and fails outright in an org that cannot
   run hosted jobs.

**(f) PRs from forks of a private repo.** Forks of a private repo are private
too, and they are created by people with read access (org members or outside
collaborators). The §2 predicate treats them as foreign, so they run hosted.

1. **Strict: every fork PR is foreign, private or not.** **Chosen** (owner, 2026-10-26). The
   predicate stays as tested, and read access never buys code execution on a
   self-hosted runner. *Cost:* in a private org that cannot run hosted jobs at
   all, PRs from internal forks get **no CI**: the jobs are rejected, the
   checks stay red, and nothing reports green. *Remedy*, documented in
   `MIGRATION.md` (S7): contributors push branches to the base repo (writers
   can), and the org turns off "Allow forking of private repositories" so such
   PRs cannot be opened.
2. Rejected: **Trust forks of private repos:** the predicate gains
   `&& !github.event.repository.private`. *Cost:* anyone with read access to a
   private repo, including outside collaborators, can run code on the
   self-hosted pool by opening a PR from a fork. It also drops the explicit
   check exactly where `pull_request_target` would be most dangerous.

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
- The `runner-json` action output and both legacy knobs disappear in N+2. The
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
about 400 diff lines.

**Merge order for release N:** S1 → S1d → S1b → S2 → S3. S1b implements
decision (b)-1. S4, S5 and S6 are independent of that chain and of each
other. S7 and S7b (docs) follow S1–S6, S8 gates release N, and S9 is release
N+2.

**File overlaps**, which are why the order above is strict. Each later issue
rebases onto the earlier one:

| Overlapping issues | Shared files (and the sections each one owns) |
|---|---|
| S1, S1d, S1b | `resolve-toolchain/action.yml`: S1 owns the algorithm and outputs, S1d the diagnostics, S1b the lane-size parser. `tests/test_ci_runner.py`: separate test functions. `.vig-os`: S1 owns the runner comments, S1b the new key. |
| S1, S2 | `tests/test_ci_runner.py`: S2 widens S1's shape and resolver tests. |
| S1b, S3 | `assets/init-workspace.sh` persistence block: S1b persists the new key, S3 adds the legacy-key migration. `tests/bats/init-workspace.bats`: separate cases. |
| S2, S3 | `devkit-upgrade.yml`: S2 changes only `runs-on`, S3 the install and PR-body steps. |
| S4, S5, S6 | `packages/vig-utils/pyproject.toml` `[project.scripts]`: one line each. |
| S7, S7b | none (split by file). |

**S1 — Runner selection core: `resolve-toolchain` and `ci.yml`.**

- *Scope:*
  - the §3 algorithm for the three classes, with the built-in lane defaults of
    §5 and no override key (that is S1b);
  - the inputs `runner-small`, `runner-large`, `runner-xlarge` and
    `legacy-resolve-runner`. All default to `''`, so a caller that S2 has not
    migrated yet keeps today's behaviour: its `runner-json` alias resolves
    from the legacy key or the default, and it is already fork-safe because
    the action evaluates the predicate;
  - the outputs `runners`, `runner-sources` and the deprecated `runner-json`
    alias;
  - the predicate evaluated in-action, and the malformed-variable `::error::`
    (needed for correctness). All other diagnostics are S1d;
  - the `ci.yml` wiring per §4;
  - the `.vig-os` template comments, replacing the site-specific example label
    with `<label>`.
- *Files:* `assets/workspace/.github/actions/resolve-toolchain/action.yml`,
  `assets/workspace/.github/workflows/ci.yml`, `assets/workspace/.vig-os`,
  `assets/workspace/.github/actionlint.yaml` (comment),
  `tests/test_ci_runner.py` (including scrubbing its site-specific label
  fixture), and the two tests that pin today's `ci.yml` wiring:
  `tests/test_scaffold_drift.py` (`test_scaffold_drift_honors_runner_override`)
  and `tests/test_workflow_ci_extension.py`
  (`test_extension_job_passes_the_resolved_toolchain_context`).
- *Shape-test rule* (`tests/test_ci_runner.py`). A `runs-on` value is one of
  three things:
  1. a **literal hosted label**;
  2. a **direct expression**, which must contain the §2 predicate;
  3. a **`fromJSON(...)` lane**, which may read only
     `needs.<resolver>.outputs.runners` or `needs.<resolver>.outputs.runner-json`
     (the resolver's job runs the action, so the action supplies the fork
     safety) or `inputs.runners` or `inputs.runner-json` of a reusable
     workflow whose every caller passes one of those outputs.

  At S1 the test is parametrized over `ci.yml` and `ci-extension.yml` only.
  `test_resolve_toolchain_runner_is_var_overridable` is split: `ci.yml`
  expects the new direct expression, and the other six resolvers keep
  `RESOLVE_RUNNER_EXPR` until S2. **S2 widens both** to every scaffolded
  workflow. That way S1 lands green while S2's workflows still carry the
  legacy expression.
- *Acceptance:*
  - executed-bash tests for each class and source: fork, variable,
    legacy-key, default;
  - variable wins over the key, per (a);
  - a malformed variable fails with an `::error::` naming it: a comma list,
    a JSON list (`["pool-l"]`), a label with surrounding or inner
    whitespace, and any character outside the label rule of §1;
  - a valid label with `. _ : / -` passes;
  - a whitespace-only variable is treated as unset;
  - no variables and no key gives `ubuntu-26.04` everywhere;
  - the shape test above;
  - a test that no scaffolded workflow declares `workflow_run` or
    `merge_group` (all workflows from S1 on: true today);
  - `ci.yml` lanes reference `runners` per §4;
  - a caller that passes none of the new inputs keeps today's `runner-json`.

**S1d — Runner diagnostics.**

- *Scope:* every §3 diagnostic except the malformed-variable error (including
  the opted-in-class `::warning::`):
  - the full-text legacy-key `::warning::` (the primary migration channel,
    §6);
  - the legacy-variable warning;
  - the whitespace-only warning;
  - the partial-setup `::notice::`;
  - the private no-variables `::notice::` and its step-summary line;
  - the `runner-sources` step-summary table.
- *Files:* `resolve-toolchain/action.yml` (the diagnostics section) and the
  diagnostic tests in `tests/test_ci_runner.py`.
- *Acceptance:*
  - the legacy-key warning names every unset required class, the
    repository-level hint, the delete-the-key step and the `MIGRATION.md`
    anchor, and never the label;
  - the partial-setup notice: the default map with only SMALL set → no
    notice; `DEVKIT_CI_LANE_SIZES=test=large` with SMALL and LARGE set → no
    notice, and with only SMALL set → a notice and a `::warning::` naming
    `CI_RUNNER_LARGE` and the `test` lane, with that lane still on the hosted
    default; a set but unused LARGE is never reported;
  - the opt-in warning also fires with no variable at all and an override in
    `.vig-os` (the after-strip case), never on a foreign run, and not for a
    class sourced from `legacy-key`;
  - the private no-variables notice fires as an annotation, is silenced by
    variables set to `ubuntu-26.04`, and does not fire on a public repo or a
    foreign run;
  - the whitespace-only warning names the offending variable (tested with
    `CI_RUNNER_LARGE` under a lane override).

**S1b — Per-lane size override `DEVKIT_CI_LANE_SIZES`** (decision (b)-1).

- *Scope:*
  - parse `DEVKIT_CI_LANE_SIZES` in `resolve-toolchain`, with an `::error::`
    on an unknown lane or size;
  - the init-workspace write-path guard and persistence;
  - the template comment;
  - each class an override names joining the required classes (LARGE or
    XLARGE), and no other class being required.
- *Files:* `resolve-toolchain/action.yml` (its parser section),
  `assets/init-workspace.sh` (guard and persistence),
  `assets/workspace/.vig-os` (the key and its comment), and the lane-size
  cases in `tests/test_ci_runner.py` and `tests/bats/init-workspace.bats`, and
  `DEVKIT_CI_LANE_SIZES` added to `MANIFEST_KEYS` in
  `tests/test_vig_os_manifest.py`.
- *Acceptance:*
  - an override moves a lane's `runners` entry;
  - invalid values fail at both the write path and resolve;
  - persisted across `--force`;
  - the default map puts every lane on `small`;
  - an override to LARGE or XLARGE with that class unset keeps the lane on
    the hosted default and gives the §3 `::warning::` naming the variable and
    the lane (the diagnostic itself is tested in S1d);
  - a set LARGE or XLARGE that no lane uses gives no notice and is not
    required.

**S2 — Remaining scaffolded workflows.**

- *Scope:* `sync-issues`, `sync-main-to-dev`, `prepare-release`,
  `prepare-hotfix`, `release`, `release-core`, `release-publish`,
  `promote-release`, `abandon-release` and their resolvers per §4; the
  `runner-json` → `runners` input on the managed reusables; the
  `ci-extension.yml` header comment for new scaffolds (`runner-json` is now the
  `extension` lane, not `DEVKIT_CI_RUNNER`-derived); new-scaffold seeded
  hooks on the SMALL direct expression; `devkit-upgrade.yml` per (e).
- *Files:* those workflow files under `assets/workspace/.github/workflows/`,
  and the release-train and hook tests in `tests/test_ci_runner.py`. Not
  disjoint from S1: different test functions in the same file.
- *Acceptance:*
  - each resolver passes all four inputs;
  - each job's class matches §4;
  - managed reusables declare `runners`;
  - the seeded-hook input contract is unchanged;
  - seeded hooks use the new expression;
  - S1's shape test and resolver-expression test are widened to every
    scaffolded workflow, including `assets/smoke-test/.github/workflows/ci-extension.yml`.

**S3 — `devkit-upgrade` migration.**

- *Scope:* §6. It ships in release N and **acts from the migrating adoption**
  (§6):
  - N's `devkit-upgrade.yml` passes `vars.CI_RUNNER_*` into the install step
    and lifts the `ci-runner-migration:` lines into a "CI runner migration"
    PR-body section;
  - `init-workspace.sh` handles the legacy key per (c), keeps it when no
    variables are visible (which is always the case in the adoption of N),
    prints the lines, and adds the private no-variables hint row;
  - the seeded-hook reconcile per (d).
- *Files:* `assets/init-workspace.sh` (the legacy-key migration in the
  persistence block, rebased on S1b's lane-size lines there), `assets/workspace/.github/workflows/devkit-upgrade.yml` (the
  install and PR-body steps; S2 touches only `runs-on`),
  `tests/bats/init-workspace.bats` (migration cases), and the devkit-upgrade
  workflow tests.
- *Acceptance:*
  - bats cases for every row of the §6 table;
  - the strip/keep outcome per (c);
  - with no `CI_RUNNER_*` in the environment (the pre-N workflow), the key is
    always kept;
  - **the "adopt N+1 before releasing N to main" path:** run N+1's
    `init-workspace.sh` with the pre-N workflow's environment (no
    `CI_RUNNER_*`). The key is kept, and the `ci-runner-migration:` lines are
    printed but not lifted, because the pre-N workflow's PR-body step is
    unchanged. A companion S9 test then asserts that at N+2 that repo is green
    with a warning when its variables cover every required class, and red
    with the full text when they do not;
  - the reconcile/drift lines per (d);
  - a workflow test that the install step's `env` carries all three
    variables and that the PR-body step lifts the lines.

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
  `packages/vig-utils/pyproject.toml` (the `check-hardcoded-endpoints`
  console-script line), `nix/hooks.nix`
  (hook entry), `.pre-commit-config.yaml` (devkit's own), and tests.
- *Acceptance:*
  - each rule fires on a positive fixture;
  - references, RFC 2606 hosts and the pragma pass;
  - devkit's own tree passes;
  - the hook is present and enabled on the consumer surface.

**S6 — Site leak-check hook point.**

- *Scope:* §10 leak check.
- *Files:* `packages/vig-utils/src/vig_utils/site_leak_check.py`,
  `packages/vig-utils/pyproject.toml` (the `site-leak-check` console-script
  line), `nix/hooks.nix` (a separate entry from S5), and tests.
- *Acceptance:*
  - no pattern file: exit 0 and silent;
  - the `DEVKIT_LEAK_PATTERNS` and `.site/` lookup order;
  - a staged match fails, with redacted output;
  - a tracked or in-tree pattern file is an error;
  - `--all-files` mode scans the tree.

**S7 — `MIGRATION.md` self-hosted rewrite.**

- *Scope:*
  - rewrite `docs/MIGRATION.md` "Run CI on self-hosted runners" around the
    variables: repository level on GitHub Free, fork safety and decision (f)'s
    remedy, size classes and the lane override, and the deprecation timeline
    including the migrating-adoption and consumer-state tombstone (§6);
  - a "CI never starts on a private repo" entry (§3 notice limit);
  - the whitespace-only `CI_RUNNER_SMALL` symptom (§1);
  - replace the site-specific example label and the `gh variable set` value
    with `<label>`;
  - update the manifest key table.
- *Files:* `docs/MIGRATION.md` only.
- *Acceptance:*
  - docs lint passes;
  - every §3 diagnostic's `MIGRATION.md` anchor resolves;
  - the section contains no site label.

**S7b — Remaining docs and scrub.**

- *Scope:*
  - `docs/DOWNSTREAM_RELEASE.md` (both copies): `runner-json` → lanes;
  - `docs/WORKFLOW_SECURITY.md`: the predicate and the trigger rules;
  - a new `docs/GOING_PUBLIC.md` (§10 checklist);
  - `.site/` and site-init docs in `docs/SOLO_ADOPTION.md`;
  - the CHANGELOG `### Deprecated` entry for both legacy knobs;
  - scrub the site-specific label and site names from the
    `tests/bats/init-workspace.bats` fixtures and the
    `tests/test_setup_toolchain_env.py` comments and docstrings. The `.vig-os`
    and `tests/test_ci_runner.py` fixture scrubs land in S1, which owns those
    files.
- *Files:* the docs named above, `CHANGELOG.md`, the bats fixture strings and
  `tests/test_setup_toolchain_env.py`.
- *Acceptance:*
  - the scrub target is the **site-specific runner label** used as today's
    example in the `MIGRATION.md` self-hosted section, plus the site, org and
    repo names in the comments next to it in the files listed above. Other org
    and repo names elsewhere are out of scope;
  - a `git grep` for that label returns nothing outside `docs/issues/`,
    `docs/pull-requests/` and the **released** sections of `CHANGELOG.md` and
    `assets/workspace/.devcontainer/CHANGELOG.md`. Released entries are never
    edited, per the changelog rules;
  - the names next to the label are checked by running S6's `site-leak-check`
    over the tree with the owner's site pattern file, so the names never
    appear in devkit;
  - docs lint passes.

**S8 — Release N gate.**

- *Scope:* verify S1–S7b on the consumer matrix and in one self-hosted consumer
  before cutting N, including a **gitflow consumer whose `dev` is ahead of
  `main`**. Its N adoption runs the pre-N workflow from `main`; the matrix
  checks that the key is kept and that the per-run warning carries the full
  migration text on the `dev` PR.
- *Files:* `scripts/consumer-matrix/render-cell.sh` and
  `tests/bats/consumer-matrix.bats`. The self-hosted cell seeds variables
  instead of the key.
- *Acceptance:*
  - the matrix is green with the key only (the warning path) and with
    variables only;
  - in the gitflow cell, the adoption PR's CI log has the full-text warning,
    and the pre-N PR body has no migration section, which is expected.

**S9 — Removal (release N+2).**

- *Scope:* §6 N+2: delete the legacy arms, keep the tombstones, remove the
  `runner-json` alias, and drop the template key. The direct expression of the
  `resolve-toolchain` jobs and resolvers is unchanged (§3: the legacy-variable term carries the tombstone).
- *Files:* `resolve-toolchain`, the scaffolded workflows, `.vig-os`,
  `init-workspace.sh`, tests, `MIGRATION.md`, and CHANGELOG `### Removed`.
- *Acceptance:*
  - consumer-state tombstone: a non-inert key → `::error::` with the full
    text; an inert key (every required variable set) → `::warning::` and
    green; a foreign run → `::warning::`;
  - the variable tombstone error and warning;
  - the companion of S3's "adopt N+1 before releasing N to main" test;
  - `DEVKIT_CI_RESOLVE_RUNNER` appears in `runs-on` only as the term before
    the hosted default in the `resolve-toolchain` jobs and resolvers, never
    in a seeded hook.
- Blocked by release N+1 shipping.
