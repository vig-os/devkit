---
type: issue
state: closed
created: 2026-08-31T08:53:38Z
updated: 2026-08-31T09:39:52Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1583
comments: 1
labels: feature
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-01T07:38:48.776Z
---

# [Issue 1583]: [[FEATURE] vigos.sesh: per-session layout profiles](https://github.com/vig-os/devkit/issues/1583)

## Description

`vigos.sesh` applies one window set to every project. `layout.windows` parameterizes *which* windows a session gets, but the choice is global — every seed in `sessions` opens identically.

Add an opt-in per-session layout: named profiles on the module, and a `layout` field on a session entry selecting one. Absent ⇒ current behaviour, unchanged.

## Problem Statement

Projects genuinely differ in what a session should open:

- A repo with no pull-request workflow (notes, vaults, prose, a scratch repo) still gets a `gh-dash` window idling on a permanently empty dashboard — real background CPU for a pane nobody opens, which is the cost `vigos.ghdash`'s tuning defaults already work to avoid.
- A docs repo has no use for a git TUI window; a polyglot service repo might want an extra one.

Today the only escape is to disable the module and hand-roll `sesh.toml`, which throws away the whole layout mechanism to change one window.

## Proposed Solution

Three small additions, all backward compatible:

1. **`vigos.sesh.layout.profiles`** — attrset of `<name> -> [ window ]`, using the existing `windowModule`. Empty by default.
2. **`sessions[].layout`** — `nullOr str`, naming a profile. `null` (default) ⇒ the existing `layout.windows`.
3. **Eval-time guard** — a `sessions[].layout` naming an unknown profile must fail at eval with a message listing the valid names, not produce a session that dies at connect time.

Internally the default set becomes just another profile (`profiles // { default = layout.windows; }`), so there is one code path.

**Delivery uses sesh's own config, not a new mechanism.** `SessionConfig` embeds `DefaultSessionConfig` in sesh's `model/config.go`, so a `[[session]]` block already accepts `startup_command`; `startup.Exec` resolves per-session → wildcard → default, first match wins. So a session with a profile emits `startup_command = "sesh-layout <profile>"` and everything else stays silent and inherits `[default_session]`.

`sesh-layout` grows an optional profile argument and dispatches over the generated profiles, defaulting to `default`. One binary, one PATH entry — which matters because consumers probe for `sesh-layout` by name to detect a provisioned host.

## Alternatives Considered

- **Inline `sessions[].windows`** instead of named profiles — more direct, but duplicates a window list across every session sharing a layout, and needs synthesized profile names. Named profiles are DRY and let one name be reused.
- **sesh's native `[[window]]` + per-session `windows`** — sesh can create windows itself. Rejected: it sends startup keys to the session rather than a captured `#{window_id}` (our generated script captures ids precisely because window names collide or auto-rename), it errors if a name has no `[[window]]` block, and it cannot run a command *in* window 1 with a shell fallback, which is how the first entry works today. Use sesh for *selection*, keep the generated script for *construction*.
- **`[[wildcard]]` patterns** — attractive for "every repo under this directory", but `configWildcardStrategy` requires the connect name to resolve to a directory, so it never fires for curated seeds connected by label. Not a substitute for per-session config.
- **Repo-local config files** — rejected on the same grounds as elsewhere in the kit: a personal-workflow file should not have to land in a shared or other-org repo.

## Additional Context

Prototyped and field-proven in a consumer config before upstreaming, which is how `vigos.sesh` itself was built ("parameterized port of the maintainer's proven setup"). The prototype ships two profiles — the standard set and one dropping the PR window — and validation covered: generated bash passes shellcheck, each profile yields exactly its window set focused on the first entry, re-running inside a live session leaves windows untouched and exits 0 (idempotency guard), an unknown profile exits 1 on stderr, and the generated `sesh.toml` parses under sesh 2.26.2 with every seed still listed.

Design discussion: [c-vigo/vigo-nixos#9](https://github.com/c-vigo/vigo-nixos/issues/9).

## Impact

- **Backward compatible.** No new required option; `sessions` entries and `layout.windows` behave exactly as now when `layout` is unset and `profiles` is empty. Existing consumers see no diff.
- Benefits anyone whose projects are not all the same shape — the multi-repo case the module already targets with `sessions`.
- Test surface: `tests/test_flake_checks.py` already asserts the sesh contract in the ci profiles; this adds profile generation, inheritance and the unknown-profile guard.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 31, 2026 at 09:39 AM_

Done — merged to `dev` in [#1584](https://github.com/vig-os/devkit/pull/1584) (`98851843`), all 14 CI checks green.

**What shipped**, as proposed:

- `vigos.sesh.layout.profiles` — named window sets, reusing the existing `windowModule`
- `sessions[].layout` — `nullOr str` selecting one; null inherits
- `default` is `layout.windows` and wins over a same-named profile key, so the default set keeps **one** home rather than two that can disagree
- eval-time guard naming the session, the offending profile and the valid set

Delivery is sesh's own config as designed: a session with a profile emits `startup_command = "sesh-layout <profile>"`, which `startup.Exec` resolves ahead of `[default_session]`, so a session naming none stays bare and inherits. `sesh-layout` takes the profile as an argument and remains a single binary — consumers probe for it by name to detect a provisioned host.

**One implementation decision worth recording**, since it isn't in the issue above: the guard **throws while rendering** rather than using `assertions`. Assertions only fire when the activation package is evaluated, so a consumer — or a test — evaluating just `home.file.".config/sesh/sesh.toml".text` would sail straight past them and get a `sesh.toml` whose sessions all die at `sesh connect`, far from the definition at fault.

**Verification** went past the unit tests: the generated script was built from a synthetic config and exercised in scratch tmux sessions — `default` → `edit git shell claude` (unchanged), `docs` → `edit shell`, re-running inside a live session left the window set untouched and exited 0, an unknown profile printed to stderr and exited 1. Suite: 935 passed, 1 skipped. `prek run --all-files` green with a clean tree afterwards. TDD order is visible in history — `349f0581` RED, `5e4714ad` GREEN.

Backward compatible: with `profiles` empty and no session setting `layout`, the generated `sesh.toml` and layout script are unchanged, so existing consumers see no diff.

Unreleased so far — it sits on `dev` awaiting the next release train.

