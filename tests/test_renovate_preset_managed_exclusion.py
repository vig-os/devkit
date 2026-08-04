"""Drift gate: the shipped renovate preset disables the managed workflow set.

Issue #1332: consumers scaffolded by devkit ran Renovate's ``github-actions``
manager over the devkit-**managed** workflows and composite actions, opening
duplicate/clobbering pin-bump PRs for files the next ``devkit-upgrade``
regenerates wholesale. The shipped preset
(``assets/workspace/.github/renovate-default.json``) now carries a trailing
``enabled: false`` packageRule covering exactly the managed set; devkit's own
root ``renovate.json`` re-enables its root paths with a later ``enabled: true``
rule (the extending config's rules merge after the preset's and win).

These tests pin the enumeration without invoking Renovate: the disabled list is
derived from the shipped workflow directory minus the ``PRESERVE_FILES`` seams
(SSoT in ``assets/init-workspace.sh``) plus the two managed composite actions, so
adding or renaming a managed workflow cannot silently reopen the gap.

Refs: #1332
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRESET = REPO_ROOT / "assets" / "workspace" / ".github" / "renovate-default.json"
ROOT_RENOVATE = REPO_ROOT / "renovate.json"
MANAGED_WORKFLOWS = REPO_ROOT / "assets" / "workspace" / ".github" / "workflows"
INIT_WORKSPACE = REPO_ROOT / "assets" / "init-workspace.sh"

# The managed composite actions that carry SHA-pinned third-party `uses:` and
# are regenerated on upgrade like the workflows.
MANAGED_ACTION_GLOBS = {
    ".github/actions/setup-devkit-toolchain/**",
    ".github/actions/resolve-toolchain/**",
}


def _load_preserve_files() -> set[str]:
    """Reuse the SSoT parser in scripts/sync_manifest.py (PRESERVE_FILES)."""
    scripts_dir = REPO_ROOT / "scripts"
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location(
        "sync_manifest", scripts_dir / "sync_manifest.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_manifest"] = module
    spec.loader.exec_module(module)
    return module.load_preserve_files(INIT_WORKSPACE)


def _package_rules(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["packageRules"]


def _expected_managed_filenames() -> set[str]:
    """Managed workflows (dir listing minus preserved seams) + managed actions."""
    preserve_files = _load_preserve_files()
    preserved_workflow_names = {
        Path(rel).name for rel in preserve_files if rel.startswith(".github/workflows/")
    }
    shipped = {p.name for p in MANAGED_WORKFLOWS.iterdir() if p.is_file()}
    managed = shipped - preserved_workflow_names
    return {f".github/workflows/{name}" for name in managed} | MANAGED_ACTION_GLOBS


def test_preset_disables_exactly_the_managed_set() -> None:
    """The preset's trailing enabled:false rule covers exactly the managed set."""
    rules = _package_rules(PRESET)
    disabled = [r for r in rules if r.get("enabled") is False and "matchFileNames" in r]
    assert len(disabled) == 1, (
        "expected exactly one enabled:false matchFileNames rule in the preset, "
        f"found {len(disabled)}"
    )
    rule = disabled[0]
    assert set(rule["matchFileNames"]) == _expected_managed_filenames()


def test_preset_disable_rule_is_last() -> None:
    """Ordering is load-bearing: the exclusion must be the final preset rule.

    Renovate merges packageRules in order and a consumer's own later rules win,
    so the exclusion must sit last in the preset for the consumer opt-back-in
    (and devkit's own root re-enable) to override it.
    """
    rules = _package_rules(PRESET)
    last = rules[-1]
    assert last.get("enabled") is False and "matchFileNames" in last


def test_root_renovate_reenables_devkit_own_paths() -> None:
    """Devkit's root config re-enables its own root workflows/actions, last."""
    rules = _package_rules(ROOT_RENOVATE)
    reenable = [r for r in rules if r.get("enabled") is True and "matchFileNames" in r]
    assert len(reenable) == 1, (
        "expected exactly one enabled:true matchFileNames rule in root "
        f"renovate.json, found {len(reenable)}"
    )
    rule = reenable[0]
    assert {".github/workflows/**", ".github/actions/**"}.issubset(
        set(rule["matchFileNames"])
    )
    # Must merge after the preset's exclusion — being a root rule already places
    # it later, but keep it last so no other root rule can shadow it either.
    assert rules[-1] is rule
