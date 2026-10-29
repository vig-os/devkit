---
type: issue
state: open
created: 2026-10-29T02:56:35Z
updated: 2026-10-29T03:18:58Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1959
comments: 1
labels: feature, area:testing
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-29T08:18:28.380Z
---

# [Issue 1959]: [test: strict GitHub-expression evaluator for managed-workflow runner wiring](https://github.com/vig-os/devkit/issues/1959)

Prerequisite for #1935 (S8 of #1908), split out at the implementer's request to keep PR #1958 reviewable.

**Problem.** The consumer-matrix runner cells run only the resolve action's `run:` body with hand-written env. The real wiring in the managed workflows is never exercised: the mapping from `vars.CI_RUNNER_*` to the resolve step's `with:` inputs, and each job's `runs-on` lane expression. A review showed that `runner-large: ${{ vars.CI_RUNNER_SMALL }}` and a test job moved to `fromJSON(...).large` both stay green.

**Scope.** A small, strict evaluator for exactly the GitHub Actions expression subset the managed workflows use in `runs-on` and in resolve-step `with:` values:
- context lookups: `vars.*`, `github.event.pull_request.head.repo.fork` (and the other `github.*` paths those expressions use), `needs.<job>.outputs.<x>`, `inputs.*`;
- `fromJSON(...)` and property access;
- `&&`, `||`, `!`, `==`, `!=`, string/number/boolean/null literals, parentheses;
- GitHub's truthiness and `||`/`&&` value semantics (they return operands, not booleans), and `${{ }}` interpolation inside a string.

Any construct outside the subset **raises** with the expression and position. It never evaluates to a default.

**Acceptance.**
- A unit test for each operator and for the truthiness/value semantics, compared against GitHub's documented behaviour (cite the docs in the test module). Include unsupported-construct-raises cases.
- A test that parses every `runs-on` and resolve-step `with:` expression in the shipped managed workflows (`assets/workspace/.github/workflows/*.yml`) and evaluates each without error for a representative context. A new unsupported construct added to a workflow then fails CI instead of silently escaping the gate.
- Location: wherever the repo keeps test helpers that bats and pytest can both use (follow existing patterns), documented in its module docstring.
- No consumer-facing behaviour change; no CHANGELOG entry unless the repo rules require one for test tooling.

Refs: #1935
---

# [Comment #1]() by [gerchowl]()

_Posted on October 29, 2026 at 03:18 AM_

Scope clarification (architect): the subset is *exactly what the managed workflows use*. `assets/workspace/.github/workflows/ci.yml:742` passes `toJSON(fromJSON(needs.resolve-toolchain.outputs.runners).extension)` to a reusable job, so `toJSON` is in scope, with GitHub's semantics (pretty-printed JSON, documented in the expressions reference; cite it and test the exact output format). Every other function still raises.

