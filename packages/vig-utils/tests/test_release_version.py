"""Tests for the release-version CLI (pluggable pre-release format, #1746).

``release-version`` computes the bare publish version (``X.Y.Z`` or
``X.Y.Z-<pre-release>``) the release train tags, from a pre-release *format*
string instead of the formerly hard-coded ``-rc{N}`` literal:

- ``{N}`` — optional auto-incremented counter (pinnable with ``--number``)
- ``{YYYYMMDD}`` — UTC date stamp

It also carries the monotonicity gate: a label switch may never produce a
version that sorts BELOW an existing tag of the same ``X.Y.Z``.

Refs: #1746
"""

from __future__ import annotations

import io
import subprocess
import sys

import pytest
from vig_utils import release_version as rv

DATE = "20260928"


def compute(
    version: str = "1.2.3",
    kind: str = "candidate",
    fmt: str = "rc{N}",
    tags: list[str] | None = None,
    prefix: str = "",
    number: str | None = None,
    date: str = DATE,
) -> rv.PublishVersion:
    return rv.compute_publish_version(
        version=version,
        kind=kind,
        fmt=fmt,
        existing_tags=tags or [],
        tag_prefix=prefix,
        number=number,
        date=date,
    )


# ── Backwards compatibility: default `rc{N}` is byte-identical to `-rcN` ─────


def test_default_format_is_rc_n() -> None:
    assert rv.DEFAULT_FORMAT == "rc{N}"


def test_first_candidate_is_rc1() -> None:
    result = compute()
    assert result.publish_version == "1.2.3-rc1"
    assert result.next_n == "1"


def test_candidate_auto_increments_past_highest_rc() -> None:
    tags = ["1.2.3-rc1", "1.2.3-rc2", "1.2.3-rc21", "1.2.3-rc9"]
    result = compute(tags=tags)
    # Counter order, NOT SemVer order: SemVer ranks rc9 above rc21 lexically.
    assert result.publish_version == "1.2.3-rc22"


def test_other_versions_and_prefixes_are_ignored() -> None:
    tags = ["1.2.30-rc7", "1.2.4-rc3", "v1.2.3-rc5", "11.2.3-rc9"]
    assert compute(tags=tags).publish_version == "1.2.3-rc1"


def test_tag_prefix_scopes_discovery() -> None:
    tags = ["v1.2.3-rc4", "1.2.3-rc9"]
    result = compute(tags=tags, prefix="v")
    assert result.publish_version == "1.2.3-rc5"  # publish_version stays bare


def test_explicit_number_pins_counter() -> None:
    result = compute(tags=["1.2.3-rc30"], number="21")
    # Pinning below the max within the SAME format is the cross-repo gate's
    # existing contract (rc-number) and stays allowed.
    assert result.publish_version == "1.2.3-rc21"
    assert result.next_n == "21"


@pytest.mark.parametrize("bad", ["0", "-1", "abc", "1.5", "01"])
def test_explicit_number_must_be_positive_integer(bad: str) -> None:
    with pytest.raises(rv.ReleaseVersionError, match="number"):
        compute(number=bad)


def test_malformed_tag_in_format_namespace_is_refused() -> None:
    with pytest.raises(rv.ReleaseVersionError, match="Malformed"):
        compute(tags=["1.2.3-rcfoo"])


def test_final_publishes_bare_version() -> None:
    result = compute(kind="final", tags=["1.2.3-rc4"])
    assert result.publish_version == "1.2.3"
    assert result.next_n == ""


@pytest.mark.parametrize("kind", ["", "beta", "Final"])
def test_invalid_kind_is_refused(kind: str) -> None:
    with pytest.raises(rv.ReleaseVersionError, match="kind"):
        compute(kind=kind)


@pytest.mark.parametrize("version", ["1.2", "v1.2.3", "1.2.3-rc1", "01.2.3", ""])
def test_invalid_version_is_refused(version: str) -> None:
    with pytest.raises(rv.ReleaseVersionError, match="version"):
        compute(version=version)


@pytest.mark.parametrize(
    "version",
    ["1\uff11.2.3", "1.1\u0662.3", "1.2.1\u09e9"],
    ids=["fullwidth", "arabic", "bengali"],
)
def test_non_ascii_digits_in_version_are_refused(version: str) -> None:
    with pytest.raises(rv.ReleaseVersionError, match="version"):
        compute(version=version)


def test_non_ascii_digits_in_number_are_refused() -> None:
    with pytest.raises(rv.ReleaseVersionError, match="number"):
        compute(number="1\u0662")


def test_non_ascii_digits_in_date_are_refused() -> None:
    with pytest.raises(rv.ReleaseVersionError, match="date"):
        compute(fmt="pre.{YYYYMMDD}", date="\u0662" * 8)


