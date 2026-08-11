"""Tests for the retry CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from vig_utils import retry

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_retry_happy_path_succeeds_first_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls["count"] += 1
        return subprocess.CompletedProcess(args=["true"], returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    rc = retry.retry_command(["true"], retries=3, backoff=1, max_backoff=2)
    assert rc == 0
    assert calls["count"] == 1


def test_retry_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}
    sleep_calls: list[int] = []

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return subprocess.CompletedProcess(args=["cmd"], returncode=42)
        return subprocess.CompletedProcess(args=["cmd"], returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(retry.time, "sleep", sleep_calls.append)

    rc = retry.retry_command(["cmd"], retries=4, backoff=2, max_backoff=10)

    assert rc == 0
    assert attempts["count"] == 3
    assert sleep_calls == [2, 4]


def test_retry_exhausts_attempts_and_returns_last_exit_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sleep_calls: list[int] = []

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["cmd"], returncode=17)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(retry.time, "sleep", sleep_calls.append)

    rc = retry.retry_command(["cmd"], retries=3, backoff=1, max_backoff=5)
    captured = capsys.readouterr()

    assert rc == 17
    assert sleep_calls == [1, 2]
    assert "Command failed after 3/3 attempts (exit: 17)" in captured.err


@pytest.mark.parametrize(
    "argv",
    [
        ["--retries", "3", "--backoff", "1", "--max-backoff", "1", "--"],
        ["--retries", "0", "--backoff", "1", "--max-backoff", "1", "--", "true"],
        ["--retries", "3", "--backoff", "nope", "--max-backoff", "1", "--", "true"],
    ],
)
def test_retry_input_validation_returns_exit_2(
    monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["retry", *argv])
    rc = retry.main()
    assert rc == 2


def test_retry_caps_backoff_with_max_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_calls: list[int] = []

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["cmd"], returncode=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(retry.time, "sleep", sleep_calls.append)

    rc = retry.retry_command(["cmd"], retries=4, backoff=5, max_backoff=6)

    assert rc == 1
    assert sleep_calls == [5, 6, 6]


def test_retry_cli_module_invocation_succeeds() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vig_utils.retry",
            "--retries",
            "2",
            "--backoff",
            "1",
            "--max-backoff",
            "1",
            "--",
            "true",
        ],
        text=True,
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr


def test_retry_handles_command_execution_oserror(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sleep_calls: list[int] = []

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(2, "No such file or directory", "missing-cmd")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(retry.time, "sleep", sleep_calls.append)

    rc = retry.retry_command(
        ["missing-cmd", "--flag"], retries=3, backoff=1, max_backoff=5
    )
    captured = capsys.readouterr()

    assert rc == 127
    assert sleep_calls == []
    assert "retry: failed to execute command: missing-cmd --flag" in captured.err
