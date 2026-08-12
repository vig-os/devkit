---
type: issue
state: open
created: 2026-08-12T01:05:44Z
updated: 2026-08-12T01:05:44Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1430
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T04:13:03.978Z
---

# [Issue 1430]: [A fresh clone does not enforce devkit's own commit rules until scripts/init.sh runs](https://github.com/vig-os/devkit/issues/1430)

## What happened

Building the Rust language pack (#1400 / #1429) I did a plain `git clone` of devkit and started committing. My first two commits **violated two of devkit's own mandatory rules and were accepted**:

- branch `feat/rust-language-pack` — the taxonomy is `<type>/<issue>-<summary>` and `feat` is not a valid type (`feature` is)
- `Refs #1400` — the standard requires the trailer `Refs: #1400`, colon included

Neither was caught. They surfaced only on my *third* commit, by which point something in the session had run `scripts/init.sh` and the hooks became live. Then a push was additionally rejected by the signed-commits ruleset, which is the only one of the three that is enforced server-side.

## Root cause

`.githooks/` is tracked, so a fresh clone *has* the hook shims on disk. But git does not use them until `core.hooksPath` points there, and the only thing that sets it is `scripts/init.sh:203`:

```sh
if git config core.hooksPath .githooks && chmod +x .githooks/* 2>/dev/null; then
```

`core.hooksPath` is **local repo config**, so it is not cloned and cannot be. Between `git clone` and `scripts/init.sh`, devkit's entire commit-side gate stack is present, believed active, and inert. Nothing says so.

## Why this matters more than it looks

This is the same failure class the Rust pack exists to prevent, occurring in the tool that defines the standard. From the first consumer's history (`gerchowl/filesender`), **five separate things** were configured, believed active, and never executed — a `deny.toml` outside the build fileset banning nothing, a `clippy.toml` the sandboxed clippy never read, `.pre-commit-config.yaml` entries at the wrong indent, hook commands absent from `PATH`, and a `just precommit` recipe that ran only the pre-commit stage so the whole gate suite never ran in CI. Every one was invisible to inspection and obvious on execution.

Add this one: **the hooks are not installed until someone runs the installer, and nothing tells you.**

The population that hits it is not the edge case. Anyone who clones outside the devcontainer, any CI job that does not call `init.sh`, and — increasingly — any coding agent, which reaches for `git clone && git commit` and has no reason to know an installer exists.

Worth noting the failure is silent in the *dangerous* direction: an un-hooked clone lets bad commits through, rather than blocking good ones. There is no feedback signal at all.

## Options

Not a recommendation — the tradeoffs are devkit's to weigh:

1. **A tracked `.githooks/`-independent trip-wire.** Hard, given `core.hooksPath` is exactly the thing not yet set.
2. **Server-side rulesets for what is currently client-only.** Branch naming and the `Refs:` trailer are both mechanically checkable in a required status check. Signed commits already works this way, and it is the only one of the three that actually held. Strongest option — it does not depend on local state at all.
3. **Make `init.sh` unmissable**: a `CONTRIBUTING.md` first line, and a `just` default recipe that fails loudly when `core.hooksPath` is unset.
4. **A CI job asserting the config**, so an un-initialised clone fails the PR rather than the commit.

(2) and (4) are the ones that survive a contributor who never reads anything, which is the case that produced this issue.

## Acceptance

- [ ] Branch-name and `Refs:` conformance enforced somewhere that does not depend on local git config
- [ ] An un-initialised clone gets a loud signal before its first commit lands, not after
- [ ] `docs/` states plainly that `.githooks/` being tracked does **not** mean the hooks run

Refs: #1400, #1429

