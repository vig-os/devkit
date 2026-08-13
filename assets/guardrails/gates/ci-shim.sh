#!/usr/bin/env bash
# guardrails: CI is a shim over a local-runnable check.
# A workflow that runs project logic but never invokes a nix check
# (`nix flake check` / `nix build` / `nix develop` / `nix run`) is drift: that
# logic cannot be run locally and re-derives the build in YAML. Nudge toward the
# shim pattern (see docs/CONVENTIONS.md "CI = a shim over a local-runnable check").
#
# NUDGE by default (warn, exit 0) — a hard gate here would false-positive on
# every not-yet-migrated repo and train `--no-verify`. Promote to a hard gate
# per-repo with GUARDRAILS_CI_SHIM_ENFORCE=1.
#
# Allowlist (legit host-bound workflows — browser e2e, platform/macOS/Windows
# bundling, release, GPU/perf): annotate the file with a `guardrails-ok` line,
# or bulk-allow via GUARDRAILS_CI_SHIM_ALLOW (space/colon-separated path globs).
set -uo pipefail
roots=("${@:-.}")
enforce="${GUARDRAILS_CI_SHIM_ENFORCE:-}"
allow="${GUARDRAILS_CI_SHIM_ALLOW:-}"
hits=0

files() {
  for p in "$@"; do
    if [ -d "$p" ]; then git -C "$p" ls-files 2>/dev/null | sed "s#^#${p%/}/#" || find "$p" -type f
    elif [ -f "$p" ]; then echo "$p"; fi
  done
}

allowed() { # path matches a GUARDRAILS_CI_SHIM_ALLOW glob?
  local f="$1" g
  for g in ${allow//:/ }; do
    # shellcheck disable=SC2254
    case "$f" in $g) return 0 ;; esac
  done
  return 1
}

while IFS= read -r f; do
  case "$f" in
    .github/workflows/*.yml | .github/workflows/*.yaml) ;;
    */.github/workflows/*.yml | */.github/workflows/*.yaml) ;;
    *) continue ;;
  esac
  [ -f "$f" ] || continue
  grep -q 'guardrails-ok' "$f" && continue                       # per-file allowlist (standard escape)
  allowed "$f" && continue                                       # bulk allowlist glob
  grep -qE '^[[:space:]]*(-[[:space:]]+)?run:' "$f" || continue   # no inline logic (matches `run:` and `- run:`) → nothing to shim
  grep -qE 'nix (flake check|build|develop|run)' "$f" && continue # invokes a nix check → it's a shim
  printf '  %s — has `run:` logic but no `nix flake check`\n' "$f"
  hits=$((hits + 1))
done < <(files "${roots[@]}")

[ "$hits" -gt 0 ] || exit 0

msg="guardrails/ci-shim: $hits workflow(s) run logic without a nix check. CI should be a shim over \`nix flake check\` (run-local + CI, one definition — see CONVENTIONS.md). Host-bound jobs (e2e/platform/release) are legit: annotate the file \`guardrails-ok\` or set GUARDRAILS_CI_SHIM_ALLOW."
if [ -n "$enforce" ]; then
  echo "$msg" >&2
  exit 1
fi
echo "nudge: $msg" >&2
exit 0
