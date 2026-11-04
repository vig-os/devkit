"""Medium document query benchmark: 20 entries, 400 figures and 400 tables."""

import argparse
import json
import os
import tempfile
import time
from collections import Counter
from pathlib import Path

from vig_utils import typst_content, typst_guard

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--unrelated-files", type=int, default=30000)
parser.add_argument("--entries", type=int, default=20)
parser.add_argument("--figures-per-entry", type=int, default=20)
args = parser.parse_args()

with tempfile.TemporaryDirectory(prefix="typst-content-benchmark-") as directory:
    os.chdir(directory)
    Path("chart.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" '
        'viewBox="0 0 100 50"><text x="1" y="20" font-size="10">Chart</text></svg>'
    )
    for i in range(args.entries):
        Path(f"document-{i:02}.typ").write_text(
            "// devkit: entry\n"
            + (
                '#figure(image("chart.svg", width: 100pt), caption: [Chart])\n'
                "#table(columns: 2, table.header([Name], [Value]), [Example], [42])\n"
                + "A medium document paragraph with representative body text.\n"
                * 10
            )
            * args.figures_per_entry
        )
    Path("unrelated").mkdir()
    for i in range(args.unrelated_files):
        Path(f"unrelated/file-{i:05}.dat").touch()
    print(
        f"Prepared {args.entries} entries and {args.unrelated_files} unrelated files",
        flush=True,
    )
    commands = Counter()
    original = typst_content.run_typst

    def count(command, *positional, **keywords):
        commands[command[0]] += 1
        return original(command, *positional, **keywords)

    typst_content.run_typst = count
    start = time.perf_counter()
    code = typst_guard.main(["content"])
    print(
        json.dumps(
            {
                "entries": args.entries,
                "unrelated_files": args.unrelated_files,
                "figures": args.entries * args.figures_per_entry,
                "tables": args.entries * args.figures_per_entry,
                "compiles": commands["compile"],
                "queries": commands["query"],
                "compiler_jobs": 2,
                "seconds": round(time.perf_counter() - start, 3),
                "exit": code,
            }
        )
    )
    assert code == 0
