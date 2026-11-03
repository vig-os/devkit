"""Evaluation-only regression checks for CI's managed Python metadata (#1976)."""

import shutil

import pytest

from tests.nix_helpers import REPO_ROOT, nix_eval_json


@pytest.mark.skipif(shutil.which("nix") is None, reason="Nix evaluation requires nix")
@pytest.mark.parametrize("system", ["x86_64-linux", "aarch64-linux"])
def test_metadata_url_matches_packaged_uv(system: str) -> None:
    """Both runner architectures must use the packaged uv's metadata layout.

    uv 0.13 split managed Python into uv-python-managed. No downloads or
    builds are needed to check the dev-shell environment used by both actions.
    """
    version = nix_eval_json(
        f"{REPO_ROOT}#devShells.{system}.default",
        apply='shell: (builtins.head (builtins.filter (p: (p.pname or "") == "uv") shell.nativeBuildInputs)).version',
    )
    crate = (
        "uv-python-managed"
        if tuple(map(int, version.split(".")[:2])) >= (0, 13)
        else "uv-python"
    )
    assert (
        nix_eval_json(
            f"{REPO_ROOT}#devShells.{system}.default.UV_PYTHON_DOWNLOADS_JSON_URL"
        )
        == f"https://raw.githubusercontent.com/astral-sh/uv/{version}/crates/{crate}/download-metadata.json"
    )


@pytest.mark.parametrize(
    "action",
    [
        ".github/actions/setup-env/action.yml",
        "assets/workspace/.github/actions/setup-devkit-toolchain/action.yml",
    ],
)
def test_actions_forward_devshell_metadata_url(action: str) -> None:
    """Both CI entry points forward the flake value rather than rebuilding it."""
    script = (REPO_ROOT / action).read_text()
    assert "${UV_PYTHON_DOWNLOADS_JSON_URL:-}" in script
    assert (
        'echo "UV_PYTHON_DOWNLOADS_JSON_URL=$UV_DL_JSON_URL" >> "$GITHUB_ENV"' in script
    )
