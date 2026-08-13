# Vendored guardrails gates

Semantic code gates, vendored from [`gerchowl/guardrails`](https://github.com/gerchowl/guardrails)
@ `61538e2` under Apache-2.0 (see `LICENSE`) — the same licence and holder as
devkit, so these copies need no separate attribution block.

**devkit is the source of truth for these files.** The upstream repo is being
retired (vig-os/devkit#1488): an org toolchain whose semantic enforcement lives
in a personal repository is a bus-factor question, and two separately-versioned
copies of the same 3,000 lines drift. Edit them here.

## Layout

| path | what |
|---|---|
| `gates/` | the 15 gates, each a standalone POSIX shell script exiting non-zero on a finding |
| `tools/` | `guardrails` (the CLI), `trace` (the per-hook JSONL wrapper every entry wraps), `trace-report` |
| `gates/test-*.sh` | upstream's own fires-on-bad / quiet-on-good fixtures. They live BESIDE the gates because they resolve siblings via `dirname "$0"` — vendoring keeps upstream's layout so the scripts run unmodified |

## Why shell

Deliberate, and re-decided rather than inherited (vig-os/devkit#1488). The
scripts are shellcheck-clean at `-S warning` (1 warning across all 15), every
gate has a fixture, and the absent `set -e` is correct rather than sloppy —
these gates `grep`, and grep exits 1 on no-match, so `-e` would abort on the
*quiet* path.

New gates should be written in Python (`vig-utils`), so the shell surface stops
growing and the test/lint story converges. Port an existing gate only where
shell is genuinely the wrong tool — the stateful ones (`perf-budget`,
`perf-record`) and the nudge ledger, not the scanners.

## Deliberately not vendored

`templates/` — upstream's starter template for a repo adopting guardrails
(a `flake.nix`, `ci.yml`, `deny.toml`, and two config stubs). devkit IS the
scaffolding system, so carrying a second, unreferenced one would be dead
surface that drifts from `assets/workspace/`. Nothing in `gates/` or `tools/`
reads it. If a consumer needs those stubs, they belong in the scaffold proper.

`crates/` — `guardrails-tunables` is Rust-only and belongs with the Rust
language pack, not an org-wide gate module; `guardrails-trace` (the crate) is
a tracing-subscriber wrapper for consumer *applications*, unrelated to the
`guardrails-trace` hook wrapper in `tools/`, which is shell. Both are tracked
on vig-os/devkit#1488.
