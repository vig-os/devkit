"""Tests for vig_utils.check_expirations."""

from __future__ import annotations

import sys
from datetime import date
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from vig_utils.check_expirations import (
    EXPIRATION_PATTERN,
    check_file,
    main,
    parse_entries,
)


class TestExpirationPattern:
    def test_valid_expiration(self):
        match = EXPIRATION_PATTERN.match("Expiration: 2026-12-01")
        assert match
        assert match.group(1) == "2026-12-01"


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
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        path = tmp_path / "ignore.txt"
        path.write_text(
            "Expiration: 2099-01-01\nCVE-2010-4756\n",
            encoding="utf-8",
        )
        orig_argv = sys.argv
        try:
            sys.argv = ["check-expirations", str(path)]
            exit_code = main(today=date(2026, 6, 9))
        finally:
            sys.argv = orig_argv
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Validated 1 exception(s)" in captured.out

    def test_main_fails_for_expired_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        path = tmp_path / "ignore.txt"
        path.write_text(
            "Expiration: 2020-01-01\nCVE-2010-4756\n",
            encoding="utf-8",
        )
        orig_argv = sys.argv
        try:
            sys.argv = ["check-expirations", str(path)]
            exit_code = main(today=date(2026, 6, 9))
        finally:
            sys.argv = orig_argv
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Expired" in captured.err

    def test_main_missing_file_fails(self, tmp_path: Path):
        path = tmp_path / "missing.txt"
        orig_argv = sys.argv
        try:
            sys.argv = ["check-expirations", str(path)]
            exit_code = main(today=date(2026, 6, 9))
        finally:
            sys.argv = orig_argv
        assert exit_code == 1
