---
type: issue
state: open
created: 2026-10-29T04:14:58Z
updated: 2026-10-29T04:16:17Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1963
comments: 1
labels: feature, area:testing
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-29T08:18:27.280Z
---

# [Issue 1963]: [test: workflow-step replay helper (evaluated with/env, isolated steps, GITHUB_OUTPUT/ENV)](https://github.com/vig-os/devkit/issues/1963)

Second prerequisite for #1935 (S8 of #1908). It's split out at the implementer's request to keep PR #1958 reviewable, and it builds on the merged expression evaluator (#1959, `tests/github_expression.py`).

**Problem.** The S8 consumer-matrix cells replay real workflow steps: the pre-N `devkit-upgrade.yml` from tag 1.18.0, and the managed workflows' resolve step and `runs-on`. Today the harness types step `env:` values by hand, and it passes values between steps through a shared shell. So a mutation such as `BASE: main` or `HOOK_DRIFT: x` in the workflow stays green, and the gate checks only its own inputs.

**Scope.** A small, tested helper that, given a workflow file, a job id and a context (`github`, `inputs`, `vars`, `needs`, an event payload):
- extracts the job's steps in order;
- for each step, evaluates `if:` (with the evaluator; unsupported constructs raise), `env:` (job- and step-level, step overriding job), and `with:` for steps that are local composite actions, if the S8 cells need that;
- runs `run:` steps each in its own `bash -eo pipefail` process (or the step's `shell:`), with only the evaluated env plus a documented minimal base env;
- provides `GITHUB_OUTPUT`, `GITHUB_ENV` and `GITHUB_STEP_SUMMARY` files, and parses them after each step, including GitHub's multiline `name<<DELIM` syntax. `steps.<id>.outputs.*` becomes available to later steps, and `GITHUB_ENV` applies to later steps only;
- fails loudly on any step kind it can't replay (`uses:` other than an explicitly allow-listed local action, unsupported `shell:`, and so on). It never skips silently;
- offers a bats-friendly CLI and a Python API.

**Acceptance.**
- Unit tests:
  - step isolation (a shell variable set in step 1 is not visible in step 2);
  - outputs and env propagation, including multiline values;
  - `if:` evaluation;
  - job/step env precedence;
  - the unsupported-step error;
  - a fixture workflow mutation (`BASE: main`) changing the replayed result.
- A test that loads the real tag-1.18.0 `devkit-upgrade.yml` (`git show 1.18.0:assets/workspace/.github/workflows/devkit-upgrade.yml`) and resolves the env of its upgrade and PR-body steps without error. If the tag is missing it fails clearly; it never skips.
- Documented in the module docstring: what it replays, what it refuses, and how it differs from a real runner.

Refs: #1935
---

# [Comment #1]() by [gerchowl]()

_Posted on October 29, 2026 at 04:16 AM_

Scope clarification (architect): the evaluator's supported context roots follow the same rule as #1959, exactly what the replayed workflows use. The pre-N `devkit-upgrade.yml` uses `steps.<id>.outputs.*` (and step `env:` may reference `env.*`). So this PR adds `steps` and `env` as context roots to `tests/github_expression.py`, with tests. The roots are case-insensitive like the others, and a missing property gives null per GitHub. No other evaluator changes.

