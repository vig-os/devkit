---
type: issue
state: open
created: 2026-08-31T09:59:08Z
updated: 2026-08-31T09:59:08Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1586
comments: 0
labels: feature
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-01T07:38:48.086Z
---

# [Issue 1586]: [[FEATURE] vigos.ghdash: per-project scope and section profiles](https://github.com/vig-os/devkit/issues/1586)

## Description

`vigos.ghdash` renders one dashboard for one fixed scope. Give it two things a multi-project setup needs: **the scope follows the project you are in**, and **the section set can differ per project**.

Both default to today's behaviour.

## Problem Statement

`repoFilters` is global. `vigos.sesh` exists precisely because a person works across many projects, and the module ships a dashboard window in the standard layout — so in practice every session opens a dashboard scoped to *someone else's* project. Widening `repoFilters` to cover them all is the escape, and it is the expensive one: an unscoped dashboard is exactly the idle-CPU problem the module's tuning defaults were written to avoid.

Section sets are global too, and projects genuinely differ. A repo shared with a team wants `Needs my review` and team queries; a solo repo is well served by `Involved / Open / Recently closed`. Sections are the one key gh-dash *replaces* rather than merges, so there is no way to vary them without replacing the whole config.

## Proposed Solution

**1. Scope follows the project.** Ship a small wrapper (`gh-dash-repo`) that resolves the repo from `origin` at the launch directory, substitutes it into the rendered config, and `exec`s `gh-dash --config` on the result. Outside a GitHub repo it falls back to `repoFilters` (and to `involves:@me` when that is empty), so it is always valid.

This is deliberately *derived*, not declared: the discriminator is the directory you launched in, so nothing has to be declared per project and no file lands in the project repo — which matters for shared and other-org repos, where a personal workflow file is unwelcome on both convention and confidentiality grounds.

**2. `vigos.ghdash.profiles`** — named section sets, with the wrapper taking a profile name as its argument (`gh-dash-repo shared`). Absent ⇒ the current three generated sections.

**3. It composes with [#1583](https://github.com/vig-os/devkit/issues/1583).** A `vigos.sesh` layout profile can point its dashboard window at `gh-dash-repo <profile>`, so *selection* rides on the sesh entry that already identifies the project — the same declaration site the layout work uses, rather than a second per-project mechanism.

## Alternatives Considered

- **Repo-local `.gh-dash.yml`** — gh-dash discovers and merges it natively, so it is the cheapest option and was the first considered. Rejected: it puts a personal-workflow file in every project repo, unacceptable for shared and other-org repos.
- **Central per-project config files + `--config`** — works, but needs a per-project file tree kept in sync with the project list, when `origin` already answers "which repo is this".
- **Widening `repoFilters`** — the status quo escape, and it reintroduces the idle-CPU cost the defaults exist to prevent.
- **Per-session `GH_DASH_CONFIG`** — takes precedence over repo-local discovery and would suppress it; `--config` composes better.

## Additional Context

The wrapper half is field-proven in a consumer config (running since the dashboard was first scoped per session) and is what closed the equivalent downstream issue. The **profile argument is new** — it has not been built anywhere yet, so unlike #1583 and #1585 this one has no prototype behind it, and the argument-handling and fallback paths deserve real scrutiny rather than being assumed from the existing wrapper.

Two things worth deciding during design:

- gh-dash has no template variable for "the current repo", which is why substitution happens at launch rather than in the config. The rendered config wants a deterministic path (a runtime dir keyed by the repo slug works and needs no cleanup, since it is overwritten each launch).
- Shipping a `gh-dash-repo` binary will **collide** with a downstream config that already ships one, exactly as `sesh-picker` does for [#1585](https://github.com/vig-os/devkit/issues/1585). That makes the consumer migration atomic rather than incremental, so it is worth landing in the same release as #1585 if possible.

## Impact

- **Backward compatible.** With `profiles` empty and the wrapper unused, the generated gh-dash settings are unchanged; `repoFilters` keeps working as the fallback scope. Existing consumers see no diff.
- Makes the dashboard window in the standard `vigos.sesh` layout actually useful across projects, rather than correct for one of them.
- Preserves the tuning defaults: a per-repo scope is *cheaper* than the widened filter it replaces.
- Test surface: `tests/test_flake_checks.py` already asserts the ghdash contract; this adds profile rendering, the empty-profiles no-op guarantee, and the wrapper's fallback behaviour outside a GitHub repo.

