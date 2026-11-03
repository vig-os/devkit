"""Reproduce the 300-term candidate benchmark; run directly with uv run python."""

import contextlib
import io
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import yaml
from vig_utils import glossary

with tempfile.TemporaryDirectory(prefix="glossary-benchmark-") as directory:
    root = Path(directory)
    subprocess.run(["git", "init", "-q", directory], check=True)
    entries = [
        {
            "id": f"item-{i}",
            "term": f"Registered Component {i:03}",
            "kind": "component",
            "definition": "Benchmark component.",
        }
        for i in range(300)
    ]
    (root / "glossary.yaml").write_text(yaml.safe_dump(entries))
    names = "ThermalValve PressureSensor ValveController CoolingModule FlowMeter SafetyRelay DrainAssembly SupplyMonitor."
    for i in range(300):
        path = root / f"documents/section-{i // 30:02}/source-{i:03}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((names + "\n") * 50)
    subprocess.run(["git", "-C", directory, "add", "."], check=True)
    os.chdir(root)
    output = io.StringIO()
    started = time.perf_counter()
    with contextlib.redirect_stdout(output):
        code = glossary.main(["candidates"])
    elapsed = time.perf_counter() - started
    rows = [json.loads(line) for line in output.getvalue().splitlines()]
    assert code == 0 and len(rows) == 2400
    print(
        json.dumps(
            {
                "files": 300,
                "lines": 15000,
                "terms": 300,
                "distinct_candidates": 8,
                "rows": len(rows),
                "seconds": round(elapsed, 3),
                "exit": code,
            }
        )
    )
