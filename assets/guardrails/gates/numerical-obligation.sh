#!/usr/bin/env bash
# guardrails: numerical-obligation — assert measured numerical values stay within their
# checked-in baseline (a high-water-mark ratchet, not a fixed budget like perf-budget).
#
# Use it for any numerical quality contract: physics parity errors, HARD-count audits,
# coverage %, dead-code %, binary-size, dependency count. Wherever you'd hand-write a
# "current = X; if (new > X) fail; if (new < X) bump X" script, this gate is the shared
# implementation — with the same TOML/JSON shape across repos.
#
# Distinct from perf-budget:
#   * baseline = high-water mark (the best we've seen), not a fixed ceiling
#   * `--update` ratchets the baseline IN THE IMPROVEMENT DIRECTION (never widens slack)
#   * default tolerance is 0 (strict); perf-budget defaults to 20% for measurement noise
#
# Usage:
#   guardrails-numerical-obligation                                # --check, default config
#   guardrails-numerical-obligation [numerical-obligation.toml]    # --check, explicit config
#   guardrails-numerical-obligation --update [config.toml]         # ratchet baselines on improvement
#   guardrails-numerical-obligation --list   [config.toml]         # show what's wired
#
# numerical-obligation.toml:
#   default_direction = "lower"    # lower-is-better (default); "higher" for throughput-style
#   default_tolerance = 0.0        # fractional headroom before regression fires (e.g. 0.05 = 5%)
#   default_mode      = "gate"     # gate | nudge
#
#   [set."audit-hard-counts"]
#   baseline    = "tools/parity/audit-baseline.json"          # canonical, version-controlled
#   measurement = "tmp/audit-current.json"                    # transient, written by your measurer
#   # direction/tolerance/mode override per set
#   # ratchet = true                                          # default true (--update writes back)
#
#   [set."parity-matrix"]
#   baseline    = "tools/parity/parity-matrix-baseline.json"
#   measurement = "${GUARDRAILS_NUMOB_PARITY:-tmp/parity-current.json}"
#   tolerance   = 0.05
#
# Both JSON files must share the same nested structure. The gate walks every numeric leaf
# (int / float, but not bool) and compares paths that exist in both files. Per-path
# overrides (per-key direction/mode/tolerance) are not in v1 — split into multiple sets
# instead.
#
# Missing measurement file = soft-skip with warning (your measurer hasn't run yet — the
# gate doesn't itself measure anything). Missing baseline = hard error (commit the
# baseline before wiring the gate).
set -uo pipefail

MODE=check
CONFIG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --check)  MODE=check; shift ;;
    --update) MODE=update; shift ;;
    --list)   MODE=list; shift ;;
    -h|--help)
      sed -n '2,40p' "$0"; exit 0 ;;
    --) shift; break ;;
    -*) echo "guardrails/numerical-obligation: unknown flag: $1" >&2; exit 2 ;;
    *)  CONFIG="$1"; shift ;;
  esac
done
CONFIG="${CONFIG:-numerical-obligation.toml}"

if [ ! -f "$CONFIG" ]; then
  echo "guardrails/numerical-obligation: no $CONFIG — skipping (add one to enable)." >&2
  exit 0
fi

exec python3 - "$CONFIG" "$MODE" <<'PY'
import json
import os
import pathlib
import sys

try:
    import tomllib
except ModuleNotFoundError:
    sys.stderr.write("guardrails/numerical-obligation: needs python>=3.11 (tomllib).\n")
    sys.exit(0)

config_path = pathlib.Path(sys.argv[1])
mode = sys.argv[2]
spec = tomllib.loads(config_path.read_text())

default_dir = spec.get("default_direction", "lower")
default_tol = float(spec.get("default_tolerance", 0.0))
default_mode = spec.get("default_mode", "gate")

sets = spec.get("set", {})
if not sets:
    sys.stderr.write(f"guardrails/numerical-obligation: no [set.*] entries in {config_path}\n")
    sys.exit(0)


