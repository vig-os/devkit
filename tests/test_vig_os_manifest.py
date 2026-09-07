"""Scaffold-manifest tests: every ``.vig-os`` knob ships declared and empty.

Each devkit knob is an opt-in/opt-out ``.vig-os`` key that must (a) ship in the
scaffold manifest so consumers can discover it, and (b) ship *empty* so the
default behavior is unchanged until a repo opts in. The per-feature suites pin
the behavior behind each knob; this file pins the declarations once, replacing
the near-identical ``test_vig_os_declares_X_key`` /
``test_resolve_toolchain_emits_X_output`` tests that had accreted one per
feature file (#1413).

Refs: #1044, #1045, #1173, #1207, #1228, #1282, #1284, #1295, #1296, #1431,
#1478, #1601
"""

from __future__ import annotations

import pytest

from tests.workflow_scaffold import RESOLVE_ACTION, WORKSPACE, load_workflow

# (key, issue) — every scaffold-manifest knob, all shipping empty by default.
MANIFEST_KEYS = [
    ("DEVKIT_WORKFLOW", "#1207"),
    ("DEVKIT_TAG_PREFIX", "#1044"),
    ("DEVKIT_FLOATING_TAGS", "#1045"),
    ("DEVKIT_CI_RUNNER", "#1173"),
    ("DEVKIT_DEV_PROFILE_PATH", "#1601"),
    ("DEVKIT_SYNC_TARGET", "#1228"),
    ("DEVKIT_SYNC_SCHEDULE", "#1228"),
    ("DEVKIT_FEATURES_DISABLED", "#1284"),
    ("DEVKIT_REFS_POLICY", "#1282"),
    ("DEVKIT_COMMIT_TYPES", "#1431"),
    ("DEVKIT_BRANCH_TYPES", "#1432"),
    ("DEVKIT_AUTO_UPGRADE", "#1296"),
    ("DEVKIT_UPGRADE_EXCLUDE", "#1296"),
    ("DEVKIT_DRIFT_CHECK", "#1295"),
    ("DEVKIT_LANGUAGES", "#1478"),
]

# (output, issue) — outputs the resolve-toolchain composite action must declare
# for the scaffolded workflows to consume.
RESOLVE_OUTPUTS = [
    ("tag-prefix", "#1044"),
    ("floating-tags", "#1045"),
    ("runner-json", "#1173"),
    ("dev-profile-path", "#1601"),
    ("refs-optional-types", "#1282"),
    ("commit-types", "#1431"),
    ("branch-types", "#1432"),
    ("drift-check", "#1295"),
    ("drift-image", "#1295"),
    ("languages", "#1478"),
]


@pytest.mark.parametrize(
    ("key", "issue"), MANIFEST_KEYS, ids=[k for k, _ in MANIFEST_KEYS]
)
def test_vig_os_declares_key_empty(key: str, issue: str) -> None:
    """The scaffold manifest ships the knob, empty (= default behavior)."""
    lines = (WORKSPACE / ".vig-os").read_text(encoding="utf-8").splitlines()
    declarations = [ln for ln in lines if ln.startswith(f"{key}=")]
    assert declarations == [f"{key}="], (
        f".vig-os must declare exactly one bare `{key}=` line ({issue}); "
        f"found {declarations!r}"
    )


@pytest.mark.parametrize(
    ("output", "issue"), RESOLVE_OUTPUTS, ids=[o for o, _ in RESOLVE_OUTPUTS]
)
def test_resolve_toolchain_declares_output(output: str, issue: str) -> None:
    """resolve-toolchain declares the output the scaffolded workflows consume."""
    action = load_workflow(RESOLVE_ACTION)
    assert output in action["outputs"], (
        f"resolve-toolchain must declare the `{output}` output ({issue})"
    )
