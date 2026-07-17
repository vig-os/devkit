"""zizmor baseline + gate invariants for the devkit-managed workflow set.

Issue #1182: zizmor over the devkit-managed workflows surfaced 73 findings that
every consumer had to baseline against code they do not own. Devkit now fixes
what is fixable and ships a maintained, devkit-owned baseline (``zizmor.yml``)
so consumer baselines shrink to zero, gated by devkit's own CI.

These tests pin the deliverable without invoking the ``zizmor`` binary (which is
not part of the toolchain): the baseline ships to consumers, is registered in
the sync manifest, scopes every exemption to a *managed workflow basename*
(never a glob — so a repo-authored workflow can never inherit an exemption), and
the CI gate that lints the managed set against it stays wired.

Refs: #1182
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT_BASELINE = REPO_ROOT / "zizmor.yml"
SCAFFOLD_BASELINE = REPO_ROOT / "assets" / "workspace" / "zizmor.yml"
MANAGED_WORKFLOWS = REPO_ROOT / "assets" / "workspace" / ".github" / "workflows"
MANIFEST = REPO_ROOT / "scripts" / "manifest.toml"
DEVKIT_CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _rules(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["rules"]


def test_baseline_ships_at_root_and_in_scaffold() -> None:
    """The baseline exists both as the devkit SSoT and in the consumer scaffold."""
    assert ROOT_BASELINE.is_file(), "devkit-owned zizmor.yml (SSoT) is missing"
    assert SCAFFOLD_BASELINE.is_file(), "scaffold zizmor.yml is missing"
    # The scaffold copy carries the same audit rules as the root SSoT (the sync
    # hook only prepends the managed-file banner).
    assert _rules(ROOT_BASELINE) == _rules(SCAFFOLD_BASELINE)


def test_baseline_registered_in_sync_manifest() -> None:
    """The scaffolded baseline is registered so consumers inherit it on upgrade."""
    manifest = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))
    sources = {entry["src"] for entry in manifest["entries"]}
    assert "zizmor.yml" in sources


@pytest.mark.parametrize("baseline", [ROOT_BASELINE, SCAFFOLD_BASELINE])
def test_every_exemption_targets_a_managed_workflow_basename(baseline: Path) -> None:
    """Scope rule: exemptions are bare managed basenames, never globs.

    A glob (or a path) could suppress a consumer-authored workflow. Requiring a
    bare filename that resolves to a shipped managed workflow guarantees a
    repo-authored file (different name) is always audited.
    """
    for audit, cfg in _rules(baseline).items():
        for entry in cfg["ignore"]:
            assert "*" not in entry and "/" not in entry, (
                f"{audit}: '{entry}' must be a bare managed basename, not a glob/path"
            )
            assert (MANAGED_WORKFLOWS / entry).is_file(), (
                f"{audit}: '{entry}' does not name a shipped managed workflow"
            )


def test_ci_gate_lints_managed_set_against_baseline() -> None:
    """devkit CI runs zizmor over the managed set with the shipped baseline."""
    ci = yaml.safe_load(DEVKIT_CI.read_text(encoding="utf-8"))
    runs = [
        step.get("run", "")
        for step in ci["jobs"]["project-checks"]["steps"]
        if "run" in step
    ]
    gate = [
        r
        for r in runs
        if "zizmor" in r
        and "--config zizmor.yml" in r
        and "assets/workspace/.github/workflows" in r
    ]
    assert gate, "project-checks must gate the managed workflow set on zizmor"