def walk_numeric(obj, path=()):
    """Yield (path-tuple, float) for every numeric leaf in a JSON object. Path is
    a tuple of (key, ...) where each key is the raw dict key or list index — never
    a joined string, so dict keys containing '.' (energy bins like '0.1–1') stay
    unambiguous."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_numeric(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_numeric(v, path + (i,))
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, (int, float)):
        yield path, float(obj)


def fmt_path(path):
    """Render a path-tuple for human-readable output. Uses '/' so dotted dict keys
    stay legible (e.g. 'columns/Reaction/0.1–1' not 'columns.Reaction.0.1–1')."""
    return "/".join(str(p) for p in path)


def set_by_path(obj, path, value):
    """Mutate `obj` so the leaf at `path` (tuple) is `value`. Preserves int-ness
    when possible."""
    cur = obj
    for p in path[:-1]:
        cur = cur[p]
    last = path[-1]
    if isinstance(cur[last], int) and value.is_integer():
        cur[last] = int(value)
    else:
        cur[last] = value


def expand_env(s):
    """Tiny ${VAR:-default} expander so config can defer paths to env."""
    if not isinstance(s, str):
        return s
    out = ""
    i = 0
    while i < len(s):
        if s[i : i + 2] == "${" and "}" in s[i:]:
            j = s.index("}", i)
            inner = s[i + 2 : j]
            if ":-" in inner:
                name, dflt = inner.split(":-", 1)
            else:
                name, dflt = inner, ""
            out += os.environ.get(name, dflt)
            i = j + 1
        else:
            out += s[i]
            i += 1
    return out


all_failures = []
all_warnings = []
all_ok = 0
updated_sets = []

if mode == "list":
    print(f"# {config_path}: {len(sets)} obligation set(s)")
    for name, cfg in sets.items():
        print(
            f"  set.{name}: baseline={cfg.get('baseline')} measurement={cfg.get('measurement')} "
            f"direction={cfg.get('direction', default_dir)} "
            f"tolerance={cfg.get('tolerance', default_tol)} "
            f"mode={cfg.get('mode', default_mode)} "
            f"ratchet={cfg.get('ratchet', True)}"
        )
    sys.exit(0)

for name, cfg in sets.items():
    base_path = pathlib.Path(expand_env(cfg.get("baseline", "")))
    meas_path = pathlib.Path(expand_env(cfg.get("measurement", "")))
    direction = cfg.get("direction", default_dir)
    tol = float(cfg.get("tolerance", default_tol))
    set_mode = cfg.get("mode", default_mode)
    ratchet = bool(cfg.get("ratchet", True))

    if not base_path.is_file():
        sys.stderr.write(
            f"  ERROR set.{name}: baseline not found at {base_path} "
            f"(commit the baseline before wiring the gate)\n"
        )
        all_failures.append(f"set.{name}: missing baseline {base_path}")
        continue
    if not meas_path.is_file():
        sys.stderr.write(
            f"  warn  set.{name}: no measurement at {meas_path} "
            f"— skipping (run the measurer to gate this set)\n"
        )
        continue

    try:
        baseline = json.loads(base_path.read_text())
        measurement = json.loads(meas_path.read_text())
    except json.JSONDecodeError as e:
        sys.stderr.write(f"  ERROR set.{name}: JSON parse failed: {e}\n")
        all_failures.append(f"set.{name}: JSON parse failed")
        continue

    base_leaves = dict(walk_numeric(baseline))
    meas_leaves = dict(walk_numeric(measurement))

    common = set(base_leaves) & set(meas_leaves)
    only_base = set(base_leaves) - set(meas_leaves)
    only_meas = set(meas_leaves) - set(base_leaves)

    set_failures = []
    set_warnings = []
    set_ok = 0
    set_improved = []

    for k in sorted(common):
        b, m = base_leaves[k], meas_leaves[k]
        if direction == "higher":
            limit = b * (1 - tol)
            regressed = m < limit
            improved = m > b
            label = f"measured {m:g} vs floor {b:g}"
        else:
            limit = b * (1 + tol)
            regressed = m > limit
            improved = m < b
            label = f"measured {m:g} vs baseline {b:g}"

        if regressed:
            line = f"set.{name}/{fmt_path(k)}: {label}, tolerance ±{tol*100:.1f}%"
            (set_failures if set_mode == "gate" else set_warnings).append(line)
        else:
            set_ok += 1
            if improved and ratchet:
                set_improved.append((k, m))

    for k in sorted(only_base):
        set_warnings.append(
            f"set.{name}/{fmt_path(k)}: in baseline but not measured — measurer dropped a key?"
        )
    for k in sorted(only_meas):
        set_warnings.append(
            f"set.{name}/{fmt_path(k)}: new in measurement, no baseline entry — run --update to absorb"
        )

    print(
        f"set.{name}: ok={set_ok} regressed={len(set_failures)} "
        f"warn={len(set_warnings)} improvements={len(set_improved)} "
        f"(direction={direction} tol={tol} mode={set_mode} ratchet={ratchet})"
    )

    if mode == "update" and ratchet and set_improved:
        for k, m in set_improved:
            set_by_path(baseline, k, m)
        base_path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
        updated_sets.append((name, base_path, len(set_improved)))

    all_failures.extend(set_failures)
    all_warnings.extend(set_warnings)
    all_ok += set_ok

for m in all_warnings:
    sys.stderr.write(f"  warn  {m}\n")
for m in all_failures:
    sys.stderr.write(f"  FAIL  {m}\n")

if mode == "update":
    for name, path, n in updated_sets:
        print(f"  updated set.{name}: ratcheted {n} improved key(s) into {path}")
    if not updated_sets:
        print("  no improvements to absorb")

if all_failures and mode == "check":
    sys.stderr.write(
        f"guardrails/numerical-obligation: {len(all_failures)} regression(s) beyond baseline.\n"
        "  Either improve the measurement, or after intentional regression update the\n"
        "  baseline by hand with a recorded reason (this gate refuses to widen slack on --update).\n"
    )
    sys.exit(1)
PY
