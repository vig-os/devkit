"""Workflow tests: the ci.yml flake-pin lockstep gate.

Issue #1752 / #1756: a direnv consumer that PINS its devkit flake input
(``?ref=X`` or ``/X``) builds its dev shell — hooks, vig-utils — from that pin,
while ``.vig-os`` ``DEVKIT_VERSION`` drives the scaffold. An adoption PR that
moved only ``DEVKIT_VERSION`` wired hooks the old toolchain could not spawn
(tessera#445). ``install.sh`` advances the pin under
``DEVKIT_FLAKE_PIN_ADVANCE=true``; this gate makes the remaining skew loud: a
step of the ``resolve-toolchain`` job fails when a pinned release ref differs
from ``DEVKIT_VERSION``, so every toolchain job is skipped and the summary gate
reports the failure. Floating inputs, non-release pins, bare and devcontainer
modes are never gated.

Refs: #1752, #1756
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import (
    INIT_WORKSPACE,
    WORKFLOWS,
    load_workflow,
    step_by_name,
    steps_of_job,
)

if TYPE_CHECKING:
    from pathlib import Path

# The ci.yml step under test, and the step it must follow.
GATE_STEP = "Check flake pin lockstep"
LANGUAGES_STEP = "Check declared languages"


def _steps() -> list[dict]:
    return steps_of_job(load_workflow(WORKFLOWS / "ci.yml"), "resolve-toolchain")


def _flake(url_line: str) -> str:
    """A consumer flake.nix carrying the doc-comment example and ``url_line``."""
    return (
        "{\n"
        "  inputs = {\n"
        '    #   vigos.url = "github:vig-os/devkit?ref=<tag>";\n'
        f"    {url_line}\n"
        '    nixpkgs.follows = "vigos/nixpkgs";\n'
        "  };\n"
        "}\n"
    )


def _run_gate(
    tmp_path: Path, mode: str, version: str, flake: str | None
) -> tuple[int, str]:
    """Execute the gate step's real bash in a tree carrying ``flake``."""
    step = step_by_name(_steps(), GATE_STEP)
    if flake is not None:
        (tmp_path / "flake.nix").write_text(flake, encoding="utf-8")
    proc = subprocess.run(
        ["bash", "-c", step["run"]],
        cwd=tmp_path,
        env={**os.environ, "MODE": mode, "DEVKIT_VERSION": version},
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout + proc.stderr


# ── ci.yml: the gate's placement and wiring ──────────────────────────────────


def test_resolve_toolchain_checkout_includes_flake_nix() -> None:
    """The sparse checkout must fetch the file the gate parses."""
    checkout = step_by_name(_steps(), "Checkout")
    assert "flake.nix" in checkout["with"]["sparse-checkout"].split()


def test_gate_follows_the_languages_gate() -> None:
    """One early gate in resolve-toolchain, right after the languages gate."""
    names = [str(s.get("name", "")) for s in _steps()]
    assert GATE_STEP in names
    assert names.index(GATE_STEP) == names.index(LANGUAGES_STEP) + 1


def test_gate_is_skipped_on_image_tag_override() -> None:
    """A dispatch that reroutes the image makes image-tag diverge from .vig-os."""
    step = step_by_name(_steps(), GATE_STEP)
    assert step["if"] == "${{ !inputs.image-tag }}"


def test_gate_routes_mode_and_version_through_env() -> None:
    """Resolver outputs reach the shell via env, never inline (zizmor)."""
    step = step_by_name(_steps(), GATE_STEP)
    assert step["env"]["MODE"] == "${{ steps.resolve.outputs.mode }}"
    assert step["env"]["DEVKIT_VERSION"] == "${{ steps.resolve.outputs.image-tag }}"
    assert "${{" not in step["run"]


def test_gate_regex_matches_the_scaffold_warning_regex() -> None:
    """The gate parses pins exactly like init-workspace.sh's lagging-pin WARNING."""
    text = INIT_WORKSPACE.read_text(encoding="utf-8")
    # The lagging-pin WARNING block: from its sync note to the WARNING echo.
    start = text.index("# Byte-identical to the regex in ci.yml")
    block = text[start : text.index("WARNING: scaffold upgraded", start)]
    scaffold = re.findall(r"grep -E '([^']+)'", block)
    gate = re.findall(r"grep -E '([^']+)'", step_by_name(_steps(), GATE_STEP)["run"])
    assert len(scaffold) == 1, scaffold
    assert len(gate) == 1, gate
    assert gate == scaffold


# ── ci.yml: the gate's behavior (executed bash) ──────────────────────────────


@pytest.mark.parametrize(
    "url_line",
    [
        'vigos.url = "github:vig-os/devkit?ref=1.16.0";',
        'devkit.url = "github:vig-os/devkit/1.16.0";',
    ],
    ids=["query-ref", "path-ref"],
)
def test_gate_fails_on_a_lagging_pin(tmp_path: Path, url_line: str) -> None:
    """The failure names the input, the pin, the version, and the knob."""
    rc, output = _run_gate(tmp_path, "direnv", "1.17.0", _flake(url_line))
    assert rc == 1
    assert "::error::" in output
    name = url_line.split(".", 1)[0]
    assert f"'{name}'" in output
    assert "1.16.0" in output
    assert "1.17.0" in output
    assert "DEVKIT_FLAKE_PIN_ADVANCE=true" in output
    assert f"nix flake update {name}" in output


def test_gate_fails_in_both_mode(tmp_path: Path) -> None:
    flake = _flake('vigos.url = "github:vig-os/devkit?ref=1.16.0";')
    rc, output = _run_gate(tmp_path, "both", "1.17.0", flake)
    assert rc == 1
    assert "::error::" in output


@pytest.mark.parametrize(
    ("url_line", "version"),
    [
        ('vigos.url = "github:vig-os/devkit?ref=1.17.0";', "1.17.0"),
        ('vigos.url = "github:vig-os/devkit/1.17.0-rc2";', "1.17.0-rc2"),
    ],
    ids=["release", "rc"],
)
def test_gate_passes_silently_on_an_aligned_pin(
    tmp_path: Path, url_line: str, version: str
) -> None:
    rc, output = _run_gate(tmp_path, "direnv", version, _flake(url_line))
    assert rc == 0
    assert "::error::" not in output
    assert "::warning::" not in output


@pytest.mark.parametrize(
    "flake",
    [
        _flake('vigos.url = "github:vig-os/devkit";'),
        _flake('scitadel.url = "github:vig-os/scitadel";'),
        None,
    ],
    ids=["floating", "doc-comment-only", "no-flake-nix"],
)
def test_gate_passes_without_a_pinned_input(tmp_path: Path, flake: str | None) -> None:
    rc, output = _run_gate(tmp_path, "direnv", "1.17.0", flake)
    assert rc == 0
    assert "::error::" not in output


def test_gate_warns_on_a_non_release_pin(tmp_path: Path) -> None:
    """A branch pin floats in effect: no false positive, but not silent."""
    flake = _flake('vigos.url = "github:vig-os/devkit?ref=main";')
    rc, output = _run_gate(tmp_path, "direnv", "1.17.0", flake)
    assert rc == 0
    assert "::warning::" in output


def test_gate_warns_on_an_empty_version(tmp_path: Path) -> None:
    """direnv resolves no image, so DEVKIT_VERSION may be empty."""
    flake = _flake('vigos.url = "github:vig-os/devkit?ref=1.16.0";')
    rc, output = _run_gate(tmp_path, "direnv", "", flake)
    assert rc == 0
    assert "::warning::" in output


@pytest.mark.parametrize("mode", ["bare", "devcontainer"])
def test_gate_ignores_modes_without_a_flake_shell(tmp_path: Path, mode: str) -> None:
    flake = _flake('vigos.url = "github:vig-os/devkit?ref=1.16.0";')
    rc, output = _run_gate(tmp_path, mode, "1.17.0", flake)
    assert rc == 0
    assert "::error::" not in output
