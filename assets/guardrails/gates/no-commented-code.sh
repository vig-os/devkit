#!/usr/bin/env bash
# guardrails: no commented-out code (use git history, not graveyards).
# Conservative heuristic: comment lines that end in code punctuation (; { }) — strong commented-code
# signal — excluding doc comments (/// //! #!) and `guardrails-ok`. Tuned for low false-positives.
set -uo pipefail
roots=("${@:-.}")
hits=0
files() {
  for p in "$@"; do
    if [ -d "$p" ]; then git -C "$p" ls-files 2>/dev/null | sed "s#^#${p%/}/#" || find "$p" -type f
    elif [ -f "$p" ]; then echo "$p"; fi
  done
}
while IFS= read -r f; do
  case "$f" in *.rs|*.ts|*.tsx|*.js|*.mjs|*.go) ;; *) continue ;; esac
  case "$f" in *gates/*|tests/*|*/tests/*) continue ;; esac
  # `//` (not /// or //!) followed by something ending in ; { or } → looks like commented-out code.
  while IFS=: read -r no line; do
    case "$line" in *guardrails-ok*) continue ;; esac
    printf '  %s:%s:%s\n' "$f" "$no" "$(printf '%s' "$line" | sed 's/^[[:space:]]*//')"
    hits=$((hits + 1))
  done < <(grep -nE '^[[:space:]]*//[^/!].*[;{}][[:space:]]*$' "$f" 2>/dev/null)
done < <(files "${roots[@]}")
if [ "$hits" -gt 0 ]; then
  echo "guardrails/no-commented-code: $hits commented-out code line(s) — delete (git remembers), or annotate 'guardrails-ok'." >&2
  exit 1
fi
