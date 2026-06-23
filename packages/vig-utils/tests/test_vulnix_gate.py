"""Tests for vig_utils.vulnix_gate."""

from __future__ import annotations

import json
import sys
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

from vig_utils.vulnix_gate import (
    blocking_findings,
    excepted_cves,
    main,
)

# A trimmed vulnix --json item (shape confirmed against vulnix 1.12).
HIGH = {
    "pname": "curl",
    "version": "8.14.1",
    "derivation": "/nix/store/x-curl-8.14.1",
    "affected_by": ["CVE-2026-3805", "CVE-2026-3783"],
    "whitelisted": [],
    "cvssv3_basescore": {"CVE-2026-3805": 7.5, "CVE-2026-3783": 5.3},
}
CRITICAL = {
    "pname": "openssl",
    "version": "3.0.0",
    "derivation": "/nix/store/x-openssl",
    "affected_by": ["CVE-2099-0001"],
    "whitelisted": [],
    "cvssv3_basescore": {"CVE-2099-0001": 9.8},
}
UNSCORED = {
    "pname": "crun",
    "version": "1.21",
    "derivation": "/nix/store/x-crun",
    "affected_by": ["CVE-2026-30892"],
    "whitelisted": [],
    "cvssv3_basescore": {},
}
LOW = {
    "pname": "busybox",
    "version": "1.36.1",
    "derivation": "/nix/store/x-busybox",
    "affected_by": ["CVE-2025-46394"],
    "whitelisted": [],
    "cvssv3_basescore": {"CVE-2025-46394": 3.2},
}


class TestExceptedCves:
    def test_non_expired_entries_are_excepted(self, tmp_path: Path):
        path = tmp_path / ".vulnixignore"
        path.write_text(
            "Expiration: 2099-01-01\nCVE-2026-3805\nCVE-2099-0001\n",
            encoding="utf-8",
        )
        assert excepted_cves(path, today=date(2026, 6, 23)) == {
            "CVE-2026-3805",
            "CVE-2099-0001",
        }

    def test_expired_entries_do_not_mask(self, tmp_path: Path):
        # Expiry is enforced separately by check-expirations; an expired
        # exception must NOT silently keep masking a HIGH finding here.
        path = tmp_path / ".vulnixignore"
        path.write_text(
            "Expiration: 2020-01-01\nCVE-2026-3805\n",
            encoding="utf-8",
        )
        assert excepted_cves(path, today=date(2026, 6, 23)) == set()

    def test_empty_register_yields_no_exceptions(self, tmp_path: Path):
        path = tmp_path / ".vulnixignore"
        path.write_text("# only comments\n", encoding="utf-8")
        assert excepted_cves(path, today=date(2026, 6, 23)) == set()


class TestBlockingFindings:
    def test_high_unexcepted_is_blocking(self):
        result = blocking_findings([HIGH], excepted=set())
        cves = {f["cve"] for f in result}
        assert "CVE-2026-3805" in cves
        # the MEDIUM CVE on the same derivation is not blocking
        assert "CVE-2026-3783" not in cves

    def test_critical_is_blocking(self):
        result = blocking_findings([CRITICAL], excepted=set())
        assert {f["cve"] for f in result} == {"CVE-2099-0001"}

    def test_excepted_high_is_not_blocking(self):
        result = blocking_findings([HIGH], excepted={"CVE-2026-3805"})
        assert result == []

    def test_low_and_unscored_are_not_blocking(self):
        # < threshold and unknown-severity CVEs are awareness-only, never gate.
        result = blocking_findings([LOW, UNSCORED], excepted=set())
        assert result == []

    def test_threshold_is_configurable(self):
        result = blocking_findings([LOW], excepted=set(), threshold=3.0)
        assert {f["cve"] for f in result} == {"CVE-2025-46394"}


class TestMain:
    def _write_findings(self, tmp_path: Path, items: list[dict]):
        path = tmp_path / "vulnix.json"
        path.write_text(json.dumps(items), encoding="utf-8")
        return path

    def _run(self, argv: list[str], today: date) -> int:
        orig = sys.argv
        try:
            sys.argv = ["vulnix-gate", *argv]
            return main(today=today)
        finally:
            sys.argv = orig

    def test_passes_when_no_blocking_findings(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        findings = self._write_findings(tmp_path, [LOW, UNSCORED])
        register = tmp_path / ".vulnixignore"
        register.write_text("# none\n", encoding="utf-8")
        code = self._run(
            [str(findings), "--register", str(register)], date(2026, 6, 23)
        )
        assert code == 0
        assert "No unexcepted HIGH/CRITICAL" in capsys.readouterr().out

    def test_fails_on_unexcepted_high(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        findings = self._write_findings(tmp_path, [HIGH])
        register = tmp_path / ".vulnixignore"
        register.write_text("# none\n", encoding="utf-8")
        code = self._run(
            [str(findings), "--register", str(register)], date(2026, 6, 23)
        )
        assert code == 1
        assert "CVE-2026-3805" in capsys.readouterr().err

    def test_passes_when_high_is_excepted(self, tmp_path: Path):
        findings = self._write_findings(tmp_path, [HIGH])
        register = tmp_path / ".vulnixignore"
        register.write_text("Expiration: 2099-01-01\nCVE-2026-3805\n", encoding="utf-8")
        code = self._run(
            [str(findings), "--register", str(register)], date(2026, 6, 23)
        )
        assert code == 0

    def test_missing_findings_file_fails(self, tmp_path: Path):
        register = tmp_path / ".vulnixignore"
        register.write_text("# none\n", encoding="utf-8")
        code = self._run(
            [str(tmp_path / "missing.json"), "--register", str(register)],
            date(2026, 6, 23),
        )
        assert code == 1
