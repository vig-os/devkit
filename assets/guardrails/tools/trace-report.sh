#!/usr/bin/env bash
# guardrails-trace-report — read the per-repo trace JSONL (written by guardrails-trace) and
# answer the two questions that justify its existence (issue #14):
#
#   perf [--window <days>]   per-gate n · p50 · p95 · fail% · last-fail over the window
#                            (default 30d) + the tiering hints: a p95 way past the commit
#                            budget is a tier-3 candidate (#13); a gate that never fired
#                            in the window may not be earning its place.
#   last                     the most recent run's verdicts — the out-of-band answer to a
#                            `git commit | tail` pipeline swallowing a FAILED gate. Any FAIL
#                            is duplicated to stderr and exits 1: impossible to miss.
#
# Reads only the local XDG cache; no network, no repo writes.
set -uo pipefail

mode="${1:-perf}"
shift 2>/dev/null || true
window_days=30
while [ "$#" -gt 0 ]; do
  case "$1" in
    --window) window_days="${2:?--window needs days}"; shift 2 ;;
    *) echo "guardrails-trace-report: unknown arg '$1'" >&2; exit 2 ;;
  esac
done

repo_top="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
slug="$(basename "$repo_top")-$(printf '%s' "$repo_top" | git hash-object --stdin 2>/dev/null | cut -c1-6)"
f="${XDG_CACHE_HOME:-$HOME/.cache}/guardrails/runs/$slug.jsonl"
if [ ! -s "$f" ]; then
  echo "guardrails: no trace data for this repo yet ($f)." >&2
  echo "Wrap hook entries with guardrails-trace to start recording — see 'guardrails info'." >&2
  exit 0
fi

# Rows are machine-written with fixed key order — extract fields by key, no jq dependency.
case "$mode" in
  perf)
    cutoff="$(date -u -v-"${window_days}"d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
             || date -u -d "-${window_days} days" +%Y-%m-%dT%H:%M:%SZ)"
    awk -v cutoff="$cutoff" '
      function field(s, k,   r) { r = ""; if (match(s, "\"" k "\":\"[^\"]*\"")) { r = substr(s, RSTART, RLENGTH); sub("\"" k "\":\"", "", r); sub(/"$/, "", r) } return r }
      function nfield(s, k,  r) { r = ""; if (match(s, "\"" k "\":[0-9-]+"))    { r = substr(s, RSTART, RLENGTH); sub("\"" k "\":", "", r) } return r }
      {
        ts = field($0, "ts"); if (ts < cutoff) next
        g = field($0, "gate"); if (g == "") next
        n[g]++
        durs[g, n[g]] = nfield($0, "duration_ms") + 0
        if (field($0, "verdict") == "fail") { fails[g]++; lastfail[g] = ts }
      }
      END {
        if (!length(n)) { print "no rows in the last window — widen with --window <days>"; exit }
        printf "%-24s %5s %8s %8s %6s  %-20s %s\n", "gate", "n", "p50", "p95", "fail%", "last-fail", "hint"
        for (g in n) {
          m = n[g]
          # insertion sort — m is small (hundreds)
          for (i = 2; i <= m; i++) { v = durs[g, i]; j = i - 1
            while (j >= 1 && durs[g, j] > v) { durs[g, j + 1] = durs[g, j]; j-- } durs[g, j + 1] = v }
          p50 = durs[g, int((m + 1) * 0.50) < 1 ? 1 : int((m + 1) * 0.50)]
          p95i = int((m + 1) * 0.95); if (p95i < 1) p95i = 1; if (p95i > m) p95i = m
          p95 = durs[g, p95i]
          fr = (fails[g] + 0) * 100.0 / m
          hint = ""
          if (p95 > 5000) hint = "tier-3 candidate (p95 > 5s commit budget)"
          else if ((fails[g] + 0) == 0 && m >= 20) hint = "never fired in window — earning its place?"
          printf "%-24s %5d %7.2fs %7.2fs %5.1f%%  %-20s %s\n", g, m, p50 / 1000.0, p95 / 1000.0, fr, (g in lastfail ? lastfail[g] : "never"), hint
        }
      }' "$f" | { IFS= read -r hdr; printf '%s\n' "$hdr"; LC_ALL=C sort; }
    ;;
  last)
    last_id="$(awk 'match($0, /"run_id":"[^"]*"/) { r = substr($0, RSTART + 10, RLENGTH - 11) } END { print r }' "$f")"
    [ -n "$last_id" ] || { echo "guardrails: trace file has no run ids." >&2; exit 0; }
    out="$(awk -v id="$last_id" '
      function field(s, k,   r) { r = ""; if (match(s, "\"" k "\":\"[^\"]*\"")) { r = substr(s, RSTART, RLENGTH); sub("\"" k "\":\"", "", r); sub(/"$/, "", r) } return r }
      function nfield(s, k,  r) { r = ""; if (match(s, "\"" k "\":[0-9-]+"))    { r = substr(s, RSTART, RLENGTH); sub("\"" k "\":", "", r) } return r }
      index($0, "\"run_id\":\"" id "\"") {
        v = field($0, "verdict"); up = toupper(v)
        printf "  %-6s %-24s %6.2fs\n", up, field($0, "gate"), nfield($0, "duration_ms") / 1000.0
        if (v == "fail") bad = 1
      }
      END { exit bad ? 1 : 0 }' "$f")"
    bad=$?
    first_ts="$(awk -v id="$last_id" 'index($0, "\"run_id\":\"" id "\"") { if (match($0, /"ts":"[^"]*"/)) { print substr($0, RSTART + 6, RLENGTH - 7); exit } }' "$f")"
    trig="$(awk -v id="$last_id" 'index($0, "\"run_id\":\"" id "\"") { if (match($0, /"trigger":"[^"]*"/)) { print substr($0, RSTART + 11, RLENGTH - 12); exit } }' "$f")"
    echo "guardrails last — run $last_id · $first_ts · $trig"
    printf '%s\n' "$out"
    if [ "$bad" -ne 0 ]; then
      printf '%s\n' "$out" | grep '  FAIL' >&2
      echo "guardrails last: FAILED gate(s) in the most recent run — see above." >&2
      exit 1
    fi
    ;;
  *)
    echo "guardrails-trace-report: unknown mode '$mode' (perf|last)" >&2; exit 2 ;;
esac
