#!/usr/bin/env bash
# guardrails: every **Accepted** ADR is reflected in the project's feature/status matrix. An ADR
# records a decision; a hand-maintained FEATURE-MATRIX (or status doc) silently drifts the moment an
# ADR is accepted without a matching row — and `derived-docs` can't catch a doc that has no generator.
# This gate keys on ADR **status** (Accepted), NOT on edits, so Proposed ADRs (roadmap) and typo fixes
# never trip it; only *decided* designs are required to appear.
#
# SOURCE OF TRUTH — the ADR FILES, not the index. Each `<adr-dir>/NNNN-slug.md` carries its own
# `- Status: Accepted|Proposed|Superseded by NNNN` header, and that header IS the decision. This
# gate used to read the *index* (docs/adr/README.md) instead — a hand-maintained restatement of
# exactly that — so an Accepted ADR never added to the index was invisible to the gate built to
# catch unreflected decisions. Two ADRs shipped that way in a consumer repo, sharing one id, with
# the matrix citing that id for both documents. A gate that trusts a restatement has the very
# defect it exists to prevent.
#
# Three checks, all keyed on the files:
#   1. ids are unique     — two files claiming NNNN make every `ADR-NNNN` citation ambiguous
#   2. Accepted → matrix  — the original purpose, now on real input
#   3. Accepted → index   — the index is a DERIVED listing; if it exists it must be complete and
#                           must agree that the ADR is Accepted
#
# Legacy fallback: a repo with an index but no parseable ADR files keeps the old index-derived
# behaviour, so consumers that store ADRs elsewhere don't break.
#
# Convention: an ADR *index* (default docs/adr/README.md) has rows like
#   | [0024](0024-....md) | description | **Accepted** |
#
# Usage: guardrails-adr-matrix [<adr-index>] [<matrix>]
#   defaults: adr-index = docs/adr/README.md (else first **/adr/README.md)
#             matrix    = first **/FEATURE-MATRIX.md
# Exempt (recorded decisions that aren't feature rows): ADR numbers in guardrails-adr-exempt.txt
#   (one per line, '#' comments allowed) and/or the $ADR_MATRIX_EXEMPT env (space-separated).
set -uo pipefail

case "${1:-}" in -h | --help) sed -n '2,/^set /p' "$0" | sed 's/^# \{0,1\}//; /^set /d'; exit 0 ;; esac

index="${1:-}"
matrix="${2:-}"
[ -n "$index" ] || index="$([ -f docs/adr/README.md ] && echo docs/adr/README.md || find . -path '*/adr/README.md' -not -path '*/.git/*' 2>/dev/null | head -1)"
[ -n "$matrix" ] || matrix="$(find . -name 'FEATURE-MATRIX.md' -not -path '*/.git/*' 2>/dev/null | head -1)"
[ -f "$index" ] || { echo "guardrails-adr-matrix: no ADR index found — nothing to check"; exit 0; }
[ -f "$matrix" ] || { echo "guardrails-adr-matrix: ADR index present but no FEATURE-MATRIX.md found" >&2; exit 1; }

exempt=" ${ADR_MATRIX_EXEMPT:-} "
[ -f guardrails-adr-exempt.txt ] && exempt="$exempt $(grep -vE '^[[:space:]]*#' guardrails-adr-exempt.txt | tr '\n' ' ') "
is_exempt() { case "$exempt" in *" $1 "*) return 0 ;; esac; return 1; }

adr_dir="$(dirname "$index")"

status_of() { grep -iEm1 '^[^A-Za-z]*Status:' "$1" | sed 's/.*[Ss]tatus:[[:space:]]*//' | tr -d '*'; }
id_of() { basename "$1" | cut -c1-4; }

# --- discover the ADR files (the source of truth) -----------------------------
adr_files=()
while IFS= read -r f; do
  [ -n "$f" ] && adr_files+=("$f")
done <<EOF
$(find "$adr_dir" -maxdepth 1 -type f -name '[0-9][0-9][0-9][0-9]-*.md' 2>/dev/null | sort)
EOF

if [ "${#adr_files[@]}" -eq 0 ]; then
  # Legacy: no ADR files to read — fall back to the index as the (weaker) input.
  echo "guardrails-adr-matrix: no ADR files under $adr_dir — falling back to the index" >&2
  missing=""
  while IFS= read -r line; do
    num="$(printf '%s' "$line" | grep -oE '\[0[0-9]{3}\]' | head -1 | tr -dc '0-9')" || true
    [ -n "$num" ] || continue
    printf '%s' "$line" | grep -qi 'Accepted' || continue
    is_exempt "$num" && continue
    grep -q "ADR-$num" "$matrix" || missing="$missing $num"
  done <"$index"
  if [ -n "$missing" ]; then
    echo "✗ adr-matrix: Accepted ADR(s) not cited in $(basename "$matrix"):$missing" >&2
    echo "  → add a row citing ADR-NNNN, or exempt it (guardrails-adr-exempt.txt / \$ADR_MATRIX_EXEMPT)." >&2
    exit 1
  fi
  echo "✓ adr-matrix: every Accepted ADR is cited in $(basename "$matrix") (index-derived)"
  exit 0
fi

# --- 1. ids must be unique ----------------------------------------------------
dupes="$(for f in "${adr_files[@]}"; do id_of "$f"; done | sort | uniq -d | tr '\n' ' ')"
if [ -n "${dupes// /}" ]; then
  echo "✗ adr-matrix: duplicate ADR id(s) in $adr_dir: ${dupes% }" >&2
  for d in $dupes; do
    for f in "${adr_files[@]}"; do
      [ "$(id_of "$f")" = "$d" ] && echo "    $f" >&2
    done
  done
  echo "  → renumber one of them; every 'ADR-NNNN' citation is ambiguous while both exist." >&2
  exit 1
fi

# --- 2 + 3. Accepted ADRs must reach the matrix AND the index -----------------
missing_matrix=""
missing_index=""
for f in "${adr_files[@]}"; do
  num="$(id_of "$f")"
  case "$(status_of "$f")" in [Aa]ccepted*) ;; *) continue ;; esac
  is_exempt "$num" && continue
  grep -q "ADR-$num" "$matrix" || missing_matrix="$missing_matrix $num"
  # The index row for NNNN must exist AND agree that it is Accepted.
  grep -E "\[$num\]" "$index" | grep -qi 'Accepted' || missing_index="$missing_index $num"
done

rc=0
if [ -n "$missing_matrix" ]; then
  echo "✗ adr-matrix: Accepted ADR(s) not cited in $(basename "$matrix"):$missing_matrix" >&2
  echo "  → add a row citing ADR-NNNN, or exempt it (guardrails-adr-exempt.txt / \$ADR_MATRIX_EXEMPT)." >&2
  rc=1
fi
if [ -n "$missing_index" ]; then
  echo "✗ adr-matrix: Accepted ADR(s) missing from (or not Accepted in) $index:$missing_index" >&2
  echo "  → the index is a derived listing: add the row, or fix its Status column to match the ADR." >&2
  rc=1
fi
[ "$rc" = 0 ] || exit 1

echo "✓ adr-matrix: every Accepted ADR is cited in $(basename "$matrix") and listed in $(basename "$index")"