def test_non_ascii_digit_tags_are_not_counted() -> None:
    """A tag spelled with non-ASCII digits is not an instance of the format."""
    with pytest.raises(rv.ReleaseVersionError, match="Malformed"):
        compute(tags=["1.2.3-rc1\u0669"])


# ── Pluggable formats ─────────────────────────────────────────────────────────


def test_dotted_alpha_format() -> None:
    result = compute(version="0.1.0", fmt="alpha.{N}", prefix="v")
    assert result.publish_version == "0.1.0-alpha.1"


def test_dotted_alpha_increments_from_tessera_existing_tag() -> None:
    """tessera is mid-series at v0.1.0-alpha.1 (tessera#441).

    Without the legacy ``v0.1.0`` tag the series simply continues; with it,
    ``test_existing_final_blocks_any_prerelease`` refuses the cut instead.
    """
    tags = ["v0.1.0-alpha.1", "v1.0.0-rc1"]
    result = compute(version="0.1.0", fmt="alpha.{N}", prefix="v", tags=tags)
    assert result.publish_version == "0.1.0-alpha.2"


def test_bare_label_without_counter() -> None:
    result = compute(fmt="alpha")
    assert result.publish_version == "1.2.3-alpha"
    assert result.next_n == ""


def test_date_stamped_format() -> None:
    assert compute(fmt="pre.{YYYYMMDD}").publish_version == "1.2.3-pre.20260928"


def test_date_and_counter_counter_resets_per_day() -> None:
    tags = ["1.2.3-nightly.20260927.4", "1.2.3-nightly.20260928.2"]
    result = compute(fmt="nightly.{YYYYMMDD}.{N}", tags=tags)
    assert result.publish_version == "1.2.3-nightly.20260928.3"


def test_number_with_counterless_format_is_refused() -> None:
    with pytest.raises(rv.ReleaseVersionError, match=r"\{N\}"):
        compute(fmt="alpha", number="2")


@pytest.mark.parametrize(
    "fmt",
    [
        "",
        "rc{M}",  # unknown placeholder
        "rc{N}{N}",  # counter twice
        "a{YYYYMMDD}b{YYYYMMDD}",  # date twice
        "rc_{N}",  # `_` outside the SemVer charset
        "rc {N}",
        ".rc{N}",  # empty leading identifier
        "rc..{N}",  # empty identifier
        "rc.{N}.",  # empty trailing identifier
        "rc.0{N}",  # numeric identifier with a leading zero
        "rc{N",  # unbalanced brace
        "+build",
        "{YYYYMMDD}{N}",  # 202601011 vs 2026010110: numeric order breaks
        "{N}{YYYYMMDD}",
        "rc1{N}",  # rc11 is ambiguous: counter 11, or 1 + 1?
        "rc.2{N}",
    ],
)
def test_invalid_format_is_refused(fmt: str) -> None:
    with pytest.raises(rv.ReleaseVersionError, match="format"):
        compute(fmt=fmt)


def test_format_is_validated_for_final_too() -> None:
    """A broken DEVKIT_PRERELEASE_FORMAT fails loudly on every kind."""
    with pytest.raises(rv.ReleaseVersionError, match="format"):
        compute(kind="final", fmt="rc_{N}")


# ── Monotonicity gate (label switch may not lower the ordering) ───────────────


def test_switch_to_lower_label_is_refused() -> None:
    """1.2.3-rc21 exists; alpha.1 would sort below it (issue example)."""
    with pytest.raises(rv.ReleaseVersionError, match="1.2.3-rc21"):
        compute(fmt="alpha.{N}", tags=["1.2.3-rc21"])


def test_switch_to_higher_label_is_allowed() -> None:
    result = compute(fmt="rc.{N}", tags=["1.2.3-beta.4", "1.2.3-alpha.2"])
    assert result.publish_version == "1.2.3-rc.1"


def test_switch_from_undotted_to_dotted_rc_is_refused() -> None:
    """SemVer ranks `rc` below `rc21` (shorter identifier), so rc.1 < rc21."""
    with pytest.raises(rv.ReleaseVersionError, match="lower"):
        compute(fmt="rc.{N}", tags=["1.2.3-rc21"])


def test_existing_final_warns_but_allows_candidate() -> None:
    """tessera's legacy v0.1.0 tag outranks every 0.1.0 pre-release.

    That is not a label switch, so it must not block: after a failed final run
    the ``X.Y.Z`` tag stays (forward-fix policy) and the documented recovery is
    a NEW candidate of the same version. The hazard is surfaced as a warning.
    """
    tags = ["v0.1.0", "v0.1.0-alpha.1", "v1.0.0-rc1"]
    result = compute(version="0.1.0", fmt="alpha.{N}", prefix="v", tags=tags)
    assert result.publish_version == "0.1.0-alpha.2"
    assert any("v0.1.0" in w for w in result.warnings)


