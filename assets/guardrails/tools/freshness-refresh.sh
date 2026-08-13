#!/usr/bin/env bash
# guardrails-freshness-refresh — keep the freshness cache warm, OFF the hot path.
#
# Throttled to ≤ once/day per repo; meant to be fire-and-forgotten from the devShell
# shellHook (backgrounded). The pre-push nudge reads ONLY the cache this writes, so the
# push (and `cd`) never touch the network inline. Safe to run on every entry — when the
# cache is fresh it returns immediately (one stat); when stale it refreshes in the
# background it was launched in. Always exits 0-ish; never blocks a shell.
#
# Knob: GUARDRAILS_FRESHNESS_TTL_MIN (default 1440 = 1 day) — max cache age before refresh.
set -uo pipefail

top="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
[ -f "$top/flake.lock" ] || exit 0

cache="${XDG_CACHE_HOME:-$HOME/.cache}/guardrails"
key="$(printf '%s' "$top" | tr -c 'A-Za-z0-9.' '_')" # repo path → stable, path-sanitized filename
stamp="$cache/$key.stamp"
ttl_min="${GUARDRAILS_FRESHNESS_TTL_MIN:-1440}"

# Throttle: if the stamp exists and is younger than the TTL, there's nothing to do.
if [ -f "$stamp" ] && [ -z "$(find "$stamp" -mmin "+$ttl_min" 2>/dev/null)" ]; then
  exit 0
fi

mkdir -p "$cache" 2>/dev/null || exit 0
# Single-refresher lock (atomic mkdir): several devShell entries can fire at TTL expiry, but only
# one may run `git ls-remote` — the losers just exit rather than storm the network. Break a stale
# lock left by a killed refresher (>10min) so freshness can't wedge forever.
lock="$cache/$key.lock"
[ -d "$lock" ] && [ -n "$(find "$lock" -mmin +10 2>/dev/null)" ] && rmdir "$lock" 2>/dev/null
mkdir "$lock" 2>/dev/null || exit 0
trap 'rmdir "$lock" 2>/dev/null || true' EXIT

out="$cache/$key.json"
tmp="$(mktemp "$cache/$key.XXXXXX" 2>/dev/null)" || exit 0 # per-run temp: no shared-tmp clobber
# --online so the nudge can show "upstream moved"; the 8s/input bound lives in guardrails-freshness.
if (cd "$top" && guardrails-freshness --online --json) >"$tmp" 2>/dev/null; then
  mv -f "$tmp" "$out" && touch "$stamp"
else
  rm -f "$tmp"
fi
exit 0
