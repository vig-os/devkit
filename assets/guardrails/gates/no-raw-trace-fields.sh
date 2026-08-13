#!/usr/bin/env bash
# guardrails: no raw Debug/Display field formatters in `tracing` macros — keep the
# structured-log / audit surface DELIBERATE. Flags `?expr` / `%expr` *field* formatters
# (e.g. info!(user = ?user), debug!(%peer), error!(?e)) which splat an arbitrary value's
# Debug/Display into the log — the classic way PII or secrets leak into the audit trail
# by reflex. The one place raw formatting belongs is the schema/redaction surface where
# the shaped fields are DEFINED; allowlist it with GUARDRAILS_TRACE_ALLOW_GLOBS
# (colon-separated path globs; a matched file is skipped wholesale). Rust-only (tracing
# is a Rust crate). tests/examples are exempt. Escape: `guardrails-ok` on the line, or on
# a pure `//` comment line directly above it (stable under rustfmt's comment wrapping).
#
# Detection: a `?`/`%` in *field position* — right after a `(` or `,` field separator, or
# after a `name =` — followed by an identifier start. The delimiter anchor excludes the
# try operator (`foo()?`), modulo (`a % b`), and `=>` match arms. String/char literals are
# blanked first, so regex patterns like r"(?i)…" / "(?P<n>…)" are NOT mistaken for the
# tracing shorthand `info!(?x)` (a real field formatter is Rust code, never inside a string).
set -uo pipefail
roots=("${@:-.}")
hits=0

IFS=: read -ra allow_globs <<< "${GUARDRAILS_TRACE_ALLOW_GLOBS:-}"

# The schema/redaction surface (allowlisted) + the standard built-in exemptions.
allowed_file() {
  # Dir-walks arrive './'-prefixed; normalize so allow-globs without a leading
  # '*' still match (same class as the no-hardcoded src/* normalization).
  set -- "${1#./}"
  case "$1" in *gates/*|tests/*|*/tests/*|*_test.*|*.test.*|examples/*|*/examples/*) return 0 ;; esac
  local g
  for g in "${allow_globs[@]}"; do
    [ -n "$g" ] || continue
    # $g is intentionally a glob pattern, not a literal.
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

# Emit one line per source line with string/char-literal content and // comments blanked,
# so the field-formatter pattern can't match inside a string (regex `(?i)` etc.) or comment.
# Handles "…" (with \" escapes), char '…', and single-line raw strings r"…" / r#"…"#.
# Line count is preserved 1:1 so `grep -n` line numbers map back to the source.
blank_strings() {
  awk '
  {
    s=$0; n=length(s); out=""; i=1
    while (i<=n) {
      c=substr(s,i,1)
      if (c=="/" && substr(s,i+1,1)=="/") break                       # // line comment
      if (c=="r" && (substr(s,i+1,1)=="\"" || substr(s,i+1,1)=="#")) { # raw string r"…"/r#"…"#
        j=i+1; h=0
        while (substr(s,j,1)=="#") { h++; j++ }
        if (substr(s,j,1)=="\"") {
          j++
          while (j<=n) {
            if (substr(s,j,1)=="\"") { k=0; while (substr(s,j+1+k,1)=="#" && k<h) k++; if (k==h) { j=j+1+h; break } }
            j++
          }
          out=out " "; i=j; continue
        }
      }
      if (c=="\"") {                                                   # normal string
        j=i+1
        while (j<=n) { if (substr(s,j,1)=="\\") { j+=2; continue } if (substr(s,j,1)=="\"") { j++; break } j++ }
        out=out " "; i=j; continue
      }
      if (c=="\x27") {                                                 # char literal (lifetimes lack a near closing quote)
        if (substr(s,i+1,1)=="\\" && substr(s,i+3,1)=="\x27") { out=out "  "; i=i+4; continue }
        if (substr(s,i+2,1)=="\x27") { out=out "  "; i=i+3; continue }
      }
      out=out c; i++
    }
    print out
  }' "$1"
}

# Field-formatter in field position: after ( or , (alt 1), or after `name =` but not `=>` (alt 2).
fmt_pat='[(,][[:space:]]*[?%][a-zA-Z_]|[^=>]=[[:space:]]*[?%][a-zA-Z_]'

while IFS= read -r f; do
  case "$f" in *.rs) ;; *) continue ;; esac
  allowed_file "$f" && continue
  while IFS=: read -r no _; do
    orig="$(sed -n "${no}p" "$f")"
    case "$orig" in *guardrails-ok*) continue ;; esac
    # A pure-comment guardrails-ok line directly ABOVE also suppresses: rustfmt wraps
    # over-long trailing comments onto the next line, so same-line markers aren't stable.
    if [ "$no" -gt 1 ]; then
      prev="$(sed -n "$((no - 1))p" "$f" | sed 's/^[[:space:]]*//')"
      case "$prev" in //*guardrails-ok*) continue ;; esac
    fi
    printf '  %s:%s:%s\n' "$f" "$no" "$(printf '%s' "$orig" | sed 's/^[[:space:]]*//')"
    hits=$((hits + 1))
  done < <(blank_strings "$f" | grep -nE "$fmt_pat")
done < <(files "${roots[@]}")

if [ "$hits" -gt 0 ]; then
  echo "guardrails/no-raw-trace-fields: $hits raw Debug/Display field formatter(s) in tracing macros — shape the field in your schema surface (allowlist via GUARDRAILS_TRACE_ALLOW_GLOBS), or annotate 'guardrails-ok'." >&2
  exit 1
fi
