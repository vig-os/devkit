"""Parser-tolerance tests for the resolve-image action against the #885 manifest.

``.vig-os`` grew from a single version pin into the project's declarative
manifest (``DEVKIT_MODE``, ``DEVKIT_PROJECT``, ``DEVKIT_ORG``, ``DEVKIT_REPO``,
reserved ``DEVKIT_MODULES``). The resolve-image composite action parses the
file line-based and matches ``DEVCONTAINER_VERSION=*`` only, so the new keys
must be byte-for-byte invisible to it: these tests extract the real ``run``
script from the action YAML and execute it against a version-only and a
full-manifest ``.vig-os``, asserting identical ``GITHUB_OUTPUT`` results.
(The other two consumers, ``initialize.sh`` and ``version-check.sh``, are
covered by ``tests/bats/manifest-parsers.bats``.)

Refs: #885
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

RESOLVE_IMAGE_ACTION = (
    REPO_ROOT / ".github" / "actions" / "resolve-image" / "action.yml"
)

VERSION_ONLY_MANIFEST = """\
# vig-os devcontainer configuration
DEVCONTAINER_VERSION=0.4.0
"""

FULL_MANIFEST = """\
# vig-os devcontainer configuration
DEVCONTAINER_VERSION=0.4.0
DEVKIT_MODE=both
DEVKIT_PROJECT=probe
DEVKIT_ORG=Probe/Org
DEVKIT_REPO=probe/probe
DEVKIT_MODULES="native rust"
DEVKIT_FUTURE_FLAG=whatever
"""


def _resolve_step_script() -> str:
    """The bash body of the action's 'Resolve image tag' step."""
    action = yaml.safe_load(RESOLVE_IMAGE_ACTION.read_text(encoding="utf-8"))
    steps = action["runs"]["steps"]
    resolve = next(s for s in steps if s.get("id") == "resolve")
    return resolve["run"]


def _run_resolver(tmp_path: Path, manifest: str, name: str) -> str:
    """Run the extracted resolver in a dir holding ``manifest`` as .vig-os.

    Returns the GITHUB_OUTPUT contents.
    """
    workdir = tmp_path / name
    workdir.mkdir()
    (workdir / ".vig-os").write_text(manifest, encoding="utf-8")
    github_output = workdir / "github_output"
    github_output.touch()
    result = subprocess.run(
        ["bash", "-c", _resolve_step_script()],
        cwd=workdir,
        env={
            **os.environ,
            "INPUT_IMAGE_TAG": "",
            "GITHUB_OUTPUT": str(github_output),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"resolver failed for {name}: {result.stdout}\n{result.stderr}"
    )
    return github_output.read_text(encoding="utf-8")


def test_resolver_ignores_manifest_keys(tmp_path: Path) -> None:
    """The #885 manifest keys never disturb version resolution."""
    output = _run_resolver(tmp_path, FULL_MANIFEST, "full")
    assert output == "tag=0.4.0\n"


def test_resolver_output_identical_for_legacy_and_full_manifest(
    tmp_path: Path,
) -> None:
    """Byte-for-byte identical resolution with and without the new keys."""
    legacy = _run_resolver(tmp_path, VERSION_ONLY_MANIFEST, "legacy")
    full = _run_resolver(tmp_path, FULL_MANIFEST, "full")
    assert legacy == full == "tag=0.4.0\n"
