#!/usr/bin/env bash
# guardrails: no debug-print leftovers — force the logging/tracing facade, not stdout spew.
# Flags dbg!()/print!()/println!()/eprint!()/eprintln!() (Rust) and console.log/debug + print(
# (TS/JS/Py) in lib/app code. Always allowed in main.rs/build.rs/bin/tests/examples (build.rs
# uses println! for cargo: directives), and on any line annotated `guardrails-ok`.
#
# CLI tools legitimately write to stdout/stderr. Set GUARDRAILS_OUTPUT_GLOBS to a colon-separated
# list of path globs for those output surfaces (e.g. "*/cli/*:*/cli.rs:*/update.rs") so the gate
# stays high-signal on app/library code instead of drowning in command-output false positives.
set -uo pipefail
roots=("${@:-.}")
hits=0

IFS=: read -ra output_globs <<< "${GUARDRAILS_OUTPUT_GLOBS:-}"

# A path is an allowed output surface if it's a built-in entrypoint/test path, or matches one of
# the repo-configured GUARDRAILS_OUTPUT_GLOBS.
allowed_output() {
  # Dir-walks arrive './'-prefixed (files() sed); normalize so globs without a
  # leading '*' (vendor/*, scripts/*) still match.
  set -- "${1#./}"
  case "$1" in *gates/*|tests/*|*/tests/*|*_test.*|*.test.*|examples/*|*/examples/*|main.rs|*/main.rs|build.rs|*/build.rs|bin/*|*/bin/*) return 0 ;; esac
  local g
  for g in "${output_globs[@]}"; do
    [ -n "$g" ] || continue
    # $g is intentionally a glob pattern for case-matching
    # shellcheck disable=SC2254
    case "$1" in $g) return 0 ;; esac
  done
  return 1
}

files() {
  for p in "$@"; do
    if [ -d "$p" ]; then git -C "$p" ls-files 2>/dev/null | sed "s#^#${p%/}/#" || find "$p" -type f
    elif [ -f "$p" ]; then echo "$p"; fi
  done
}

# Filtering is pure bash (no per-file process). Rust vs web/py use different
# patterns, so partition into two batches, then run grep ONCE per batch instead
# of once per file — the fork-exec per file was the whole cost on a large tree.
rust_files=(); web_files=()
while IFS= read -r f; do
  case "$f" in *.rs) ;; *.ts|*.tsx|*.js|*.mjs|*.py) ;; *) continue ;; esac
  allowed_output "$f" && continue
  case "$f" in *.rs) rust_files+=("$f") ;; *) web_files+=("$f") ;; esac
done < <(files "${roots[@]}")

rust_pat='dbg!\(|e?println!\(|e?print!\('
web_pat='dbg!\(|console\.(log|debug)\(|[[:space:]]print\('

# grep -nHE over a NUL-delimited batch: -H forces the file: prefix even for a
# single file, xargs -0 survives paths with spaces. Length-guarded so an empty
# batch never feeds grep an empty arg list (which would block on stdin).
matches=""
if [ "${#rust_files[@]}" -gt 0 ]; then
  matches+="$(printf '%s\0' "${rust_files[@]}" | xargs -0 grep -nHE "$rust_pat" 2>/dev/null)"$'\n'
fi
if [ "${#web_files[@]}" -gt 0 ]; then
  matches+="$(printf '%s\0' "${web_files[@]}" | xargs -0 grep -nHE "$web_pat" 2>/dev/null)"$'\n'
fi

# Drop `guardrails-ok`-annotated lines (per-line escape). Scope the filter to the
# content past the `file:line:` prefix — filtering the whole joined line would let
# a path containing 'guardrails-ok' suppress every finding under it.
leaks="$(printf '%s' "$matches" | awk '{ c=$0; sub(/^[^:]+:[0-9]+:/, "", c); if (c !~ /guardrails-ok/ && $0 !~ /^[[:space:]]*$/) print }')"
if [ -n "$leaks" ]; then
  printf '%s\n' "$leaks" | sed -E 's/^([^:]+:[0-9]+:)[[:space:]]*/  \1/'
  hits=$(printf '%s\n' "$leaks" | grep -c .)
fi

if [ "$hits" -gt 0 ]; then
  echo "guardrails/no-debug-leftovers: $hits debug-print(s) — use the tracing facade, or annotate 'guardrails-ok'." >&2
  exit 1
fi
