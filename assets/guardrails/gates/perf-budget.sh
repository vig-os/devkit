#!/usr/bin/env bash
# guardrails: perf-budget — gate bench regressions against a checked-in budgets file.
#
# Run AFTER your benches. Two result sources, merged:
#   * criterion: target/criterion/<id>/new/estimates.json medians (`cargo criterion`),
#   * bespoke harnesses: a flat JSON map written by YOUR bench (GPU fps ceilings, MB/s throughput —
#     anything criterion can't measure): GUARDRAILS_PERF_RESULTS (default perf-results.json),
#     `{"bench_id": value, ...}` — values in whatever unit the budget uses.
# This gate only COMPARES — fast and deterministic, no measurement here.
#
# Usage: guardrails-perf-budget [perf-budgets.toml] [target/criterion]
#   gate-mode budgets fail the build on regression; nudge-mode only warn. The threshold is a
#   per-budget `tolerance` (fractional headroom; default 0.20 = 20%), matching the
#   "gate big regressions, nudge the rest" methodology in docs/CONVENTIONS.md.
#
# perf-budgets.toml:
#   default_tolerance = 0.20
#   [bench."parser/parse_frame"]   # key = criterion id (its target/criterion/<id> path) or your map key
#   budget_ns = 1500               # `budget` works too (unit-agnostic — fps, MB/s, particles…)
#   mode = "gate"                  # gate | nudge
#   # direction = "higher"         # higher-is-better metrics (throughput/fps/ceiling); default lower
#   # tolerance = 0.10             # optional per-budget override
set -uo pipefail
budgets="${1:-perf-budgets.toml}"
crit_dir="${2:-target/criterion}"

if [ ! -f "$budgets" ]; then
  echo "guardrails/perf-budget: no $budgets — skipping (add one to enable perf gating)." >&2
  exit 0
fi

exec python3 - "$budgets" "$crit_dir" <<'PY'
import json, os, pathlib, sys
try:
    import tomllib
except ModuleNotFoundError:
    sys.stderr.write("guardrails/perf-budget: needs python>=3.11 (tomllib) on PATH.\n")
    sys.exit(0)

budgets_path, crit = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
spec = tomllib.loads(budgets_path.read_text())
default_tol = float(spec.get("default_tolerance", 0.20))
benches = spec.get("bench", {})

# Bespoke-harness results: a flat {"bench_id": value} map (values in the budget's unit).
results = {}
rp = pathlib.Path(os.environ.get("GUARDRAILS_PERF_RESULTS", "perf-results.json"))
if rp.exists():
    try:
        results = {str(k): float(v) for k, v in json.loads(rp.read_text()).items()}
    except (ValueError, AttributeError) as e:
        sys.stderr.write(f"guardrails/perf-budget: unreadable {rp}: {e}\n")

ok, warnings, failures = [], [], []
for bid, cfg in benches.items():
    if "budget_ns" not in cfg and "budget" not in cfg:
        warnings.append(f"{bid}: budget entry has neither budget_ns nor budget — skipped")
        continue
    budget = float(cfg.get("budget_ns", cfg.get("budget")))
    mode = cfg.get("mode", "gate")
    tol = float(cfg.get("tolerance", default_tol))
    higher = cfg.get("direction", "lower") == "higher"
    est = crit / bid / "new" / "estimates.json"
    if est.exists():
        measured = float(json.loads(est.read_text())["median"]["point_estimate"])
    elif bid in results:
        measured = results[bid]
    else:
        warnings.append(f"{bid}: no criterion data at {est} and no entry in {rp} — run the benches first")
        continue
    pct = (measured / budget - 1) * 100
    if higher:
        limit = budget * (1 - tol)
        over = measured < limit
        line = f"{bid}: measured {measured:.0f} vs floor {budget:.0f} ({pct:+.1f}%, -{tol*100:.0f}% allowed, higher=better)"
    else:
        limit = budget * (1 + tol)
        over = measured > limit
        line = f"{bid}: measured {measured:.0f} vs budget {budget:.0f} ({pct:+.1f}%, +{tol*100:.0f}% allowed)"
    if over:
        (failures if mode == "gate" else warnings).append(line)
    else:
        ok.append(line)

for m in ok:
    print(f"  ok    {m}")
for m in warnings:
    sys.stderr.write(f"  warn  {m}\n")
for m in failures:
    sys.stderr.write(f"  FAIL  {m}\n")

if failures:
    sys.stderr.write(
        f"guardrails/perf-budget: {len(failures)} gated regression(s) over budget — "
        "optimize, or raise the budget if the cost is justified and recorded.\n"
    )
    sys.exit(1)
PY
