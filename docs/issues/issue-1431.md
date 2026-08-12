---
type: issue
state: closed
created: 2026-08-12T05:14:30Z
updated: 2026-08-12T06:26:05Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1431
comments: 1
labels: feature, priority:medium, area:workspace, effort:medium, semver:minor
assignees: none
milestone: 1.8.0
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:43.291Z
---

# [Issue 1431]: [[FEATURE] feat(workspace): scaffold-time commit-types knob (DEVKIT_COMMIT_TYPES) for validate-commit-msg + validate-commit-range](https://github.com/vig-os/devkit/issues/1431)

### Description

A `.vig-os` manifest key `DEVKIT_COMMIT_TYPES` that renders a per-consumer approved-commit-types list into **both** enforcement points at scaffold time — the `validate-commit-msg` hook's `--types` arg in the scaffolded `.pre-commit-config.yaml` and CI's `validate-commit-range` call — following the `DEVKIT_REFS_POLICY` blueprint (#1282 / PR #1292) exactly.

### Problem Statement

exo-pet/vault#54: the ADR-0002 record-change flow prescribes a `record` commit type that the devkit-managed gates reject with the default type list. A repo-side `--types` override in `ci.yml` would trip the scaffold-drift gate, and editing the preserved hook YAML causes permanent drift + hook/CI desync (the same two costs that motivated #1282). Per-consumer flexibility is the chosen direction (option B in the vault issue) over adding `record` to the org-wide defaults.

### Proposed Solution

- New `.vig-os` key `DEVKIT_COMMIT_TYPES`: comma-separated **full replacement** of the approved types; empty (default) resolves to today's 11 (`feat,fix,docs,chore,refactor,perf,test,ci,build,revert,style`) — byte-identical default scaffold.
- `init-workspace.sh`: read + strict charset guard (`[a-z][a-z0-9]*` per entry — the value is spliced into a sed replacement and YAML, so the allowlist is load-bearing, like the DEVKIT_SYNC_TARGET guard); `render_commit_types()` as an anchored sed on the `--types` arg line (mirrors `render_refs_policy`); conditional write-back across `--force` upgrades; a **notice** (not abort) when `chore`/`build` are dropped (renovate + devkit-upgrade bot commits use them).
- `resolve-toolchain`: parse the key, emit a `commit-types` output (default = full list); `ci.yml` commit-checks passes `--types` via env (the #1279 env-routing pattern).
- **Composition fix**: the `optional` refs-policy mapping hardcodes the full default list in BOTH renderers (`render_refs_policy` + resolve-toolchain) — it must mirror the resolved custom list instead.
- Template `.vig-os` ships the documented bare key.
- Docs: `docs/MIGRATION.md` manifest table + knob section; `docs/COMMIT_MESSAGE_STANDARD.md` note that consumers may extend the list.

Spike evidence (2026-08-11, dev @4822b706): `validate-commit-msg` **and** `validate-commit-range` already accept `--types` — no vig-utils change needed. With `--types …,record` a `record(registry): …` message passes and still requires `Refs:` under the default `chore-optional` policy; CI's call just never passes the flag today. The anchored sed was proven against the template YAML.

#### Acceptance criteria

- [ ] Default (absent/empty key) produces a byte-identical scaffold and identical CI behavior
- [ ] Hook and `validate-commit-range` agree in all modes (single source of truth: one key, two renderers in lockstep)
- [ ] `DEVKIT_REFS_POLICY=optional` composes with a custom types list (refs-optional list mirrors it)
- [ ] Invalid charset refused loudly at scaffold time; round-trip across `--force` proven in bats
- [ ] test_ci_runner.py mapping/env-routing/flag coverage mirroring the #1282 tests

### Alternatives Considered

- **Add `record` to the org-wide defaults** (option A in exo-pet/vault#54) — one consumer's ADR vocabulary leaks into every repo; rejected in favor of per-consumer flexibility.
- **Amend ADR-0002 to reuse `chore(registry)`** — loses the distinct audit-trail marker that was the ADR's point.

### Additional Context

exo-pet/vault#54 (origin), #1282 (`DEVKIT_REFS_POLICY` — the blueprint), #1074 (hook/CI desync precedent), #885 (manifest as the config surface). Note: direnv consumers on flake-generated hooks have **no local commit-msg-stage hooks at all** (separate gap, tracked in its own issue), so for them this knob is realized entirely through CI until that gap is closed.

### Impact

Backward compatible (semver:minor labeled; 1.7.1 train inclusion per the #1254 precedent). Benefits any consumer with a domain-specific commit vocabulary.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 06:26 AM_

Merged to dev via #1436 (dev-targeted PRs do not auto-close). Ships with 1.7.1.

