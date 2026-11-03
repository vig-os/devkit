"""Medium document query benchmark: 20 entries, 400 figures and 400 tables."""

import argparse
import json
import os
import tempfile
import time
from pathlib import Path

from vig_utils import typst_guard

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--unrelated-files", type=int, default=30000)
args = parser.parse_args()

with tempfile.TemporaryDirectory(prefix="typst-content-benchmark-") as directory:
    os.chdir(directory)
    Path("chart.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" '
        'viewBox="0 0 100 50"><text x="1" y="20" font-size="10">Chart</text></svg>'
    )
    for i in range(20):
        Path(f"document-{i:02}.typ").write_text(
            "// devkit: entry\n"
            + (
                '#figure(image("chart.svg", width: 100pt), caption: [Chart])\n'
                "#table(columns: 2, table.header([Name], [Value]), [Example], [42])\n"
                + "A medium document paragraph with representative body text.\n"
                * 10
            )
            * 20
        )
    Path("unrelated").mkdir()
    for i in range(args.unrelated_files):
        Path(f"unrelated/file-{i:05}.dat").touch()
    print(f"Prepared 20 entries and {args.unrelated_files} unrelated files", flush=True)
    start = time.perf_counter()
    code = typst_guard.main(["content"])
    print(
        json.dumps(
            {
                "entries": 20,
                "unrelated_files": args.unrelated_files,
                "figures": 400,
                "tables": 400,
                "compiles": 20,
                "queries": 20,
                "compiler_jobs": 2,
                "seconds": round(time.perf_counter() - start, 3),
                "exit": code,
            }
        )
    )
    assert code == 0
