#!/usr/bin/env bash
# guardrails: derived docs match their source of truth. A doc/region that says it was generated
# from `cmd` must STILL match `cmd`'s output — otherwise the docs lie. Hand-maintained "see also"
# tables, generated CLI help, dumped schemas: all drift the moment the source moves. This gate
# re-runs the declared command and diffs.
#
# Marker syntax (anywhere in a text file):
#   <!-- guardrails:derived cmd="<shell command>" -->
#   ...derived content...
#   <!-- guardrails:derived:end -->
#
# Check mode (default): for each region, run `sh -c "$cmd"` at the repo root, trim trailing
# whitespace per line + normalize the final newline, diff against the region. Mismatch → exit 1
# with a unified diff and the `--fix` hint.
# Fix mode (`--fix`): rewrite each region in place with fresh output.
#
# SECURITY — the commands run with the same trust as any pre-commit hook in this repo: the gate
# executes what the REPO declares. A malicious marker is no different from a malicious hook entry;
# review marker commands the same way you review `.pre-commit-config.yaml`. By design, not a bug.
set -uo pipefail

fix=0
roots=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --fix) fix=1; shift ;;
    --)    shift; while [ "$#" -gt 0 ]; do roots+=("$1"); shift; done ;;
    -h|--help)
      sed -n '2,/^set /p' "$0" | sed 's/^# \{0,1\}//; /^set /d'
      exit 0 ;;
    -*) echo "guardrails/derived-docs: unknown flag '$1'" >&2; exit 2 ;;
    *)  roots+=("$1"); shift ;;
  esac
done
[ "${#roots[@]}" -eq 0 ] && roots=(".")

# File list: explicit args (prek passes staged files), else git-tracked files at the root. We scan
# tracked TEXT files only — binary blobs can't carry a marker comment anyway, and the cost of
# `file -b` per blob is real on large repos.
list_files() {
  for p in "$@"; do
    if [ -d "$p" ]; then
      ( cd "$p" && git ls-files 2>/dev/null ) | sed "s#^#${p%/}/#" \
        || find "$p" -type f -not -path '*/.git/*'
    elif [ -f "$p" ]; then
      printf '%s\n' "$p"
    fi
  done
}

# A region looks like:
#   <!-- guardrails:derived cmd="..." -->\n<body>\n<!-- guardrails:derived:end -->
# We tolerate leading whitespace on the marker lines (markdown indents inside lists etc.) but the
# START and END markers must be on lines of their own. Quotes around the command may be " or '.
# bash regex is POSIX ERE (no backrefs), so we accept "any quote / any quote" and let the inner
# (.*) be greedy minus the trailing `"` / `'` — both quote forms in practice land on a balanced
# pair because the content is a shell command (the alternative would be picking the wrong closing
# quote, which a sane command line doesn't produce).
START_RE_DQ='^[[:space:]]*<!--[[:space:]]*guardrails:derived[[:space:]]+cmd="(.*)"[[:space:]]*-->[[:space:]]*$'
START_RE_SQ="^[[:space:]]*<!--[[:space:]]*guardrails:derived[[:space:]]+cmd='(.*)'[[:space:]]*-->[[:space:]]*\$"
END_RE='^[[:space:]]*<!--[[:space:]]*guardrails:derived:end[[:space:]]*-->[[:space:]]*$'

# match_start <line> → echo command on stdout, return 0; else return 1.
match_start() {
  if [[ "$1" =~ $START_RE_DQ ]]; then printf '%s' "${BASH_REMATCH[1]}"; return 0; fi
  if [[ "$1" =~ $START_RE_SQ ]]; then printf '%s' "${BASH_REMATCH[1]}"; return 0; fi
  return 1
}

# Normalize a stream: strip trailing whitespace per line; ensure exactly one trailing newline.
# (Same shape `sed` + a final newline. POSIX-portable.)
normalize() { sed -e 's/[[:space:]]\+$//'; }

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

hits=0
errors=0

