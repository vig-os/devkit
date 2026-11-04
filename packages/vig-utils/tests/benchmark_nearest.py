"""Benchmark 2,000 distinct candidate names against 300 registered terms."""

import hashlib
import json
import time

from vig_utils import glossary

entries = [{"term": f"Registered Component {i:03}"} for i in range(300)]
nearest = glossary.nearest_matcher(entries)
started = time.perf_counter()
results = [nearest(f"Registered Component {i:04}") for i in range(2000)]
elapsed = time.perf_counter() - started
print(
    json.dumps(
        {
            "names": len(results),
            "terms": len(entries),
            "seconds": round(elapsed, 3),
            "result_sha256": hashlib.sha256(json.dumps(results).encode()).hexdigest(),
        }
    )
)
