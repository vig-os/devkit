"""Shared helpers for the workflow-shape test suites.

Two families live here:

- The scaffold invocation (#1210): the workflow model (#1205) is realized
  entirely at scaffold time, so any suite that needs to observe the *trunk*
  shape must render a real workspace by executing ``assets/init-workspace.sh``.
  ``scaffold``/``scaffold_tree`` centralize that invocation — a ``just`` stub on
  PATH, ``TEMPLATE_DIR``/``WORKSPACE_DIR``/``SHORT_NAME``/``GITHUB_REPOSITORY``
  in the env, and ``--force --no-prompts --mode both``.
- Workflow-YAML access: every shape suite parses the same workflow files, so
  the loader, the ``on:``-key quirk handling, job/step lookups, and the
  resolve-toolchain executed-bash harness live here once instead of as
  per-file private copies.

Refs: #1210, #1413
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "assets" / "workspace"
WORKFLOWS = WORKSPACE / ".github" / "workflows"
INIT_WORKSPACE = REPO_ROOT / "assets" / "init-workspace.sh"
RESOLVE_ACTION = WORKSPACE / ".github" / "actions" / "resolve-toolchain" / "action.yml"

# A properly SHA-pinned action ref: full name + 40-hex commit. Shape-checking
# pins (instead of hardcoding the SHA) keeps tests green across Renovate bumps.
ACTION_PIN_RE = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")


def load_workflow(path: Path) -> dict:
    """Parse a workflow/action YAML file."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def on_block(doc: dict) -> object:
    """The workflow's trigger block (YAML 1.1 parses bare ``on:`` as True)."""
    return doc.get("on", doc.get(True))


def jobs(doc: dict) -> dict:
    return doc.get("jobs") or {}


def needs_of(job: dict) -> list[str]:
    needs = job.get("needs") or []
    return [needs] if isinstance(needs, str) else list(needs)


def steps_of_job(doc: dict, job: str) -> list[dict]:
    return doc["jobs"][job]["steps"]


def step_by_id(steps: list[dict], step_id: str) -> dict:
    matches = [s for s in steps if s.get("id") == step_id]
    assert matches, f"no step with id {step_id!r}"
    return matches[0]


def step_by_name(steps: list[dict], fragment: str) -> dict:
    frag = fragment.lower()
    matches = [s for s in steps if frag in str(s.get("name", "")).lower()]
    assert matches, f"no step with name containing {fragment!r}"
    return matches[0]


def run_text_of_job(job: dict) -> str:
    """All ``run:`` bodies of a job's steps, concatenated."""
    return "\n".join(
        str(s.get("run", "")) for s in (job.get("steps") or []) if isinstance(s, dict)
    )


def both_copies(rel: str) -> list[Path]:
    """Devkit's own copy and the scaffold copy of a ``.github/workflows`` file."""
    return [
        REPO_ROOT / ".github" / "workflows" / rel,
        WORKFLOWS / rel,
    ]


def run_resolve_toolchain(
    tmp_path: Path, manifest: str | None, *, check: bool = True
) -> dict[str, str]:
    """Execute the resolve-toolchain step's real bash against a .vig-os manifest.

    Returns the parsed GITHUB_OUTPUT key=value map. The early outputs
    (``runner-json``, ``drift-check``, ``refs-optional-types``) are emitted
    before mode/tag resolution, so callers exercising an error path (e.g. no
    manifest => default ``both`` mode with no tag) pass ``check=False``.
    """
    action = load_workflow(RESOLVE_ACTION)
    script = action["runs"]["steps"][0]["run"]

    if manifest is not None:
        (tmp_path / ".vig-os").write_text(manifest, encoding="utf-8")

    github_output = tmp_path / "github_output"
    github_output.touch()

    env = {
        **os.environ,
        "INPUT_IMAGE_TAG": "",
        "GITHUB_OUTPUT": str(github_output),
    }
    subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )
    return parse_github_output(github_output)


def parse_github_output(path: Path) -> dict[str, str]:
    """Parse a GITHUB_OUTPUT file's simple key=value lines."""
    outputs: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            outputs[key] = value
    return outputs


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
