#!/usr/bin/env bash
# guardrails: no committed merge-conflict markers. A conflicted merge can be committed with the
# `<<<<<<<`/`=======`/`>>>>>>>` markers still in the file — git happily records it, `git status`
# is clean afterwards, and the file is silently broken (a real incident: markers committed into a
# flake.nix made `nix develop` unevaluable on main while every status looked green).
#
# Deterministic, zero-false-positive-by-construction:
#   * `<<<<<<< ` and `>>>>>>> ` at line start are flagged unconditionally (the space+ref form git
#     writes; a 7-char ASCII arrow run starting a line has no legitimate use in source).
#   * a bare `=======` line is flagged ONLY if the same file also contains a `<<<<<<<` marker —
#     setext markdown headings underlined with equals signs stay legal.
# No escape hatch on purpose: there is no legitimate committed conflict marker.
set -uo pipefail

roots=("${@:-.}")
hits=0

# Build the file list: explicit args (prek passes staged files), else git-tracked text files.
list_files() {
  if [ "$#" -gt 0 ] && [ "$1" != "." ]; then
    printf '%s\n' "$@"
  else
    git ls-files 2>/dev/null || find . -type f -not -path './.git/*'
  fi
}

while IFS= read -r f; do
  [ -f "$f" ] || continue
  case "$f" in *.png|*.jpg|*.jpeg|*.gif|*.ico|*.pdf|*.woff*|*.bin|*.lock) continue ;; esac
  # Markers written literally (awk interval-regex portability); they sit mid-line here, and the
  # gate only flags them at line START, so this file does not flag itself.
  out="$(awk '
    /^<<<<<<<( |$)/ { print FILENAME ":" FNR ": " $0; start = 1; next }
    /^>>>>>>>( |$)/ { print FILENAME ":" FNR ": " $0; next }
    /^=======$/     { eq[FNR] = $0 }
    END { if (start) for (n in eq) print FILENAME ":" n ": " eq[n] }
  ' "$f" 2>/dev/null)"
  if [ -n "$out" ]; then
    printf '%s\n' "$out"
    hits=$((hits + $(printf '%s\n' "$out" | grep -c .)))
  fi
done < <(list_files "${roots[@]}")

if [ "$hits" -gt 0 ]; then
  echo "guardrails/no-conflict-markers: $hits merge-conflict marker line(s) committed — resolve the conflict (no escape: there is no legitimate committed marker)." >&2
  exit 1
fi
