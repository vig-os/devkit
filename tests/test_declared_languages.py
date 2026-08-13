"""Scaffold + workflow tests: the declared-language manifest key and CI gate.

Issue #1478: ``just test`` / ``just lint`` are guarded on ``[ -f pyproject.toml ]``
and exit 0 when the marker is absent, so a repo whose whole Python project was
deleted still reported a green ``Tests`` check (live instance: the 1.8.0-rc3
smoke deploy, #1466). Detection alone cannot close that hole — the deploy that
deleted ``pyproject.toml`` also re-ran the scaffold, so a detection *cache* would
have been rewritten to empty in the same commit.

The fix is a STICKY declaration: ``DEVKIT_LANGUAGES`` in ``.vig-os`` is seeded
from detection on scaffold, grows when a new language appears, and is NEVER
narrowed by the scaffold — removing a language is a deliberate hand-edit.
``resolve-toolchain`` re-emits it as the ``languages`` output and ``ci.yml``
fails early when a declared language's marker file is gone.

Refs: #1478, #1466, #1281
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import (
    WORKFLOWS,
    load_workflow,
    run_resolve_toolchain,
    scaffold,
    step_by_name,
    steps_of_job,
)

if TYPE_CHECKING:
    from pathlib import Path

# The manifest key and the resolve-toolchain output that re-exports it.
LANGUAGES_KEY = "DEVKIT_LANGUAGES"
LANGUAGES_OUTPUT = "languages"

# The ci.yml step that gates declared languages on their marker files.
GATE_STEP = "Check declared languages"

# Marker file per gated language (nix is declared but deliberately not gated —
# flake.nix ships with every direnv scaffold, so absence is not decidable).
MARKERS = {"python": "pyproject.toml", "node": "package.json", "rust": "Cargo.toml"}


def _seed(tmp_path: Path, name: str, files: dict[str, str]) -> Path:
    """Build a seed workspace tree with the given relative files."""
    root = tmp_path / name
    root.mkdir(parents=True)
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def _read_key(manifest: Path, key: str) -> str:
    """The value of ``key`` in a scaffolded ``.vig-os`` (empty when bare)."""
    lines = manifest.read_text(encoding="utf-8").splitlines()
    declarations = [ln for ln in lines if ln.startswith(f"{key}=")]
    assert len(declarations) == 1, f"expected one {key}= line, found {declarations!r}"
    return declarations[0].split("=", 1)[1]


def _manifest(**keys: str) -> str:
    """A minimal consumer .vig-os carrying the given keys."""
    body = "DEVKIT_VERSION=1.2.3\nDEVKIT_MODE=both\n"
    for key, value in keys.items():
        body += f"{key}={value}\n"
    return body


def _scaffolded_languages(tmp_path: Path, seed: Path, name: str) -> str:
    """Scaffold over ``seed`` and return the resulting DEVKIT_LANGUAGES value."""
    proc = scaffold(tmp_path, seed=seed, name=name)
    assert proc.returncode == 0, proc.stderr
    return _read_key(tmp_path / name / ".vig-os", LANGUAGES_KEY)


# ── Scaffold: seeding, stickiness, growth ────────────────────────────────────


def test_languages_seeded_from_detection_on_python_repo(tmp_path: Path) -> None:
    """A fresh scaffold of a Python repo declares `python`."""
    seed = _seed(tmp_path, "seed", {"pyproject.toml": "[project]\nname='x'\n"})
    assert _scaffolded_languages(tmp_path, seed, "py") == "python"


def test_languages_stay_empty_for_language_neutral_repo(tmp_path: Path) -> None:
    """A repo with no language marker declares nothing — and stays green."""
    seed = _seed(tmp_path, "seed-neutral", {"README.md": "# neutral\n"})
    assert _scaffolded_languages(tmp_path, seed, "neutral") == ""


def test_languages_are_sticky_when_marker_disappears(tmp_path: Path) -> None:
    """A re-scaffold NEVER removes a declared language (#1466).

    This is the load-bearing property: the deploy that deleted pyproject.toml
    re-ran the scaffold in the same commit, so a detection cache would have been
    rewritten to empty and CI would still have been green.
    """
    seed = _seed(
        tmp_path,
        "seed-sticky",
        {".vig-os": _manifest(**{LANGUAGES_KEY: "python"}), "README.md": "# x\n"},
    )
    proc = scaffold(tmp_path, seed=seed, name="sticky")
    assert proc.returncode == 0, proc.stderr
    assert _read_key(tmp_path / "sticky" / ".vig-os", LANGUAGES_KEY) == "python"


def test_missing_marker_prints_a_loud_notice(tmp_path: Path) -> None:
    """The scaffold names the declared language and its missing marker."""
    seed = _seed(
        tmp_path,
        "seed-notice",
        {".vig-os": _manifest(**{LANGUAGES_KEY: "python"}), "README.md": "# x\n"},
    )
    proc = scaffold(tmp_path, seed=seed, name="notice")
    assert proc.returncode == 0, proc.stderr
    combined = proc.stdout + proc.stderr
    assert "python" in combined
    assert "pyproject.toml" in combined
    assert LANGUAGES_KEY in combined


def test_newly_detected_language_is_added(tmp_path: Path) -> None:
    """A language that appears since the last scaffold joins the declaration."""
    seed = _seed(
        tmp_path,
        "seed-grow",
        {
            ".vig-os": _manifest(**{LANGUAGES_KEY: "python"}),
            "pyproject.toml": "[project]\nname='x'\n",
            "package.json": '{"name": "x"}\n',
        },
    )
    assert _scaffolded_languages(tmp_path, seed, "grow") == "python,node"


def test_languages_round_trip_across_force_upgrade(tmp_path: Path) -> None:
    """A hand-declared value survives a `--force` upgrade unchanged."""
    seed = _seed(
        tmp_path,
        "seed-rt",
        {
            ".vig-os": _manifest(**{LANGUAGES_KEY: "python,rust"}),
            "pyproject.toml": "[project]\nname='x'\n",
            "Cargo.toml": "[package]\nname='x'\n",
        },
    )
    assert _scaffolded_languages(tmp_path, seed, "rt") == "python,rust"


def test_invalid_language_aborts_the_scaffold(tmp_path: Path) -> None:
    """An unknown language name fails loudly at the write path."""
    seed = _seed(
        tmp_path,
        "seed-bad",
        {".vig-os": _manifest(**{LANGUAGES_KEY: "klingon"})},
    )
    proc = scaffold(tmp_path, seed=seed, name="bad", check=False)
    assert proc.returncode != 0
    assert LANGUAGES_KEY in proc.stderr


# ── resolve-toolchain: the `languages` output ────────────────────────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(None, "", id="key-absent-empty"),
        pytest.param("", "", id="key-empty"),
        pytest.param("python", "python", id="single"),
        pytest.param("python, node ,rust", "python,node,rust", id="whitespace-trimmed"),
        pytest.param(" ,", "", id="all-blank-empty"),
    ],
)
def test_languages_output_emission(
    tmp_path: Path, value: str | None, expected: str
) -> None:
    """DEVKIT_LANGUAGES is normalized onto the `languages` output."""
    manifest = "DEVKIT_MODE=direnv\nDEVKIT_VERSION=1.2.3\n"
    if value is not None:
        manifest += f"{LANGUAGES_KEY}={value}\n"
    outputs = run_resolve_toolchain(tmp_path, manifest)
    assert outputs[LANGUAGES_OUTPUT] == expected


def test_languages_output_emitted_without_manifest(tmp_path: Path) -> None:
    """No .vig-os at all still emits an explicit empty `languages`."""
    outputs = run_resolve_toolchain(tmp_path, None, check=False)
    assert outputs[LANGUAGES_OUTPUT] == ""


# ── ci.yml: the gate's wiring ────────────────────────────────────────────────


def test_gate_runs_in_resolve_toolchain_job() -> None:
    """One early gate, in the job every toolchain job already `needs:`."""
    workflow = load_workflow(WORKFLOWS / "ci.yml")
    step = step_by_name(steps_of_job(workflow, "resolve-toolchain"), GATE_STEP)
    assert step["run"], "the gate must carry a run block"


def test_gate_routes_languages_through_env() -> None:
    """The declared list reaches the shell via env, never inline (zizmor)."""
    workflow = load_workflow(WORKFLOWS / "ci.yml")
    step = step_by_name(steps_of_job(workflow, "resolve-toolchain"), GATE_STEP)
    assert (
        f"${{{{ steps.resolve.outputs.{LANGUAGES_OUTPUT} }}}}" in step["env"].values()
    )
    assert "${{" not in step["run"]


@pytest.mark.parametrize("marker", sorted(MARKERS.values()))
def test_resolve_toolchain_checkout_includes_markers(marker: str) -> None:
    """The sparse checkout must fetch the marker files the gate tests for."""
    workflow = load_workflow(WORKFLOWS / "ci.yml")
    checkout = step_by_name(steps_of_job(workflow, "resolve-toolchain"), "Checkout")
    patterns = checkout["with"]["sparse-checkout"].split()
    assert marker in patterns


# ── ci.yml: the gate's behavior (executed bash) ──────────────────────────────


def _run_gate(tmp_path: Path, languages: str, markers: list[str]) -> tuple[int, str]:
    """Execute the gate step's real bash against a tree carrying ``markers``."""
    workflow = load_workflow(WORKFLOWS / "ci.yml")
    step = step_by_name(steps_of_job(workflow, "resolve-toolchain"), GATE_STEP)
    for marker in markers:
        (tmp_path / marker).write_text("", encoding="utf-8")
    proc = subprocess.run(
        ["bash", "-c", step["run"]],
        cwd=tmp_path,
        env={**os.environ, "LANGUAGES": languages},
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout + proc.stderr


def test_gate_passes_for_language_neutral_repo(tmp_path: Path) -> None:
    """No declaration => nothing to assert; a neutral repo stays green."""
    rc, _ = _run_gate(tmp_path, "", [])
    assert rc == 0


@pytest.mark.parametrize(("language", "marker"), sorted(MARKERS.items()))
def test_gate_passes_when_marker_present(
    tmp_path: Path, language: str, marker: str
) -> None:
    rc, _ = _run_gate(tmp_path, language, [marker])
    assert rc == 0


@pytest.mark.parametrize(("language", "marker"), sorted(MARKERS.items()))
def test_gate_fails_when_marker_absent(
    tmp_path: Path, language: str, marker: str
) -> None:
    """The failure names the language, the marker, and the way out."""
    rc, output = _run_gate(tmp_path, language, [])
    assert rc == 1
    assert language in output
    assert marker in output
    assert ".vig-os" in output


def test_gate_fails_when_one_of_several_markers_is_absent(tmp_path: Path) -> None:
    rc, output = _run_gate(tmp_path, "python,node", ["package.json"])
    assert rc == 1
    assert "pyproject.toml" in output


def test_gate_skips_nix(tmp_path: Path) -> None:
    """nix has no single marker file, so it is declared but never gated."""
    rc, output = _run_gate(tmp_path, "nix", [])
    assert rc == 0
    assert "nix" in output


def test_gate_warns_on_unknown_language(tmp_path: Path) -> None:
    """An unmapped name warns; the loud guard lives at the scaffold write path."""
    rc, output = _run_gate(tmp_path, "klingon", [])
    assert rc == 0
    assert "::warning::" in output
