#!/usr/bin/env bash
# guardrails-stale — stateless "which gates are overdue?" check (issue #13).
#
# The motivating miss: a RUSTSEC advisory sat unnoticed for weeks with ZERO local churn —
# the advisory DB moved on the CALENDAR while Cargo.lock sat still, and cargo-deny only
# wakes when a commit touches the lockfile. So staleness needs two levers:
#   * calendar — days since the gate last ran green (from the #14 trace JSONL),
#   * churn    — files/lines changed since that last green run.
# No daemon, no watcher (#20's lesson: an ambient banner you can't action becomes
# blindness): this is a one-shot primitive; delivery surfaces own their throttle
# (the once/week post-push slot ships as guardrails-stale-nudge; prompt segments and
# agent hooks call `guardrails stale --json` themselves).
#
# Config: guardrails-stale.toml at the repo root (no file → silent, exit 0 — opt-in):
#   [cargo-deny]     max_days = 7      # advisory DBs drift on the calendar
#   [clippy]         max_files = 40    # heavy tier: nudge when churn piles up un-linted
#   [no-fake-impl]   max_lines = 500
# Output: one stderr line naming the overdue gates (exit 0 ALWAYS — a nudge, not a gate).
# --json: per-gate stats to stdout (also without config — consumers bring their own policy).
set -uo pipefail

json=0
[ "${1:-}" = "--json" ] && json=1

top="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
repo="$(basename "$top")"
slug="$repo-$(printf '%s' "$top" | git hash-object --stdin 2>/dev/null | cut -c1-6)"
trace="${XDG_CACHE_HOME:-$HOME/.cache}/guardrails/runs/$slug.jsonl"
cfg="$top/guardrails-stale.toml"

[ -f "$trace" ] || { [ "$json" = 1 ] && echo '{"gates":{},"note":"no trace data — wrap hook entries with guardrails-trace"}'; exit 0; }
if [ "$json" = 0 ] && [ ! -f "$cfg" ]; then exit 0; fi

python3 - "$trace" "$cfg" "$json" <<'PY'
import json, os, subprocess, sys
from datetime import datetime, timezone

trace, cfg_path, want_json = sys.argv[1], sys.argv[2], sys.argv[3] == "1"

try:
    import tomllib
    cfg = tomllib.load(open(cfg_path, "rb")) if cfg_path and os.path.exists(cfg_path) else {}
except Exception:
    cfg = {}

# Last green ts per gate from the trace JSONL (machine-written, fixed keys).
last_green = {}
for line in open(trace, errors="replace"):
    try:
        r = json.loads(line)
    except ValueError:
        continue
    if r.get("verdict") == "pass" and r.get("gate"):
        last_green[r["gate"]] = r.get("ts", "")

def churn_since(ts):
    """Files/lines touched since ts: commits since + the working tree."""
    files, lines = set(), 0
    try:
        out = subprocess.run(["git", "log", f"--since={ts}", "--name-only", "--pretty=format:"],
                             capture_output=True, text=True, timeout=10).stdout
        files |= {f for f in out.splitlines() if f}
        out = subprocess.run(["git", "diff", "HEAD", "--numstat"],
                             capture_output=True, text=True, timeout=10).stdout
        for row in out.splitlines():
            p = row.split("\t")
            if len(p) == 3:
                files.add(p[2])
                lines += (int(p[0]) if p[0].isdigit() else 0) + (int(p[1]) if p[1].isdigit() else 0)
        out = subprocess.run(["git", "log", f"--since={ts}", "--shortstat", "--pretty=format:"],
                             capture_output=True, text=True, timeout=10).stdout
        for row in out.splitlines():
            for tok in row.split(","):
                tok = tok.strip()
                if tok.endswith(("(+)", "(-)")) or "insertion" in tok or "deletion" in tok:
                    n = tok.split(" ")[0]
                    lines += int(n) if n.isdigit() else 0
    except Exception:
        pass
    return len(files), lines

now = datetime.now(timezone.utc)
gates = sorted(set(cfg) | (set(last_green) if want_json else set()))
stats, overdue = {}, []
for g in gates:
    ts = last_green.get(g)
    days = None
    if ts:
        try:
            days = (now - datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).days
        except ValueError:
            pass
    nfiles, nlines = churn_since(ts) if ts else (None, None)
    stats[g] = {"last_green": ts, "days_since_green": days,
                "files_since_green": nfiles, "lines_since_green": nlines}
    rules = cfg.get(g, {}) if isinstance(cfg.get(g, {}), dict) else {}
    for k in rules:
        if k not in ("max_days", "max_files", "max_lines"):
            print(f"guardrails-stale: unknown key '{k}' in [{g}] (want max_days/max_files/max_lines)", file=sys.stderr)
    why = []
    if ts is None and rules:
        why.append("never green")
    if days is not None and "max_days" in rules and days > rules["max_days"]:
        why.append(f"{days}d")
    if nfiles is not None and "max_files" in rules and nfiles > rules["max_files"]:
        why.append(f"{nfiles} files")
    if nlines is not None and "max_lines" in rules and nlines > rules["max_lines"]:
        why.append(f"{nlines} lines")
    if why:
        overdue.append(f"{g} {' + '.join(why)}")
        stats[g]["overdue"] = why

if want_json:
    print(json.dumps({"gates": stats}, sort_keys=True))
if overdue:
    print("⚠ stale: " + " · ".join(overdue) + " — run the gate, or `guardrails last` for the latest verdicts.",
          file=sys.stderr)
PY
exit 0
