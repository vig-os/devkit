"""Tests for vig_utils.check_expirations."""

from __future__ import annotations

import json
import sys
from datetime import date
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from vig_utils.check_expirations import (
    check_file,
    classify_entries,
    main,
    parse_entries,
)


class TestParseEntries:
    def test_single_entry_with_expiration(self, tmp_path: Path):
        path = tmp_path / "allow.txt"
        path.write_text(
            "# comment\nExpiration: 2026-12-01\nGHSA-abcd-1234-efgh\n",
            encoding="utf-8",
        )
        entries = parse_entries(path)
        assert entries == [("GHSA-abcd-1234-efgh", date(2026, 12, 1))]

    def test_shared_expiration_applies_to_multiple_entries(self, tmp_path: Path):
        path = tmp_path / "ignore.txt"
        path.write_text(
            "Expiration: 2026-12-01\nCVE-2010-4756\nCVE-2011-4116\n",
            encoding="utf-8",
        )
        entries = parse_entries(path)
        assert entries == [
            ("CVE-2010-4756", date(2026, 12, 1)),
            ("CVE-2011-4116", date(2026, 12, 1)),
        ]

    def test_per_entry_expiration_blocks(self, tmp_path: Path):
        path = tmp_path / "ignore.txt"
        path.write_text(
            "Expiration: 2026-09-01\n"
            "CVE-2026-42504\n"
            "Expiration: 2026-12-01\n"
            "jwt-token\n",
            encoding="utf-8",
        )
        entries = parse_entries(path)
        assert entries == [
            ("CVE-2026-42504", date(2026, 9, 1)),
            ("jwt-token", date(2026, 12, 1)),
        ]

    def test_missing_expiration_raises(self, tmp_path: Path):
        path = tmp_path / "ignore.txt"
        path.write_text("CVE-2010-4756\n", encoding="utf-8")
        with pytest.raises(ValueError, match="no Expiration directive"):
            parse_entries(path)

    def test_invalid_expiration_date_raises_with_context(self, tmp_path: Path):
        path = tmp_path / "ignore.txt"
        path.write_text("Expiration: 2026-13-45\nCVE-2010-4756\n", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid expiration date"):
            parse_entries(path)

    def test_ignores_comments_and_blank_lines(self, tmp_path: Path):
        path = tmp_path / "ignore.txt"
        path.write_text(
            "\n# header\nExpiration: 2026-12-01\n\n# glibc\nCVE-2010-4756\n",
            encoding="utf-8",
        )
        entries = parse_entries(path)
        assert entries == [("CVE-2010-4756", date(2026, 12, 1))]


class TestCheckFile:
    def test_valid_entries_pass(self, tmp_path: Path):
        path = tmp_path / "ignore.txt"
        path.write_text(
            "Expiration: 2099-01-01\nCVE-2010-4756\n",
            encoding="utf-8",
        )
        errors = check_file(path, today=date(2026, 6, 9))
        assert errors == []

    def test_expired_entry_fails(self, tmp_path: Path):
        path = tmp_path / "ignore.txt"
        path.write_text(
            "Expiration: 2020-01-01\nCVE-2010-4756\n",
            encoding="utf-8",
        )
        errors = check_file(path, today=date(2026, 6, 9))
        assert len(errors) == 1
        assert "CVE-2010-4756" in errors[0]
        assert "expired 2020-01-01" in errors[0]

    def test_expiration_on_review_day_is_valid(self, tmp_path: Path):
        path = tmp_path / "ignore.txt"
        path.write_text(
            "Expiration: 2026-06-09\nCVE-2010-4756\n",
            encoding="utf-8",
        )
        errors = check_file(path, today=date(2026, 6, 9))
        assert errors == []

    def test_multiple_expired_entries_all_reported(self, tmp_path: Path):
        path = tmp_path / "ignore.txt"
        path.write_text(
            "Expiration: 2020-01-01\nCVE-2010-4756\nCVE-2011-4116\n",
            encoding="utf-8",
        )
        errors = check_file(path, today=date(2026, 6, 9))
        assert len(errors) == 2


class TestMainFunction:
    def test_main_passes_for_valid_file(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        path = tmp_path / "ignore.txt"
        path.write_text(
            "Expiration: 2099-01-01\nCVE-2010-4756\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(sys, "argv", ["check-expirations", str(path)])
        exit_code = main(today=date(2026, 6, 9))
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Validated 1 exception(s)" in captured.out

    def test_main_fails_for_expired_file(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        path = tmp_path / "ignore.txt"
        path.write_text(
            "Expiration: 2020-01-01\nCVE-2010-4756\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(sys, "argv", ["check-expirations", str(path)])
        exit_code = main(today=date(2026, 6, 9))
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Expired" in captured.err

    def test_main_missing_file_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        path = tmp_path / "missing.txt"
        monkeypatch.setattr(sys, "argv", ["check-expirations", str(path)])
        exit_code = main(today=date(2026, 6, 9))
        assert exit_code == 1


class TestClassifyEntries:
    """The single classification rule behind --warn-days and --json."""

    ENTRIES = [
        ("CVE-EXPIRED", date(2026, 6, 1)),
        ("CVE-TODAY", date(2026, 6, 9)),
        ("CVE-SOON", date(2026, 6, 16)),
        ("CVE-LATER", date(2026, 6, 17)),
    ]

    def test_without_a_window_only_expired_is_reported(self, tmp_path: Path):
        expired, expiring = classify_entries(
            self.ENTRIES, path=tmp_path / "ignore.txt", today=date(2026, 6, 9)
        )
        assert [record["id"] for record in expired] == ["CVE-EXPIRED"]
        assert expiring == []

    def test_window_is_inclusive_of_its_last_day(self, tmp_path: Path):
        _, expiring = classify_entries(
            self.ENTRIES,
            path=tmp_path / "ignore.txt",
            today=date(2026, 6, 9),
            warn_days=7,
        )
        # CVE-TODAY (0 days) and CVE-SOON (exactly 7 days) are inside the
        # window; CVE-LATER (8 days) is not.
        assert [record["id"] for record in expiring] == ["CVE-TODAY", "CVE-SOON"]

    def test_records_carry_id_file_expiration_and_days_left(self, tmp_path: Path):
        path = tmp_path / "ignore.txt"
        _, expiring = classify_entries(
            self.ENTRIES, path=path, today=date(2026, 6, 9), warn_days=7
        )
        assert expiring[1] == {
            "id": "CVE-SOON",
            "file": str(path),
            "expiration": "2026-06-16",
            "days_left": 7,
        }

    def test_expired_records_carry_a_negative_days_left(self, tmp_path: Path):
        expired, _ = classify_entries(
            self.ENTRIES,
            path=tmp_path / "ignore.txt",
            today=date(2026, 6, 9),
            warn_days=7,
        )
        assert expired[0]["days_left"] == -8

    def test_expired_entries_are_never_also_expiring(self, tmp_path: Path):
        expired, expiring = classify_entries(
            self.ENTRIES,
            path=tmp_path / "ignore.txt",
            today=date(2026, 6, 9),
            warn_days=365,
        )
        assert [record["id"] for record in expired] == ["CVE-EXPIRED"]
        assert "CVE-EXPIRED" not in [record["id"] for record in expiring]


class TestWarnDays:
    """--warn-days annotates upcoming expiries without changing exit codes."""

    def _write(self, tmp_path: Path) -> Path:
        path = tmp_path / "ignore.txt"
        path.write_text(
            "Expiration: 2026-06-16\nCVE-SOON\nExpiration: 2026-07-01\nCVE-LATER\n",
            encoding="utf-8",
        )
        return path

    def test_default_run_emits_no_warning(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        path = self._write(tmp_path)
        monkeypatch.setattr(sys, "argv", ["check-expirations", str(path)])
        exit_code = main(today=date(2026, 6, 9))
        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out == "Validated 2 exception(s) across 1 file(s)\n"
        assert captured.err == ""

    def test_warn_days_annotates_entries_inside_the_window(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        path = self._write(tmp_path)
        monkeypatch.setattr(
            sys, "argv", ["check-expirations", "--warn-days", "7", str(path)]
        )
        exit_code = main(today=date(2026, 6, 9))
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "::warning::" in captured.err
        assert "CVE-SOON" in captured.err
        assert "2026-06-16" in captured.err
        assert "CVE-LATER" not in captured.err
        # The human summary is untouched by the warning window.
        assert captured.out == "Validated 2 exception(s) across 1 file(s)\n"

    def test_warn_days_does_not_rescue_an_expired_entry(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        path = tmp_path / "ignore.txt"
        path.write_text("Expiration: 2020-01-01\nCVE-OLD\n", encoding="utf-8")
        monkeypatch.setattr(
            sys, "argv", ["check-expirations", "--warn-days", "7", str(path)]
        )
        exit_code = main(today=date(2026, 6, 9))
        assert exit_code == 1
        assert "::error::" in capsys.readouterr().err

    def test_nothing_inside_the_window_emits_no_warning(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        path = self._write(tmp_path)
        monkeypatch.setattr(
            sys, "argv", ["check-expirations", "--warn-days", "1", str(path)]
        )
        exit_code = main(today=date(2026, 6, 9))
        assert exit_code == 0
        assert "::warning::" not in capsys.readouterr().err


class TestJsonOutput:
    """--json exposes the classification so a workflow never re-parses."""

    def _write(self, tmp_path: Path) -> Path:
        path = tmp_path / "ignore.txt"
        path.write_text(
            "Expiration: 2020-01-01\nCVE-OLD\nExpiration: 2026-06-16\nCVE-SOON\n",
            encoding="utf-8",
        )
        return path

    def test_json_replaces_the_human_summary_on_stdout(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        path = tmp_path / "ignore.txt"
        path.write_text("Expiration: 2099-01-01\nCVE-FUTURE\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["check-expirations", "--json", str(path)])
        exit_code = main(today=date(2026, 6, 9))
        assert exit_code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload == {"expired": [], "expiring": []}

    def test_json_composes_with_warn_days(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        path = self._write(tmp_path)
        monkeypatch.setattr(
            sys,
            "argv",
            ["check-expirations", "--json", "--warn-days", "7", str(path)],
        )
        exit_code = main(today=date(2026, 6, 9))
        assert exit_code == 1  # the expired entry still fails the run
        payload = json.loads(capsys.readouterr().out)
        assert [record["id"] for record in payload["expired"]] == ["CVE-OLD"]
        assert payload["expiring"] == [
            {
                "id": "CVE-SOON",
                "file": str(path),
                "expiration": "2026-06-16",
                "days_left": 7,
            }
        ]

    def test_json_spans_every_file_given(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        first = tmp_path / "a.txt"
        first.write_text("Expiration: 2026-06-10\nCVE-A\n", encoding="utf-8")
        second = tmp_path / "b.txt"
        second.write_text("Expiration: 2026-06-11\nCVE-B\n", encoding="utf-8")
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check-expirations",
                "--json",
                "--warn-days",
                "7",
                str(first),
                str(second),
            ],
        )
        exit_code = main(today=date(2026, 6, 9))
        assert exit_code == 0
        payload = json.loads(capsys.readouterr().out)
        assert [record["id"] for record in payload["expiring"]] == ["CVE-A", "CVE-B"]
        assert [record["file"] for record in payload["expiring"]] == [
            str(first),
            str(second),
        ]
