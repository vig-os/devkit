#!/usr/bin/env bash
# guardrails — what is this, and how do I use it. A terminal answer to "a teammate
# added guardrails to our repo; now what?". Print with `guardrails` or `guardrails info`.
set -uo pipefail
case "${1:-info}" in
  info | "" | -h | --help | help)
    if [ "${2:-}" = "--perf" ]; then shift 2; exec guardrails-trace-report perf "$@"; fi ;;
  last) shift; exec guardrails-trace-report last "$@" ;;
  stale) shift; exec guardrails-stale "$@" ;;
  freshness) shift; exec guardrails-freshness "$@" ;;
  diffpack) shift; exec guardrails-diffpack "$@" ;;
  *) echo "guardrails: unknown command '$1' (try: guardrails info)" >&2 ;;
esac
cat <<'EOF'
guardrails — shareable code-quality / governance for this repo.
Gates run on every commit (via prek); deep checks (cargo-deny, perf) run in CI.

GATES — block a commit unless escaped:
  protect-trunk       HEAD is a protected branch (main/master) — trunk advances by merge/PR only;
                      the pre-push twin refuses pushes advancing a protected REMOTE ref
                      (GUARDRAILS_PROTECTED_BRANCHES to change/disable · GUARDRAILS_ALLOW_TRUNK=1
                      for an intentional hotfix · CI auto-allowed). Solo/trunk-flow upgrade:
                      GUARDRAILS_TRUNK_MERGE_GATE=1 lets the push-side gate EARN a trunk push —
                      allowed iff GUARDRAILS_TRUNK_MERGE_CMD (default `nix flake check`) is green
  no-fake-impl        todo!()/unimplemented!()/FIXME/placeholder-impl — stubs shipped as "done"
  no-debug-leftovers  dbg!/print!/println!/eprint!/eprintln!/console.log outside main/bin/tests
  no-commented-code   commented-out code graveyards
  no-hardcoded        magic values that should be tunables (src/ only). Adopting on a legacy
                      tree? Ratchet mode: `guardrails-no-hardcoded --record-baseline` commits a
                      per-file debt snapshot — growth hard-fails, burn-down nudges a re-record,
                      at-baseline stays silent (no big-bang triage needed)
  no-conflict-markers committed <<<<<<</=======/>>>>>>> merge-marker lines (no escape — never legitimate)
  no-raw-trace-fields raw ?/% Debug/Display field formatters in tracing! macros — shape the field
                      in your schema surface (PII/secrets leak into logs by reflex otherwise)
  derived-docs        regions marked `<!-- guardrails:derived cmd="…" -->` must match `cmd`'s output
                      (re-run with --fix to regenerate; commands run with repo-hook trust)
  + gitleaks · rustfmt · clippy -D warnings · cargo-deny

NUDGES — warn (exit 0); promote per-repo with the gate's *_ENFORCE knob:
  ci-shim             a CI workflow runs logic but no `nix flake check` (GUARDRAILS_CI_SHIM_ENFORCE)
  duplication         a ≥6-line block cloned across ≥2 sites — reinvention vs reuse; extract a
                      helper (GUARDRAILS_DUP_ENFORCE / _MIN_LINES / _EXTS / _ALLOW)
CI-deep (not pre-commit) — run after `cargo criterion`:
  perf-budget             gate criterion regressions over a checked-in perf-budgets.toml
  perf-record             append per-bench medians to perf-history.csv — the PR diff is the report,
                          git history is the trend (no external service)
  numerical-obligation    ratchet measured numerical contracts (parity errors, HARD counts, coverage %,
                          binary size) against a checked-in baseline JSON. Distinct from perf-budget:
                          the baseline MOVES on improvement (--update writes back in the improvement
                          direction only — refuses to widen slack). Schema in numerical-obligation.toml.

ESCAPE / BYPASS:
  one line    append  // guardrails-ok
  one commit  git commit --no-verify   (sparingly — the point is to not need it)

CONFIG KNOBS (in your repo root):
  .pre-commit-config.yaml  which gates run + their entries
  GUARDRAILS_OUTPUT_GLOBS  no-debug-leftovers: colon-sep path globs for legit CLI output surfaces,
                           e.g.  entry: env GUARDRAILS_OUTPUT_GLOBS=*/cli/*:scripts/* guardrails-no-debug-leftovers
  GUARDRAILS_TRACE_ALLOW_GLOBS  no-raw-trace-fields: colon-sep path globs for the schema/redaction
                           surface where raw ?/% field formatting is defined, e.g. src/trace_schema.rs
  guardrails-allow.txt     no-hardcoded: blessed path prefixes to skip
  guardrails-baseline.txt  no-hardcoded ratchet: committed per-file count snapshot (or point
                           GUARDRAILS_HARDCODED_BASELINE elsewhere); --record-baseline refuses
                           to loosen — the ratchet only tightens
  GUARDRAILS_ENV_PREFIXES  no-hardcoded: colon-sep env-var name prefixes to flag as bare string
                           literals (write the shared const instead), e.g. "MYAPP_:OTHER_"
  perf-budgets.toml        perf-budget: criterion median ceilings (run after `cargo criterion`)
  perf-history.csv         perf-record: committed per-bench history; the PR diff = the perf report
  numerical-obligation.toml  numerical-obligation: [set."name"] entries → (baseline json, measurement
                           json, direction/tolerance/mode/ratchet). Baseline files are version-controlled,
                           measurement files written by your measurer at gate time.
  deny.toml                cargo-deny: license allow-list + advisory ignores

WIRE THE HOOKS (normally automatic via direnv / nix develop — both stages):
  just install-hooks    or    prek install -t pre-commit -t pre-push

GATE TRACING (opt-in per entry — wrap it):
  entry: guardrails-trace <name> -- <cmd...>   append one JSONL row per gate run (duration,
                           verdict, exit code) to the XDG cache — transparent: streams and
                           exit code pass through untouched
  guardrails info --perf   per-gate n/p50/p95/fail%/last-fail (+ tier-3 / retire hints)
  guardrails last          the most recent run's verdicts; any FAIL repeats on stderr and
                           exits 1 — a piped/truncated stdout can't swallow a red gate

FRESH-EYES REVIEW (author ≠ reviewer — see CONVENTIONS.md):
  guardrails diffpack             one reviewable artifact: escape-hatch + gate-config deltas
                                  first, ADR refs, then the diff — pipe to a fresh-context
                                  reviewer (agent or human) with refutation framing
  guardrails diffpack --base origin/main    branch review instead of working tree

STALE GATES (tiers by config, not by daemon — issue #13):
  guardrails stale         which gates are overdue — calendar (days since last green run)
                           AND churn (files/lines since) vs guardrails-stale.toml thresholds;
                           one line, exit 0 always. --json for prompt segments / agent hooks.
                           Delivered once/week after a push (guardrails-stale-nudge), same
                           throttle discipline as the freshness nudge.

FLAKE FRESHNESS (off the hot path — on demand, not on `cd`):
  guardrails freshness            this flake's inputs by lock age (offline)
  guardrails freshness --online   also flag inputs whose upstream ref moved
  guardrails freshness --json     machine output (fleet dashboard / push-time nudge)

MORE: docs/CONVENTIONS.md · github:gerchowl/guardrails
EOF
