"""Scaffold-manifest tests: every ``.vig-os`` knob ships declared and empty.

Each devkit knob is an opt-in/opt-out ``.vig-os`` key that must (a) ship in the
scaffold manifest so consumers can discover it, and (b) ship *empty* so the
default behavior is unchanged until a repo opts in. The per-feature suites pin
the behavior behind each knob; this file pins the declarations once, replacing
the near-identical ``test_vig_os_declares_X_key`` /
``test_resolve_toolchain_emits_X_output`` tests that had accreted one per
feature file (#1413).

Refs: #1044, #1045, #1173, #1207, #1228, #1282, #1284, #1295, #1296, #1431,
#1478, #1601, #1633, #1651, #1710, #1746, #1752
"""

from __future__ import annotations

import pytest

from tests.workflow_scaffold import RESOLVE_ACTION, WORKSPACE, load_workflow

# (key, issue) — every scaffold-manifest knob, all shipping empty by default.
MANIFEST_KEYS = [
    ("DEVKIT_RELEASE_REQUIRED_APPROVALS", "#1851"),
    ("DEVKIT_WORKFLOW", "#1207"),
    ("DEVKIT_TAG_PREFIX", "#1044"),
    ("DEVKIT_FLOATING_TAGS", "#1045"),
    ("DEVKIT_CI_RUNNER", "#1173"),
    ("DEVKIT_DEV_PROFILE_PATH", "#1601"),
    ("DEVKIT_SYNC_TARGET", "#1228"),
    ("DEVKIT_SYNC_SCHEDULE", "#1228"),
    ("DEVKIT_FEATURES_DISABLED", "#1284"),
    ("DEVKIT_REFS_POLICY", "#1282"),
    ("DEVKIT_REFS_OPTIONAL_TYPES", "#1633"),
    ("DEVKIT_COMMIT_TYPES", "#1431"),
    ("DEVKIT_BRANCH_TYPES", "#1432"),
    ("DEVKIT_AUTO_UPGRADE", "#1296"),
    ("DEVKIT_UPGRADE_EXCLUDE", "#1296"),
    ("DEVKIT_DRIFT_CHECK", "#1295"),
    ("DEVKIT_LANGUAGES", "#1478"),
    ("DEVKIT_LICENSE", "#1651"),
    ("DEVKIT_COMMIT_APP_ENVIRONMENT", "#1710"),
    ("DEVKIT_PRERELEASE_FORMAT", "#1746"),
    ("DEVKIT_FLAKE_PIN_ADVANCE", "#1752"),
]

# (output, issue) — outputs the resolve-toolchain composite action must declare
# for the scaffolded workflows to consume.
RESOLVE_OUTPUTS = [
    ("release-required-approvals", "#1851"),
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
    ("prerelease-format", "#1746"),
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


@pytest.mark.parametrize("value", ["", "0", "2", "-1", "1.5", "abc"])
def test_release_approvals_manifest(tmp_path, value):
    from tests.workflow_scaffold import exec_resolve_toolchain, scaffold

    valid = value in {"", "0", "2"}
    manifest = f"DEVKIT_MODE=bare\nDEVKIT_RELEASE_REQUIRED_APPROVALS={value}\n"
    resolve_dir = tmp_path / "resolve"
    resolve_dir.mkdir()
    proc, outputs = exec_resolve_toolchain(resolve_dir, manifest)
    assert (proc.returncode == 0) == valid, proc.stdout + proc.stderr
    if valid:
        assert outputs["release-required-approvals"] == (value or "1")
    else:
        assert "DEVKIT_RELEASE_REQUIRED_APPROVALS" in proc.stdout + proc.stderr
        assert "non-negative integer" in proc.stdout + proc.stderr
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".vig-os").write_text(manifest)
    result = scaffold(tmp_path, check=False)
    assert (result.returncode == 0) == valid, result.stdout + result.stderr
    if valid:
        assert (
            f"DEVKIT_RELEASE_REQUIRED_APPROVALS={value}\n"
            in (workspace / ".vig-os").read_text()
        )
    else:
        assert "non-negative integer" in result.stderr