def test_candidate_after_failed_final_is_allowed() -> None:
    """Regression guard for the forward-fix recovery path (rc after X.Y.Z)."""
    result = compute(tags=["1.2.3", "1.2.3-rc4"])
    assert result.publish_version == "1.2.3-rc5"
    assert result.warnings


def test_no_warnings_on_a_clean_series() -> None:
    assert compute(tags=["1.2.3-rc1"]).warnings == ()


def test_legacy_tags_of_other_versions_do_not_interfere() -> None:
    """v1.0.0-rc1 / v0.1.0 belong to other X.Y.Z and are out of scope."""
    tags = ["v0.1.0", "v1.0.0-rc1", "v0.1.0-alpha.1"]
    result = compute(version="0.2.0", fmt="alpha.{N}", prefix="v", tags=tags)
    assert result.publish_version == "0.2.0-alpha.1"


@pytest.mark.parametrize(
    ("fmt", "tags"),
    [
        ("alpha", ["1.2.3-alpha"]),
        ("pre.{YYYYMMDD}", ["1.2.3-pre.20260928"]),
    ],
    ids=["counterless", "dated-same-day"],
)
def test_recomputing_an_existing_tag_is_refused(fmt: str, tags: list[str]) -> None:
    """A counterless format cannot mint a second candidate for the same X.Y.Z.

    Without this, the existing tag was silently recomputed and the run only
    failed late in finalize (or, on the same SHA, passed as a fake retry).
    """
    with pytest.raises(rv.ReleaseVersionError, match="already exists"):
        compute(fmt=fmt, tags=tags)


def test_dated_format_on_a_new_day_is_allowed() -> None:
    assert compute(
        fmt="pre.{YYYYMMDD}", tags=["1.2.3-pre.20260927"]
    ).publish_version == ("1.2.3-pre.20260928")


def test_explicit_number_may_name_an_existing_tag() -> None:
    """The cross-repo gate pins rc-number to an upstream tag (existing contract)."""
    assert compute(tags=["1.2.3-rc21"], number="21").publish_version == "1.2.3-rc21"


def test_final_is_never_lowered_by_prereleases() -> None:
    assert compute(kind="final", tags=["1.2.3-rc9"]).publish_version == "1.2.3"


def test_undotted_rc_series_is_never_refused_by_its_own_tags() -> None:
    """Regression guard: SemVer order of rc9 vs rc10 must not trip the gate."""
    tags = [f"1.2.3-rc{n}" for n in range(1, 12)]
    assert compute(tags=tags).publish_version == "1.2.3-rc12"


# ── SemVer precedence helper ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("lower", "higher"),
    [
        ("1.0.0-alpha", "1.0.0-alpha.1"),
        ("1.0.0-alpha.1", "1.0.0-alpha.beta"),
        ("1.0.0-alpha.beta", "1.0.0-beta"),
        ("1.0.0-beta", "1.0.0-beta.2"),
        ("1.0.0-beta.2", "1.0.0-beta.11"),
        ("1.0.0-beta.11", "1.0.0-rc.1"),
        ("1.0.0-rc.1", "1.0.0"),
        ("1.0.0-rc10", "1.0.0-rc9"),  # lexical — why counters rank by N
    ],
)
def test_semver_precedence(lower: str, higher: str) -> None:
    assert rv.semver_key(lower) < rv.semver_key(higher)


# ── CLI ───────────────────────────────────────────────────────────────────────


def test_main_reads_tags_from_stdin_and_prints_outputs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("v1.2.3-alpha.3\n\nv1.2.3-alpha.1\n"))
    rc = rv.main(
        [
            "--version",
            "1.2.3",
            "--kind",
            "candidate",
            "--format",
            "alpha.{N}",
            "--tag-prefix",
            "v",
            "--date",
            DATE,
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["publish_version=1.2.3-alpha.4", "next_n=4"]


def test_main_defaults_format_when_empty(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty --format (unset input + unset .vig-os key) means rc{N}."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    rc = rv.main(["--version", "1.2.3", "--kind", "candidate", "--format", ""])
    assert rc == 0
    assert "publish_version=1.2.3-rc1" in capsys.readouterr().out


def test_main_prints_warnings_as_annotations(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("1.2.3\n"))
    rc = rv.main(["--version", "1.2.3", "--kind", "candidate", "--format", ""])
    assert rc == 0
    captured = capsys.readouterr()
    assert "publish_version=1.2.3-rc1" in captured.out
    assert captured.err.startswith("::warning::")


def test_main_reports_error_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("1.2.3-rc21\n"))
    rc = rv.main(["--version", "1.2.3", "--kind", "candidate", "--format", "alpha.{N}"])
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ERROR" in captured.err


def test_console_script_is_installed() -> None:
    proc = subprocess.run(
        ["release-version", "--help"], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr
    assert "--format" in proc.stdout
