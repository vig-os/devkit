#!/usr/bin/env bash
# guardrails-trace — wrap one gate/hook command, append a duration+verdict JSONL row (issue #14).
#
#   entry: guardrails-trace no-fake-impl -- guardrails-no-fake-impl
#
# Two motivations (both from real incidents):
#   * perf tuning needs per-gate timing history (deciding what belongs in a soft tier, #13);
#   * verdicts must survive stdout — a `git commit | tail` pipeline once masked a FAILED gate;
#     the JSONL is the durable out-of-band record `guardrails last` replays.
#
# The wrapper is transparent: stdout/stderr inherit, the wrapped command's exit code is
# propagated untouched. One row per run, single O_APPEND write ≪ PIPE_BUF → atomic without
# locks, safe across concurrent worktree commits. Rows go per-repo to
#   ${XDG_CACHE_HOME:-~/.cache}/guardrails/runs/<repo>-<pathhash>.jsonl   (10MB, 1 rotation)
#
# Row (v1, fixed key order): {"v":1,"ts","run_id","repo","gate","trigger","verdict","exit_code",
# "duration_ms","changed_files"} — verdict pass|fail AND the raw exit code (clippy 101 vs 1 is
# signal). GR_RUN_ID/GR_TRIGGER come from the injected hook bootstrap; absent (manual run) a
# per-invocation id + trigger=manual are stamped so rows never collide.
set -uo pipefail

gate="${1:?usage: guardrails-trace <name> -- <cmd...>}"
shift
[ "${1:-}" = "--" ] && shift
[ "$#" -gt 0 ] || { echo "guardrails-trace: nothing to run (usage: guardrails-trace <name> -- <cmd...>)" >&2; exit 2; }

# Millisecond clock. GNU date has %N (wall-clock ms — the dur<0 clamp below absorbs NTP
# steps); BSD (macOS) prints a literal 'N' → python3 monotonic_ns fallback (in the toolbelt).
# Probe ONCE at top level — inside $(now_ms) the assignment would die with the subshell.
GR_DATE_HAS_NS="$([ "$(date +%N)" != "N" ] && echo 1 || echo 0)"
now_ms() {
  if [ "$GR_DATE_HAS_NS" = 1 ]; then
    date +%s%3N
  else
    python3 -c 'import time; print(time.monotonic_ns() // 1000000)'
  fi
}

# changed_files ≈ trailing args that are existing files (prek appends the staged list after
# the command; a gate invoked bare scans the tree — count 0 means "whole tree / unknown").
# Skip $1 — the wrapped executable itself may be a file path and is not a changed file.
changed=0; skip_cmd=1
for a in "$@"; do
  if [ "$skip_cmd" = 1 ]; then skip_cmd=0; continue; fi
  [ -f "$a" ] && changed=$((changed + 1))
done

start="$(now_ms)"
"$@"
ec=$?
dur=$(( $(now_ms) - start ))
[ "$dur" -lt 0 ] && dur=0

repo_top="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
repo="$(basename "$repo_top")"
slug="$repo-$(printf '%s' "$repo_top" | git hash-object --stdin 2>/dev/null | cut -c1-6)"
dir="${XDG_CACHE_HOME:-$HOME/.cache}/guardrails/runs"
f="$dir/$slug.jsonl"
mkdir -p "$dir" 2>/dev/null || { exit "$ec"; }  # tracing must never break the gate

# Rotate at ~10MB, keep one generation (p95 stabilizes at ~200 samples/gate; this is years).
size=0; [ -f "$f" ] && size="$(wc -c < "$f")"
# (Concurrent hooks racing the threshold: the first mv wins, the loser's mv ENOENTs
# silently — worst case one rotation generation, never the live file.)
[ "${size:-0}" -gt 10485760 ] && mv -f "$f" "$f.1" 2>/dev/null

# JSON-escape interpolated strings (a repo dir named weird"repo must not corrupt the row).
esc() { printf '%s' "$1" | sed 's/[\\"]/\\&/g'; }
verdict=pass; [ "$ec" -ne 0 ] && verdict=fail
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
run_id="${GR_RUN_ID:-$(date +%s)-$$}"
trigger="${GR_TRIGGER:-manual}"
printf '{"v":1,"ts":"%s","run_id":"%s","repo":"%s","gate":"%s","trigger":"%s","verdict":"%s","exit_code":%d,"duration_ms":%d,"changed_files":%d}\n' \
  "$ts" "$(esc "$run_id")" "$(esc "$repo")" "$(esc "$gate")" "$(esc "$trigger")" "$verdict" "$ec" "$dur" "$changed" >> "$f" 2>/dev/null || true

exit "$ec"
