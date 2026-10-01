"""The one test of the consumer-matrix Python fixture (devkit #1762)."""

import os
from pathlib import Path

from hello import greet


def test_greet() -> None:
    assert greet("matrix") == "Hello, matrix!"
    # Proof for the matrix that `just test` really ran this suite.
    sentinel = os.environ.get("CONSUMER_MATRIX_SENTINEL")
    if sentinel:
        Path(sentinel).write_text("python\n", encoding="utf-8")
