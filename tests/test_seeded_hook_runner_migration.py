"""Execute the scaffold against released and dev hook layouts (#1929)."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest
import yaml

from tests.workflow_scaffold import INIT_WORKSPACE, REPO_ROOT, WORKSPACE

if TYPE_CHECKING:
    from pathlib import Path

HOOKS = ("prepare-release-extension", "release-extension", "publish-release-extension")
# Audited git log -p across all tags and dev, from the first seam (00ea919d)
# through the pre-S2 dev hooks; S2's SMALL expression is already reconciled.
STOCK = (
    "ubuntu-22.04",
    "ubuntu-24.04",
    "ubuntu-26.04",
    "${{ fromJSON(inputs.runner-json) }}",
    "${{ vars.DEVKIT_CI_RESOLVE_RUNNER || 'ubuntu-26.04' }}",
)
TARGET = next(
    line.strip().removeprefix("runs-on: ")
    for line in (WORKSPACE / ".github/workflows/release-extension.yml")
    .read_text()
    .splitlines()
    if line.strip().startswith("runs-on:")
)
VALID = {"DEVKIT_UPGRADE_CONTEXT": "1", "DEVKIT_UPGRADE_CI_RUNNER_SMALL": "pool-s"}
ANCHOR = "MIGRATION.md#seeded-hook-runner-migration"


def _hook(
    value: str, *, jobs: str = "jobs:", indent: int = 2, job: str = "extension"
) -> bytes:
    return (
        f"name: Consumer hook\non: workflow_call\n{jobs}\n"
        f"{' ' * indent}{job}:\n{' ' * (indent * 2)}runs-on: {value}\n"
        f"{' ' * (indent * 2)}steps: []\n"
    ).encode()


def _upgrade(
    tmp_path: Path,
    hooks: dict[str, bytes] | None,
    context: dict[str, str],
    manifest: str = "",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    ws = tmp_path / "workspace"
    ws.mkdir(exist_ok=True)
    if hooks is not None:
        for name, data in hooks.items():
            path = ws / f".github/workflows/{name}.yml"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (ws / ".vig-os").write_text("DEVKIT_MODE=direnv\n" + manifest)
    env = {k: v for k, v in os.environ.items() if not k.startswith("DEVKIT_UPGRADE_")}
    env.update(context)
    env.update(
        TEMPLATE_DIR=str(WORKSPACE),
        WORKSPACE_DIR=str(ws),
        SHORT_NAME="testproj",
        GITHUB_REPOSITORY="test/repo",
    )
    proc = subprocess.run(
        ["bash", str(INIT_WORKSPACE), "--force", "--no-prompts"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc, ws


@pytest.mark.parametrize("value", STOCK)
def test_every_historical_stock_value_folds(tmp_path: Path, value: str) -> None:
    proc, ws = _upgrade(tmp_path, {name: _hook(value) for name in HOOKS}, VALID)
    for name in HOOKS:
        assert (ws / f".github/workflows/{name}.yml").read_bytes() == _hook(TARGET)
        assert (
            f"Seeded hook reconciled: extension in .github/workflows/{name}.yml"
            in proc.stdout
        )
    assert ANCHOR in proc.stdout
    again, _ = _upgrade(tmp_path, None, VALID)
    assert "Seeded hook reconciled:" not in again.stdout
    assert "Seeded hook drift:" not in again.stdout
    assert "Seeded hook pending:" not in again.stdout


@pytest.mark.parametrize(
    "layout", ["crlf", "jobs-comment", "four-spaces", "quoted-job", "inline-comment"]
)
def test_variant_layouts_preserve_bytes_except_runner(
    tmp_path: Path, layout: str
) -> None:
    old = _hook(
        "ubuntu-26.04",
        jobs="jobs:  # consumer" if layout == "jobs-comment" else "jobs:",
        indent=4 if layout == "four-spaces" else 2,
        job='"extension"' if layout == "quoted-job" else "extension",
    )
    if layout == "crlf":
        old = old.replace(b"\n", b"\r\n")
    if layout == "inline-comment":
        old = old.replace(b"ubuntu-26.04", b"ubuntu-26.04  # consumer")
    proc, ws = _upgrade(tmp_path, {HOOKS[0]: old}, VALID)
    expected = old.replace(b"runs-on: ubuntu-26.04", f"runs-on: {TARGET}".encode())
    assert (ws / f".github/workflows/{HOOKS[0]}.yml").read_bytes() == expected
    assert (
        f"Seeded hook reconciled: extension in .github/workflows/{HOOKS[0]}.yml"
        in proc.stdout
    )


@pytest.mark.parametrize(
    "context",
    [
        {},
        {"DEVKIT_UPGRADE_CONTEXT": "0", "DEVKIT_UPGRADE_CI_RUNNER_SMALL": "pool-s"},
        {"DEVKIT_UPGRADE_CI_RUNNER_SMALL": "pool-s"},
        {
            "DEVKIT_UPGRADE_CONTEXT": "1",
            "DEVKIT_UPGRADE_LEGACY_RESOLVE_RUNNER": "pool-old",
        },
        {"DEVKIT_UPGRADE_CONTEXT": "1", "DEVKIT_UPGRADE_CI_RUNNER_SMALL": " pool-s"},
    ],
)
def test_pending_keeps_hook_and_never_suggests_deleting_legacy(
    tmp_path: Path, context: dict[str, str]
) -> None:
    original = _hook(STOCK[-1])
    proc, ws = _upgrade(tmp_path, {HOOKS[0]: original}, context)
    assert (ws / f".github/workflows/{HOOKS[0]}.yml").read_bytes() == original
    assert "Seeded hook pending: extension" in proc.stdout
    assert "CI_RUNNER_SMALL" in proc.stdout
    assert ANCHOR in proc.stdout
    assert "delete the old variable" not in proc.stdout
    assert "pool-old" not in proc.stdout


def test_mixed_stock_and_custom_job_reports_drift_and_blocks_delete(
    tmp_path: Path,
) -> None:
    original = (
        _hook("ubuntu-26.04")
        + b'  "custom":\n    runs-on: custom-pool\n    steps: []\n'
    )
    proc, ws = _upgrade(
        tmp_path,
        {HOOKS[0]: original},
        {**VALID, "DEVKIT_UPGRADE_LEGACY_RESOLVE_RUNNER": "pool-old"},
    )
    assert (ws / f".github/workflows/{HOOKS[0]}.yml").read_bytes() == original.replace(
        b"runs-on: ubuntu-26.04", f"runs-on: {TARGET}".encode()
    )
    assert "Seeded hook reconciled: extension" in proc.stdout
    assert (
        f"Seeded hook drift: custom in .github/workflows/{HOOKS[0]}.yml" in proc.stdout
    )
    assert "delete the old variable" not in proc.stdout
    assert "keep DEVKIT_CI_RESOLVE_RUNNER" in proc.stdout


def test_delete_hint_requires_every_hook_job_reconciled(tmp_path: Path) -> None:
    proc, _ = _upgrade(
        tmp_path,
        {name: _hook(STOCK[-1]) for name in HOOKS},
        {**VALID, "DEVKIT_UPGRADE_LEGACY_RESOLVE_RUNNER": "pool-old"},
    )
    assert "delete the old variable" in proc.stdout
    assert ANCHOR in proc.stdout


def test_no_context_describes_variables_as_unknown(tmp_path: Path) -> None:
    proc, _ = _upgrade(
        tmp_path,
        {},
        {"DEVKIT_UPGRADE_CI_RUNNER_SMALL": "pool-s"},
        "DEVKIT_CI_RUNNER=pool-old\n",
    )
    assert "variables unknown" in proc.stdout
    assert "missing or invalid variables" not in proc.stdout


def test_fold_preserves_missing_final_newline(tmp_path: Path) -> None:
    original = _hook(STOCK[-1]).rstrip(b"\n")
    _, ws = _upgrade(tmp_path, {HOOKS[0]: original}, VALID)
    assert (ws / f".github/workflows/{HOOKS[0]}.yml").read_bytes() == original.replace(
        STOCK[-1].encode(), TARGET.encode()
    )


@pytest.mark.parametrize("kind", ["reconciled", "pending", "drift"])
@pytest.mark.parametrize("workflow", ["pre-n", "current"])
def test_hook_findings_use_the_migration_channel_under_both_body_builders(
    tmp_path: Path,
    kind: str,
    workflow: str,
) -> None:
    value = "custom-pool" if kind == "drift" else STOCK[-1]
    proc, _ = _upgrade(
        tmp_path, {HOOKS[0]: _hook(value)}, {} if kind == "pending" else VALID
    )
    findings = [line for line in proc.stdout.splitlines() if "Seeded hook " in line]
    assert any(f"Seeded hook {kind}:" in line for line in findings)
    assert all(line.startswith("ci-runner-migration:") for line in findings)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    body = tmp_path / "body"
    gh = bindir / "gh"
    gh.write_text(
        '#!/usr/bin/env bash\nif [[ "$2" == view ]]; then exit 1; fi\n'
        "while [[ $# -gt 0 ]]; do\n"
        '  if [[ "$1" == --body ]]; then printf "%s" "$2" > "$BODY_FILE"; exit 0; fi\n'
        "  shift\ndone\nexit 2\n"
    )
    gh.chmod(0o755)
    if workflow == "pre-n":
        script = (REPO_ROOT / "tests/fixtures/pre-n-upgrade-pr-body.sh").read_text()
    else:
        doc = yaml.safe_load(
            (WORKSPACE / ".github/workflows/devkit-upgrade.yml").read_text()
        )
        script = next(
            step["run"]
            for step in doc["jobs"]["upgrade"]["steps"]
            if "adoption PR" in step.get("name", "")
        )
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "BODY_FILE": str(body),
        "TARGET": "1.2.3",
        "BASE": "dev",
        "BRANCH": "chore/adoption",
        "FLAKE_BUMP": "",
        "HOOK_DRIFT": "\n".join(
            line for line in findings if line.startswith("preserved-hook-drift:")
        ),
        "HOOK_RECONCILE": "\n".join(
            line
            for line in findings
            if line.startswith(("preserved-hook-fold:", "preserved-hook-insert:"))
        ),
        "CI_RUNNER_MIGRATION": "\n".join(
            line for line in findings if line.startswith("ci-runner-migration:")
        ),
    }
    result = subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    text = body.read_text()
    if workflow == "pre-n":
        assert (
            "Seeded hook" not in text
        )  # §6: never smuggle runner findings into old hook headings.
        assert "retired hook block" not in text
    else:
        assert "### CI runner migration\n\n" in text
        assert f"Seeded hook {kind}:" in text
        assert ANCHOR in text


def test_migration_docs_and_changelog_match_the_new_contract() -> None:
    docs = (REPO_ROOT / "docs/MIGRATION.md").read_text()
    assert "### Seeded hook runner migration" in docs
    for word in (
        "reconciled",
        "pending",
        "drift",
        "CI_RUNNER_SMALL",
        "DEVKIT_CI_RESOLVE_RUNNER",
    ):
        assert (
            word
            in docs.split("### Seeded hook runner migration", 1)[1].split("\n### ", 1)[
                0
            ]
        )
    changelog = (
        (REPO_ROOT / "CHANGELOG.md")
        .read_text()
        .split("## Unreleased", 1)[1]
        .split("\n## ", 1)[0]
    )
    assert "[#1929]" in changelog.split("### Added", 1)[1].split("\n### ", 1)[0]
    assert "[#1929]" not in changelog.split("### Fixed", 1)[1].split("\n### ", 1)[0]
