#!/usr/bin/env bash
# guardrails: no bare hardcoded values — wrap them in `const_tunable!` / `config!` so every magic
# value lands in the generated TUNABLES.md (registered + auditable from one file). This is the
# enforcement half of the decorator→registry pattern.
#
# Heuristic (low false-positive, documented): in scanned `crates/*/src/**/*.rs` and root
# `src/**/*.rs` (single-crate repos), flags
#   * float literals (except 0.0/0.5/1.0/2.0) — checked PER TOKEN, so an allowed `0.0` on the same
#     line doesn't mask a `3.7`,
#   * decimal integers >= 100 (hex/binary excluded; digit-group underscores normalised so `100_000`
#     is still seen),
#   * absolute `/Users/`, `/home/`, `/tmp/` paths — checked with string literals INTACT (that's
#     where paths live),
#   * bare project env-var name literals, when GUARDRAILS_ENV_PREFIXES is set (colon-separated,
#     e.g. "MYAPP_:OTHER_") — write the shared const, not the string.
# Exempt when the line:
#   - is inside a `const_tunable!(...)` / `config!(...)` invocation (the sanctioned home), or
#   - carries `guardrails-ok` / `hardcode-ok`, or sits inside a
#     `guardrails-ok-begin` … `guardrails-ok-end` block (hardcode-ok-begin/-end work too), or
#   - sits in the `#[cfg(test)]`-attributed item (module body or brace-less item), or
#   - the file/prefix is listed in `guardrails-allow.txt`.
#
# RATCHET MODE (adoption without big-bang triage, issue #30): commit a per-file count snapshot
# (`guardrails-no-hardcoded --record-baseline` → guardrails-baseline.txt, or point
# GUARDRAILS_HARDCODED_BASELINE elsewhere). With a baseline present, per file:
#   count > baseline → HARD FAIL (new magic values are gated — strict on growth),
#   count < baseline → pass + nudge to re-record (the ratchet only tightens),
#   count = baseline → pass, silently.
# `--record-baseline` refuses to snapshot a count higher than the committed one. No baseline
# file → exactly today's all-or-nothing behavior; existing consumers are unaffected.
set -uo pipefail
root="$(git rev-parse --show-toplevel 2>/dev/null || echo .)"
cd "$root" || exit 2
allow="guardrails-allow.txt"
baseline="${GUARDRAILS_HARDCODED_BASELINE:-guardrails-baseline.txt}"

record=0
if [ "${1:-}" = "--record-baseline" ]; then record=1; shift; fi

files=()
# --record-baseline snapshots the WHOLE scan surface (a baseline of just-staged files would
# shrink the committed snapshot to whatever happened to be in the index).
if [ "$#" -gt 0 ] && [ "$record" = 0 ]; then for a in "$@"; do files+=("$a"); done
else while IFS= read -r x; do files+=("$x"); done < <({ find crates -type f -name '*.rs' -path '*/src/*'; find src -type f -name '*.rs'; } 2>/dev/null); fi

prefixes=()
[ -f "$allow" ] && while IFS= read -r l; do l="${l%%#*}"; l="$(printf '%s' "$l" | tr -d '[:space:]')"; [ -n "$l" ] && prefixes+=("$l"); done < "$allow"

