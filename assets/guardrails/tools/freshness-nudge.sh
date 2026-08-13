#!/usr/bin/env bash
# guardrails-freshness-nudge — the once/week, one-line drift reminder at PUSH time.
#
# Reads ONLY the cache that guardrails-freshness-refresh writes — no network, no `nix`, never
# blocks the push. Injected near the top of the pre-push git hook by the guardrails devShell
# (before prek's `exec`, after the toolbelt is on PATH). Prints a single line to stderr iff
# inputs are drifting, at most once per week per repo. ALWAYS exits 0 (never fails a push), and
# never reads stdin (pre-push's ref list must reach prek intact).
#
# Knob: GUARDRAILS_FRESHNESS_NAG_MIN (default 10080 = 1 week) — min gap between nudges.
set -uo pipefail

top="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cache="${XDG_CACHE_HOME:-$HOME/.cache}/guardrails"
key="$(printf '%s' "$top" | tr -c 'A-Za-z0-9.' '_')"
data="$cache/$key.json"
nag="$cache/$key.nag"
[ -f "$data" ] || exit 0 # no cache yet (refresh hasn't run) → stay silent

nag_min="${GUARDRAILS_FRESHNESS_NAG_MIN:-10080}"
# Throttle: nudged within the window → stay quiet (don't touch the stamp, so drift still surfaces later).
if [ -f "$nag" ] && [ -z "$(find "$nag" -mmin "+$nag_min" 2>/dev/null)" ]; then
  exit 0
fi

# Summarize the cache into one line; empty unless something is actually drifting.
line="$(python3 - "$data" <<'PY' 2>/dev/null
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
stale = [r for r in d.get("inputs", []) if r.get("stale")]
if not stale:
    sys.exit(0)

def tag(r):
    name = r.get("input", "?")
    if r.get("behind") is True:
        return f"{name}←upstream"
    a = r.get("age_days")
    return f"{name} {a}d" if a is not None else name

shown = ", ".join(tag(r) for r in stale[:4]) + (" …" if len(stale) > 4 else "")
print(f"⟳ pins drifting: {shown}  — `guardrails freshness` when ready")
PY
)"

if [ -n "$line" ]; then
  printf '%s\n' "$line" >&2
  mkdir -p "$cache" 2>/dev/null && touch "$nag"
fi
exit 0
