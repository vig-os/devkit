#!/usr/bin/env bash
# guardrails-stale-nudge — the once/week delivery wrapper around guardrails-stale (issue #13),
# riding the SAME post-push slot and throttle discipline as the freshness nudge (#20): one
# line at a moment you're already deciding about this repo, never per-event, never blocking.
# Injected into the pre-push hook by the devShell; reads no stdin; ALWAYS exits 0.
#
# Knob: GUARDRAILS_STALE_NAG_MIN (default 10080 = 1 week) — min gap between nudges.
set -uo pipefail

top="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
[ -f "$top/guardrails-stale.toml" ] || exit 0 # opt-in: no config, no nudge
cache="${XDG_CACHE_HOME:-$HOME/.cache}/guardrails"
key="$(printf '%s' "$top" | tr -c 'A-Za-z0-9.' '_')"
nag="$cache/$key.stale-nag"

nag_min="${GUARDRAILS_STALE_NAG_MIN:-10080}"
case "$nag_min" in ''|*[!0-9]*) nag_min=10080 ;; esac # garbage knob → default, not silence-forever
if [ -f "$nag" ] && [ -z "$(find "$nag" -mmin "+$nag_min" 2>/dev/null)" ]; then
  exit 0 # nudged recently — quiet (stamp untouched, so staleness still surfaces later)
fi

line="$(guardrails-stale 2>&1 >/dev/null || true)"
[ -n "$line" ] || exit 0
printf '%s\n' "$line" >&2
mkdir -p "$cache" 2>/dev/null && touch "$nag" 2>/dev/null || true
exit 0
