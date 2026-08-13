#!/usr/bin/env bash
# guardrails-nudge-ledger — the shared persistence-escalation harness for debt-class nudges
# (issue #32; mechanism extracted from the duplication gate, #31).
#
# The lifecycle a debt-class nudge needs is gate-agnostic: a finding is quiet when NEW, gets
# louder while it PERSISTS (age = commits since first seen — git as the deterministic clock),
# auto-PROMOTES to a hard block once it persists undealt-with past a threshold, and DROPS from
# the ledger when resolved (ratchet-shrink). Only the finding-key is gate-specific. Each gate
# shrinks to "detect → emit (key, count, label)"; this harness owns the ledger and the tiers.
#
# Interface (TSV on stdin, one finding per line):  key<TAB>count<TAB>label
#   key    stable identity of the finding (clone-hash / workflow path / crate name …)
#   count  a size the gate wants growth-tracked (sites, hits; 0 if n/a)
#   label  display text the gate will show its user
#
#   guardrails-nudge-ledger check  --ledger <path> [--enforce-age <n>] < findings.tsv
#     stdout, one line per finding:  key<TAB>tier<TAB>label
#       tier ∈ new | persisted:<age> | persisted:<age>:grew:<a>><b> | promoted:<age>
#     Exit 0 always — the GATE decides blocking from the tiers (it owns the vocabulary).
#   guardrails-nudge-ledger record --ledger <path> < findings.tsv
#     Reconciles the ledger: persisting keys keep their first-seen commit, new keys stamp at
#     HEAD, vanished (resolved) keys drop → the ledger only shrinks unless real drift appears.
#     Sorted output = clean diffs. Exit 0.
#
# Age caveat (from the #31 review): on shallow clones or after history rewrites the first-seen
# SHA may be unreachable — `git rev-list --count` fails, age falls back to 0 (fail-open: a bad
# ledger can silence escalation, never falsely block) and ONE warning goes to stderr so the
# hole is visible instead of silent.
#
# Ledger format note: rows are key<TAB>first_seen<TAB>count. #31-era duplication ledgers had a
# 4th span column — the reader takes the first three fields (col 3 kept its meaning), so old
# committed ledgers load correctly and the first re-record drops the span column. LOAD-BEARING:
# col 3 must stay "the growth-tracked count" in any future format change.
set -uo pipefail
TAB="$(printf '\t')"

mode="${1:?usage: guardrails-nudge-ledger check|record --ledger <path> [--enforce-age <n>]}"
shift
ledger="" enforce_age=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --ledger) ledger="${2:?--ledger needs a path}"; shift 2 ;;
    --enforce-age) enforce_age="${2:?--enforce-age needs a number}"; shift 2 ;;
    *) echo "guardrails-nudge-ledger: unknown arg '$1'" >&2; exit 2 ;;
  esac
done
[ -n "$ledger" ] || { echo "guardrails-nudge-ledger: --ledger is required" >&2; exit 2; }
case "$enforce_age" in ''|*[!0-9]*) echo "guardrails-nudge-ledger: --enforce-age must be a non-negative integer (got '$enforce_age')" >&2; exit 2 ;; esac

# Ledger rows: key<TAB>first_seen_commit<TAB>count
declare -A led_first led_count
if [ -f "$ledger" ]; then
  while IFS="$TAB" read -r k fseen c _; do
    [ -n "$k" ] || continue
    led_first["$k"]="$fseen"; led_count["$k"]="$c"
  done < "$ledger"
fi
head_sha="$(git rev-parse HEAD 2>/dev/null || true)"

warned_age=""
age_of() { # $1 = first-seen sha → commits since; 0 + one stderr warning when unreachable
  local a
  if a="$(git rev-list --count "$1..HEAD" 2>/dev/null)"; then
    printf '%s' "$a"
  else
    if [ -z "$warned_age" ]; then
      echo "guardrails-nudge-ledger: first-seen commit unreachable (shallow clone / rewritten history) — age treated as 0, escalation may under-fire here." >&2
      warned_age=1
    fi
    printf 0
  fi
}

out="" new_ledger=""
while IFS="$TAB" read -r key count label; do
  [ -n "$key" ] || continue
  first="${led_first[$key]:-}"
  if [ -n "$first" ]; then
    age="$(age_of "$first")"
    prev="${led_count[$key]:-$count}"
    grew=""
    [ "$count" -gt "$prev" ] 2>/dev/null && grew=":grew:$prev>$count"
    tier="persisted:$age$grew"
    if [ "$enforce_age" -gt 0 ] && [ "$age" -ge "$enforce_age" ] 2>/dev/null; then
      tier="promoted:$age$grew"
    fi
    stamp="$first"
  else
    tier="new"
    stamp="$head_sha"
  fi
  out+="$key$TAB$tier$TAB$label"$'\n'
  new_ledger+="$key$TAB$stamp$TAB$count"$'\n'
done

case "$mode" in
  check)
    printf '%s' "$out"
    ;;
  record)
    mkdir -p "$(dirname "$ledger")"
    printf '%s' "$new_ledger" | LC_ALL=C sort > "$ledger"
    ;;
  *) echo "guardrails-nudge-ledger: unknown mode '$mode' (check|record)" >&2; exit 2 ;;
esac