is_exempt() {
  # Normalise `./src/x.rs` → `src/x.rs` so the repo-root patterns below match both shapes.
  local path="${1#./}"
  case "$path" in *.rs) ;; *) return 0 ;; esac
  # `src/*` covers single-crate repos (pre-commit passes RELATIVE paths from the repo root —
  # `src/foo.rs` never matches `*/src/*`, which previously made the gate vacuously green there);
  # `*/src/*` covers workspace `crates/*/src/**` and absolute paths.
  case "$path" in src/*|*/src/*) ;; *) return 0 ;; esac
  # NB: guard the empty expansion — `"${prefixes[@]:-}"` yields ONE EMPTY WORD when the array is
  # empty, and an empty prefix `case`-matches every path: without this guard the gate silently
  # exempted ALL files whenever guardrails-allow.txt was absent (a vacuously-green gate).
  for p in "${prefixes[@]:-}"; do
    [ -n "$p" ] || continue
    case "$path" in "$p"*) return 0 ;; esac
  done
  return 1
}

# Colon-separated env-name prefixes to flag as bare string literals (project env vars belong in
# one shared const). Converted to an ERE alternation for awk; empty = check disabled.
env_re=""
if [ -n "${GUARDRAILS_ENV_PREFIXES:-}" ]; then
  env_re="$(printf '%s' "$GUARDRAILS_ENV_PREFIXES" | tr -s ':' '|' | sed 's/^|//; s/|$//')"
fi

hits=0
all_out=""   # every hit line (printed straight in all-or-nothing mode, filtered in ratchet mode)
counts=""    # "path<TAB>count" per scanned file (count 0 included — burn-down detection needs it)
for f in "${files[@]:-}"; do
  [ -f "$f" ] || continue
  is_exempt "$f" && continue
  out="$(awk -v env_re="$env_re" '
    # #[cfg(test)] exempts only the ITEM it attributes, not the rest of the file: arm on the
    # attribute, then skip until the item body closes (brace-counted on a string/comment-stripped
    # copy) or a brace-less item (`use`/`mod foo;`/const) ends in `;`. Previously the flag never
    # reset, so all prod code below any mid-file test attr/helper went unscanned to EOF.
    /#\[cfg\(test\)\]/ { intest = 1; tdepth = 0 }
    intest {
      body = $0
      sub(/\/\/.*/, "", body)
      gsub(/"[^"]*"/, "", body)
      opens = gsub(/{/, "", body); closes = gsub(/}/, "", body)
      tdepth += opens - closes
      if (opens + closes > 0 && tdepth <= 0) intest = 0
      else if (opens == 0 && tdepth == 0 && body ~ /;[[:space:]]*$/) intest = 0
      next
    }
    /guardrails-ok-begin|hardcode-ok-begin/ { inblock = 1; next }   # block escape: exempt until -end
    /guardrails-ok-end|hardcode-ok-end/     { inblock = 0; next }
    inblock { next }
    /const_tunable!|config!|guardrails-ok|hardcode-ok/ { next }
    {
      line = $0
      sub(/\/\/.*/, "", line)            # strip // line comments
      # Path/env-name checks run with STRING LITERALS INTACT — that is where these values live.
      if (line ~ /\/Users\/|\/home\/|\/tmp\//) { print FILENAME ":" FNR ": " $0; next }
      if (env_re != "" && line ~ ("\"(" env_re ")")) { print FILENAME ":" FNR ": " $0; next }
      # Numeric checks run on a string-blanked copy (format specs / escape sequences are not values).
      nostr = line
      gsub(/"[^"]*"/, "", nostr)
      # Normalise digit-group underscores so 100_000 is still a 6-digit integer to the checks below.
      while (nostr ~ /[0-9]_[0-9]/) { gsub(/_/, "", nostr) }
      # Floats: PER TOKEN, so an allowed 0.0 on the line does not mask a flagged 3.7.
      s = nostr
      flagged = 0
      while (match(s, /[0-9]+\.[0-9]+/)) {
        tok = substr(s, RSTART, RLENGTH); s = substr(s, RSTART + RLENGTH)
        if (tok != "0.0" && tok != "0.5" && tok != "1.0" && tok != "2.0") { flagged = 1; break }
      }
      if (flagged) { print FILENAME ":" FNR ": " $0; next }
      # Integers >= 100 (drop hex/binary and floats from the copy first).
      t = nostr
      gsub(/0[xX][0-9a-fA-F]+/, "", t)
      gsub(/0[bB][01]+/, "", t)
      gsub(/[0-9]+\.[0-9]+/, "", t)
      if (t ~ /(^|[^0-9a-zA-Z_.])[1-9][0-9][0-9]/) { print FILENAME ":" FNR ": " $0 }
    }
  ' "$f")"
  cnt=0
  if [ -n "$out" ]; then
    all_out+="$out"$'\n'
    cnt=$(printf '%s\n' "$out" | grep -c .)
    hits=$((hits + cnt))
  fi
  counts+="${f#./}"$'\t'"$cnt"$'\n'
done

# --record-baseline: write the snapshot (nonzero counts only, sorted). The ratchet only
# tightens: refuse to record any per-file count above the committed one.
if [ "$record" = 1 ]; then
  if [ -f "$baseline" ]; then
    # (baseline loaded via getline, not NR==FNR — an EMPTY committed baseline must not make
    # awk mistake the first stdin line for a baseline row)
    regress="$(printf '%s' "$counts" | awk -F'\t' -v bl="$baseline" '
      BEGIN { while ((getline l < bl) > 0) { n = index(l, "\t"); old[substr(l, 1, n - 1)] = substr(l, n + 1) + 0 } }
      NF && $2 + 0 > (($1 in old) ? old[$1] : 0) { print "  " $1 ": " (($1 in old) ? old[$1] : 0) " -> " $2 }
    ')"
    if [ -n "$regress" ]; then
      echo "guardrails/no-hardcoded: refusing --record-baseline — count(s) grew past the committed baseline:" >&2
      printf '%s\n' "$regress" >&2
      echo "  Fix the new bare values (wrap in const_tunable!/config!), then re-record." >&2
      echo "  Renamed a file with known debt? The ratchet compares by path — move its row in $baseline to the new path, then re-record." >&2
      exit 1
    fi
  fi
  printf '%s' "$counts" | awk -F'\t' '$2 + 0 > 0' | LC_ALL=C sort > "$baseline"
  echo "guardrails/no-hardcoded: baseline recorded → $baseline ($(grep -c . "$baseline" 2>/dev/null || echo 0) file(s) with debt). Commit it." >&2
  exit 0
fi

# Ratchet mode: a committed baseline splits the verdict per file (growth gates, burn-down
# nudges re-record, at-baseline stays silent — that's the adoption story).
if [ -f "$baseline" ]; then
  over="$(printf '%s' "$counts" | awk -F'\t' -v bl="$baseline" '
    BEGIN { while ((getline l < bl) > 0) { n = index(l, "\t"); old[substr(l, 1, n - 1)] = substr(l, n + 1) + 0 } }
    NF && $2 + 0 > (($1 in old) ? old[$1] : 0) { print $1 }
  ')"
  under="$(printf '%s' "$counts" | awk -F'\t' -v bl="$baseline" '
    BEGIN { while ((getline l < bl) > 0) { n = index(l, "\t"); old[substr(l, 1, n - 1)] = substr(l, n + 1) + 0 } }
    NF && ($1 in old) && $2 + 0 < old[$1] { print $1 }
  ')"
  if [ -n "$over" ]; then
    printf '%s' "$all_out" | awk -F: -v overlist="$over" '
      BEGIN { n = split(overlist, a, "\n"); for (i = 1; i <= n; i++) ov[a[i]] = 1 }
      { p = $1; sub(/^\.\//, "", p) }   # counts/baseline keys are ./-normalized; hit lines are raw
      ov[p]'
    echo "guardrails/no-hardcoded: $(printf '%s\n' "$over" | grep -c .) file(s) grew past the committed baseline ($baseline) — new bare values are gated. Wrap in const_tunable!/config!, or annotate 'guardrails-ok'." >&2
    exit 1
  fi
  if [ -n "$under" ]; then
    echo "guardrails/no-hardcoded: NUDGE — $(printf '%s\n' "$under" | grep -c .) file(s) burned below the baseline. Bank the win: guardrails-no-hardcoded --record-baseline (then commit $baseline)." >&2
  fi
  exit 0
fi

if [ "$hits" -gt 0 ]; then
  printf '%s' "$all_out"
  echo "guardrails/no-hardcoded: $hits bare value(s) — wrap in const_tunable!/config! (→ TUNABLES.md), or annotate 'guardrails-ok'." >&2
  exit 1
fi
