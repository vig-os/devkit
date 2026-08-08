"""Shared scaffolding helper for the DEVKIT_WORKFLOW (gitflow | trunk) suites.

The workflow model (#1205) is realized entirely at scaffold time, so any suite
that needs to observe the *trunk* shape must render a real workspace by
executing ``assets/init-workspace.sh``. This helper centralizes that invocation
— a ``just`` stub on PATH, ``TEMPLATE_DIR``/``WORKSPACE_DIR``/``SHORT_NAME``/
``GITHUB_REPOSITORY`` in the env, and ``--force --no-prompts --mode both`` — so
the dev-assuming suites parametrized for trunk (#1210) share one source of
truth with ``tests/test_workflow_model.py`` instead of each re-deriving the run.

Refs: #1210
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "assets" / "workspace"
WORKFLOWS = WORKSPACE / ".github" / "workflows"
INIT_WORKSPACE = REPO_ROOT / "assets" / "init-workspace.sh"


def scaffold(
    tmp_path: Path,
    *,
    workflow: str | None = None,
    seed: Path | None = None,
    name: str = "workspace",
    check: bool = True,
    preview: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Scaffold a workspace by executing the real init-workspace.sh.

    A ``just`` stub on PATH keeps the final ``just sync`` step a fast no-op;
    ``workflow`` appends ``--workflow``; ``seed`` pre-populates the workspace
    (to exercise the upgrade path); ``preview`` appends ``--preview`` so the
    run reports the add/overwrite/preserve/delete plan and exits without
    touching the tree (#886). Returns the CompletedProcess so callers can
    assert on exit code / stderr.
    """
    dest = tmp_path / name
    if seed is not None:
        shutil.copytree(seed, dest)
    else:
        dest.mkdir(exist_ok=True)

    stub = tmp_path / "stub-bin"
    stub.mkdir(exist_ok=True)
    just_stub = stub / "just"
    just_stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    just_stub.chmod(0o755)

    env = {
        **os.environ,
        "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}",
        "TEMPLATE_DIR": str(WORKSPACE),
        "WORKSPACE_DIR": str(dest),
        "SHORT_NAME": "testproj",
        "GITHUB_REPOSITORY": "test/repo",
    }
    args = ["bash", str(INIT_WORKSPACE), "--force", "--no-prompts", "--mode", "both"]
    if workflow is not None:
        args += ["--workflow", workflow]
    if preview:
        args.append("--preview")

    return subprocess.run(args, env=env, check=check, capture_output=True, text=True)


def scaffold_tree(tmp_path: Path, workflow: str | None = None, **kw: object) -> Path:
    """Scaffold and return the workspace root (asserting the run succeeded)."""
    name = kw.pop("name", workflow or "gitflow")
    proc = scaffold(tmp_path, workflow=workflow, name=name, **kw)  # type: ignore[arg-type]
    assert proc.returncode == 0, proc.stderr
    return tmp_path / name
