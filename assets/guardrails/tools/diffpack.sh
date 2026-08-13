#!/usr/bin/env bash
# guardrails diffpack — one reviewable artifact for a fresh-eyes pass (issue #12).
#
# Authors are confirmation-blind to their own regressions; the fix is a fresh-context
# reviewer (human or agent) with REFUTATION framing ("try to refute that this works").
# That reviewer needs the full review surface in ONE read — not just the diff, but the
# governance context the diff touches. This command emits exactly that, to stdout:
#
#   1. WHAT     — working diff vs a base (default: staged+unstaged vs HEAD; --base <ref>
#                 for a branch review, e.g. --base origin/main).
#   2. CONTEXT  — governance surfaces the diff touches:
#                 * ADR sections referenced by changed hunks (ADR-NNN mentions),
#                 * gate-config deltas (guardrails-allow.txt, guardrails-baseline.txt,
#                   perf-budgets.toml, numerical-obligation.toml, .pre-commit-config.yaml,
#                   deny.toml) called out loudly — reviewers rubber-stamp these last,
#                 * escape-hatch deltas: added guardrails-ok / hardcode-ok / --no-verify
#                   mentions in the diff (an added escape IS review surface #1).
#   3. HOW TO REVIEW — the author≠reviewer contract (from CONVENTIONS.md), inlined so a
#                 spawned agent needs no other context.
#
# Usage: guardrails diffpack [--base <ref>]    (also: guardrails-diffpack)
set -uo pipefail

base=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --base) base="${2:?--base needs a ref}"; shift 2 ;;
    -h|--help) sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "guardrails-diffpack: unknown arg '$1' (try --base <ref>)" >&2; exit 2 ;;
  esac
done

git rev-parse --git-dir >/dev/null 2>&1 || { echo "guardrails-diffpack: not a git repo" >&2; exit 2; }

if [ -n "$base" ]; then
  diff_cmd=(git diff "$base"...HEAD)
  scope="$base...HEAD"
else
  diff_cmd=(git diff HEAD)
  scope="working tree vs HEAD"
fi

diff_out="$("${diff_cmd[@]}" 2>/dev/null)"
if [ -z "$diff_out" ]; then
  echo "guardrails-diffpack: no changes in scope ($scope) — nothing to pack." >&2
  exit 0
fi

echo "# diffpack — $scope"
echo "# repo: $(basename "$(git rev-parse --show-toplevel)") @ $(git rev-parse --short HEAD)"
echo

# ---- 2. governance context first (a reviewer reads this BEFORE the diff) -------------
echo "## Review surface"
echo

# Escape-hatch deltas: any ADDED line carrying an escape marker is the highest-signal
# review target — it's the author asking for an exemption.
escapes="$(printf '%s\n' "$diff_out" | grep -nE '^\+.*(guardrails-ok|hardcode-ok|--no-verify|GUARDRAILS_ALLOW_TRUNK)' | grep -v '^+++' || true)"
if [ -n "$escapes" ]; then
  echo "### ⚠ Added escape hatches (review these FIRST — each is a requested exemption)"
  printf '%s\n' "$escapes" | sed 's/^/    /'
  echo
fi

# Gate-config deltas: allowlists/baselines/budgets changing alongside code deserve
# suspicion — loosening the gate is how debt sneaks in with the feature.
gate_cfg="$(printf '%s\n' "$diff_out" | awk '/^diff --git/ { f=$3; sub(/^a\//, "", f) }
  /^diff --git/ && f ~ /(guardrails-allow\.txt|guardrails-baseline\.txt|perf-budgets\.toml|perf-history\.csv|numerical-obligation\.toml|\.pre-commit-config\.yaml|deny\.toml)$/ { print f }')"
if [ -n "$gate_cfg" ]; then
  echo "### ⚠ Gate-config deltas (is the gate being loosened to admit this diff?)"
  printf '%s\n' "$gate_cfg" | sed 's/^/    /'
  echo
fi

# ADR references in changed hunks: the reviewer must check the diff against what the
# cited decision actually says (drift between decided design and code is the #1 catch).
adrs="$(printf '%s\n' "$diff_out" | grep -oE 'ADR-[0-9]+' | LC_ALL=C sort -u || true)"
if [ -n "$adrs" ]; then
  echo "### ADRs referenced by changed hunks (diff must match the decided design)"
  for a in $adrs; do
    hit="$(git grep -l "$a" -- 'docs/adr/*' 'docs/*.md' 2>/dev/null | head -1 || true)"
    echo "    $a${hit:+ — $hit}"
  done
  echo
fi

# Derived-docs regions touched: hand-edits to generated regions will be reverted by the
# gate; flag them so the reviewer checks the SOURCE was regenerated instead.
derived="$(printf '%s\n' "$diff_out" | grep -c 'guardrails:derived' || true)"
if [ "${derived:-0}" -gt 0 ]; then
  echo "### Derived-docs regions in the diff ($derived marker line(s)) — was the generator re-run, or is this a hand-edit?"
  echo
fi

changed_files="$(printf '%s\n' "$diff_out" | grep -c '^diff --git' || true)"
echo "### Shape"
echo "    files changed: $changed_files    (+$(printf '%s\n' "$diff_out" | grep -c '^+[^+]') / -$(printf '%s\n' "$diff_out" | grep -c '^-[^-]') lines)"
echo

# ---- 3. the reviewer contract ----------------------------------------------------------
cat <<'EOF'
## Reviewer contract (author ≠ reviewer)
You are a FRESH-CONTEXT reviewer; the author's reasoning is not in your context, and that
is the point. Review with REFUTATION framing: actively try to prove this diff wrong,
regressive, or out of scope — do not summarize it back.
  1. Escape hatches + gate-config deltas above are the first read: each is the author
     asking to be exempted from a rule. Refute the justification.
  2. If an ADR is cited, read the ADR section and refute that the code matches it.
  3. Hunt regressions the author is blind to: retired concepts re-introduced, invariants
     silently weakened, tests that assert the happy path but not the documented pitfalls.
  4. Verdict format: approve / blockers (file:line) / nits. No hedging.

## Diff
EOF
printf '%s\n' "$diff_out"
