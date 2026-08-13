#!/usr/bin/env bash
# guardrails-freshness — surface THIS flake's input drift, off the hot path.
#
# Pinning hides staleness: you're reproducible, so you never notice an input aged
# out until something breaks. This is the on-demand "tell me now" (the once/week
# post-push nudge just reads this command's --json cache — never the hot `cd` path).
# Offline by default (lock age from flake.lock); --online adds an upstream behind-
# check via `git ls-remote` (bounded, best-effort, degrades silently when offline).
#
#   guardrails freshness            # human table, offline (lock age)
#   guardrails freshness --online   # also flag inputs whose upstream ref moved
#   guardrails freshness --json     # machine output (g-fleet dashboard + push-nudge cache)
#
# Knob: GUARDRAILS_FRESHNESS_STALE_DAYS (default 30) — the age that counts as "drifting".
set -uo pipefail

stale_days="${GUARDRAILS_FRESHNESS_STALE_DAYS:-30}"
online=0
as_json=0
for a in "$@"; do
  case "$a" in
    --online) online=1 ;;
    --json) as_json=1 ;;
    -h | --help)
      echo "usage: guardrails freshness [--online] [--json]   (env: GUARDRAILS_FRESHNESS_STALE_DAYS)"
      exit 0
      ;;
    *)
      echo "guardrails freshness: unknown arg '$a'" >&2
      exit 2
      ;;
  esac
done

root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
if [ ! -f "$root/flake.lock" ]; then
  if [ "$as_json" = 1 ]; then echo '{"inputs":[],"note":"no flake.lock"}'; else echo "guardrails freshness: no flake.lock in $root"; fi
  exit 0
fi

# nix flake metadata gives each input's locked {rev,lastModified,type,owner/repo/ref}.
meta="$(nix --extra-experimental-features 'nix-command flakes' flake metadata "$root" --json 2>/dev/null)"
if [ -z "$meta" ]; then
  # Degrade silently (offline / nix missing). Keep --json TOTAL: the cache + post-push nudge
  # parse our stdout, so always emit valid JSON in --json mode — never empty.
  if [ "$as_json" = 1 ]; then echo '{"inputs":[],"note":"metadata unavailable (offline?)"}'; else echo "guardrails freshness: nix flake metadata failed (offline?)" >&2; fi
  exit 0
fi

tmp="$(mktemp 2>/dev/null)" || tmp=""
if [ -z "$tmp" ]; then
  if [ "$as_json" = 1 ]; then echo '{"inputs":[],"note":"mktemp unavailable"}'; else echo "guardrails freshness: mktemp failed" >&2; fi
  exit 0
fi
printf '%s' "$meta" >"$tmp"
trap 'rm -f "$tmp"' EXIT

GR_ONLINE="$online" GR_JSON="$as_json" GR_STALE="$stale_days" python3 - "$tmp" <<'PY'
import json, os, subprocess, sys, time

meta = json.load(open(sys.argv[1]))
locks = meta.get("locks", {})
nodes = locks.get("nodes", {})
root = locks.get("root", "root")
direct = nodes.get(root, {}).get("inputs", {})
now = time.time()
online = os.environ["GR_ONLINE"] == "1"
as_json = os.environ["GR_JSON"] == "1"
stale_days = int(os.environ["GR_STALE"])


def remote_moved(locked, original):
    """True/False if the locked ref's upstream tip differs; None if unknown/uncheckable.
    Best-effort + advisory: branch-tracked inputs often record ref=None, so we fall back to the
    input's `original` ref, then HEAD (default branch) — which can over-report. Treat the
    resulting `behind` as a hint, not an authority."""
    t = locked.get("type")
    if t == "github":
        url = f"https://github.com/{locked.get('owner')}/{locked.get('repo')}.git"
    elif t in ("git", "gitlab", "sourcehut"):
        url = locked.get("url", "")
    else:
        return None
    if not url:
        return None
    ref = locked.get("ref") or original.get("ref") or "HEAD"
    try:
        out = subprocess.run(["git", "ls-remote", url, ref],
                             capture_output=True, text=True, timeout=8)
        tip = out.stdout.split()[0] if out.stdout.strip() else ""
        return (tip[:40] != locked.get("rev", "")[:40]) if tip else None
    except Exception:
        return None


rows = []
for name, ref in direct.items():
    key = ref[0] if isinstance(ref, list) else ref          # follows → [node, ...]
    node = nodes.get(key, {})
    locked = node.get("locked", {})
    lm = locked.get("lastModified")
    age = int((now - lm) // 86400) if lm else None
    behind = remote_moved(locked, node.get("original", {})) if online else None
    stale = (age is not None and age >= stale_days) or behind is True
    rows.append({"input": name, "age_days": age, "rev": locked.get("rev", "")[:9],
                 "behind": behind, "stale": stale})

rows.sort(key=lambda r: (r["age_days"] is None, -(r["age_days"] or 0)))

if as_json:
    print(json.dumps({"root": meta.get("resolvedUrl", root), "checked": int(now),
                      "stale_days": stale_days, "inputs": rows}, indent=2))
    sys.exit(0)

if not rows:
    print("guardrails freshness: no direct flake inputs")
    sys.exit(0)

for r in rows:
    age = f"{r['age_days']}d" if r["age_days"] is not None else "?"
    flag = "⟳" if r["stale"] else "·"           # ⟳ drifting · fresh
    note = "  ← upstream moved" if r["behind"] is True else ("  (unchecked)" if (online and r["behind"] is None) else "")
    print(f"  {flag} {r['input']:<18} {age:>5} old   {r['rev']}{note}")

n = sum(1 for r in rows if r["stale"])
if n:
    print(f"\n⟳ {n}/{len(rows)} inputs drifting (≥{stale_days}d or upstream moved) — `nix flake update` when ready")
else:
    print(f"\n✓ all {len(rows)} inputs fresh (<{stale_days}d)")
PY