process_file() {
  local f="$1"
  [ -f "$f" ] || return 0
  # Quick reject: file has neither start nor end marker.
  if ! grep -qE 'guardrails:derived' "$f" 2>/dev/null; then return 0; fi

  # Walk the file line by line, tracking region state.
  local lineno=0 in_region=0 region_start=0 body_start=0 cmd="" body=""
  local out_lines=() change=0
  while IFS= read -r line || [ -n "$line" ]; do
    lineno=$((lineno + 1))
    if [ "$in_region" = 0 ]; then
      if cmd="$(match_start "$line")"; then
        in_region=1
        region_start=$lineno
        body=""
        out_lines+=("$line")
        # Body position in REBUILT-OUTPUT coordinates: once an earlier region's
        # replacement changed the line count, source line numbers no longer map
        # onto out_lines — truncating by them eats the text between regions.
        body_start=${#out_lines[@]}
        continue
      fi
      if [[ "$line" =~ $END_RE ]]; then
        echo "guardrails/derived-docs: $f:$lineno: stray :end marker without a matching start" >&2
        errors=$((errors + 1))
        out_lines+=("$line")
        continue
      fi
      out_lines+=("$line")
    else
      # Inside a region: another start marker = nested (illegal).
      if cmd2="$(match_start "$line")"; then
        echo "guardrails/derived-docs: $f:$lineno: nested derived region (started at line $region_start)" >&2
        errors=$((errors + 1))
        # Recover: treat as a fresh start so we don't cascade.
        region_start=$lineno
        cmd="$cmd2"
        body=""
        out_lines+=("$line")
        body_start=${#out_lines[@]}
        continue
      fi
      if [[ "$line" =~ $END_RE ]]; then
        # Run the command, normalize, compare.
        local fresh
        if ! fresh="$(cd "$repo_root" && sh -c "$cmd" 2>&1)"; then
          echo "guardrails/derived-docs: $f:$region_start: command failed: $cmd" >&2
          printf '%s\n' "$fresh" | sed 's/^/    /' >&2
          errors=$((errors + 1))
          out_lines+=("$line")
          in_region=0
          continue
        fi
        local fresh_n have_n
        fresh_n="$(printf '%s\n' "$fresh" | normalize)"
        have_n="$(printf '%s' "$body" | normalize)"
        # Strip a single trailing newline from each side so the diff isn't noisy about it.
        if [ "$fresh_n" != "$have_n" ]; then
          hits=$((hits + 1))
          if [ "$fix" = 1 ]; then
            change=1
            # Replace the region body with fresh content: drop the body lines already pushed
            # (everything after the start marker, whose rebuilt-output position is body_start)
            # and push the fresh ones instead.
            out_lines=("${out_lines[@]:0:$body_start}")
            # Push each line of fresh_n. printf with %s and read -r preserves embedded blanks.
            while IFS= read -r fl; do out_lines+=("$fl"); done <<< "$fresh_n"
          else
            echo "guardrails/derived-docs: $f:$region_start: derived region out of date" >&2
            echo "    command: $cmd" >&2
            # Unified diff (have → want). Use process substitutions; bash-only is fine here.
            diff -u --label "$f (current)" --label "$f (from: $cmd)" \
              <(printf '%s\n' "$have_n") <(printf '%s\n' "$fresh_n") \
              | sed 's/^/    /' >&2 || true
            echo "    run with --fix to regenerate" >&2
          fi
        fi
        out_lines+=("$line")
        in_region=0
        continue
      fi
      # Accumulate body. Join with literal newlines.
      if [ -z "$body" ]; then body="$line"; else body="$body"$'\n'"$line"; fi
      out_lines+=("$line")
    fi
  done < "$f"

  if [ "$in_region" = 1 ]; then
    echo "guardrails/derived-docs: $f:$region_start: unterminated derived region (no :end marker)" >&2
    errors=$((errors + 1))
  fi

  # In --fix mode, write back if anything changed.
  if [ "$fix" = 1 ] && [ "$change" = 1 ] && [ "$errors" = 0 ]; then
    # Preserve trailing-newline semantics: every line gets one \n; the original file probably
    # ended with \n too, so this is the right shape for tracked text files.
    local tmp; tmp="$(mktemp)"
    : > "$tmp"
    local l
    for l in "${out_lines[@]}"; do
      printf '%s\n' "$l" >> "$tmp"
    done
    mv "$tmp" "$f"
    echo "guardrails/derived-docs: $f: regenerated" >&2
  fi
}

while IFS= read -r f; do
  # Skip obvious binaries by extension (cheap, no `file` dep).
  case "$f" in
    *.png|*.jpg|*.jpeg|*.gif|*.ico|*.pdf|*.woff|*.woff2|*.ttf|*.otf|*.bin|*.zip|*.tar|*.tgz|*.lock) continue ;;
    */.git/*) continue ;;
  esac
  process_file "$f"
done < <(list_files "${roots[@]}")

if [ "$errors" -gt 0 ]; then
  echo "guardrails/derived-docs: $errors marker error(s) — fix the syntax (no escape; bad markers can't be diffed)." >&2
  exit 1
fi
if [ "$hits" -gt 0 ] && [ "$fix" = 0 ]; then
  echo "guardrails/derived-docs: $hits region(s) out of date — re-run with --fix to regenerate." >&2
  exit 1
fi
exit 0
