"""Shape tests: the configurable dev-shell gcroot profile path (#1601).

``setup-devkit-toolchain``'s direnv branch realises the consumer dev-shell into
a ``--profile``. The ``--profile`` is what makes it a **gcroot** rather than a
bare ``nix develop``, and under ``RUNNER_TEMP`` that root is wiped when the job
ends. On a hosted runner that is correct — the machine is discarded too. On an
**ephemeral self-hosted** runner the trade-off inverts: ``RUNNER_TEMP`` goes but
the ``/nix/store`` stays, so nothing roots the dev-shell between jobs and the
host's ``nix.gc`` collects the closure every CI run needs (measured: a 26 s step
becoming 180–237 s, three toolchain lanes per run).

``dev-profile-path`` lets such a runner put the root somewhere that outlives the
job. It is opt-in: unset reproduces today's behavior byte for byte, and the
scaffolded workflows source it from the ``DEVKIT_DEV_PROFILE_PATH`` repository
(or organization) variable — the same wiring as ``vars.CACHIX_CACHE``, and the
only one that survives a devkit upgrade regenerating the managed workflows.

The *behavior* of the resolved path (default, validation, every realisation
moving together) is executed bash and lives in ``test_setup_toolchain_env.py``.

Refs: #1601
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.workflow_scaffold import load_workflow as _load

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "assets" / "workspace"
WORKFLOWS = WORKSPACE / ".github" / "workflows"
INIT_WORKSPACE = REPO_ROOT / "assets" / "init-workspace.sh"
ACTION = WORKSPACE / ".github" / "actions" / "setup-devkit-toolchain" / "action.yml"

INPUT_NAME = "dev-profile-path"
ENV_NAME = "DEVKIT_DEV_PROFILE_PATH"
WIRING = "${{ vars.DEVKIT_DEV_PROFILE_PATH }}"
DEVSHELL_STEP_NAME = "Build repo flake dev-shell and export PATH"
TOOLCHAIN_USES = "./.github/actions/setup-devkit-toolchain"

# `--profile "<value>"` as the step writes it.
PROFILE_RE = re.compile(r'--profile\s+"([^"]+)"')


def _devshell_step() -> dict:
    action = _load(ACTION)
    for step in action["runs"]["steps"]:
        if step.get("name") == DEVSHELL_STEP_NAME:
            return step
    raise AssertionError(f"step {DEVSHELL_STEP_NAME!r} not found in {ACTION}")


def _toolchain_steps(doc: object) -> list[dict]:
    """Every `setup-devkit-toolchain` step anywhere in a workflow document."""
    found: list[dict] = []
    if isinstance(doc, dict):
        if doc.get("uses") == TOOLCHAIN_USES:
            found.append(doc)
        for value in doc.values():
            found += _toolchain_steps(value)
    elif isinstance(doc, list):
        for item in doc:
            found += _toolchain_steps(item)
    return found


def test_action_declares_an_optional_dev_profile_path() -> None:
    """The input exists, is optional, and defaults to today's behavior."""
    action = _load(ACTION)

    assert INPUT_NAME in action["inputs"], (
        f"setup-devkit-toolchain must expose a {INPUT_NAME} input"
    )
    spec = action["inputs"][INPUT_NAME]
    assert spec.get("required") in (False, "false", None)
    # An empty default is what keeps the unset case byte-identical: the step
    # resolves the RUNNER_TEMP path itself, so no consumer changes behavior.
    assert spec.get("default", "") == "", (
        "dev-profile-path must default to empty so hosted runners are untouched"
    )


def test_dev_profile_path_input_is_documented_for_self_hosted_runners() -> None:
    """The input table carries the self-hosted rationale, not just a name."""
    description = _load(ACTION)["inputs"][INPUT_NAME]["description"]

    assert "self-hosted" in description.lower(), (
        "the input description must say why a self-hosted runner needs this"
    )
    assert "RUNNER_TEMP" in description, (
        "the input description must name the default it replaces"
    )


def test_dev_profile_path_reaches_the_step_through_the_environment() -> None:
    """The input is routed via `env:`, never interpolated into `run:`.

    A consumer-supplied path expanded inline in `run:` is the template-injection
    shape the zizmor gate rejects; every other consumer-controlled value in this
    scaffold takes the same env route.
    """
    step = _devshell_step()

    assert step.get("env", {}).get(ENV_NAME) == f"${{{{ inputs.{INPUT_NAME} }}}}", (
        f"the devshell step must map {INPUT_NAME} to {ENV_NAME} via env:"
    )
    assert "${{" not in step["run"], (
        "the devshell step's run: must stay free of ${{ }} interpolation"
    )


def test_every_realisation_uses_the_resolved_profile() -> None:
    """All four `nix develop` calls root the same profile.

    A half-moved profile would leave the closure rooted under RUNNER_TEMP again,
    which is exactly the bug — and it would still look green.
    """
    run = _devshell_step()["run"]
    profiles = set(PROFILE_RE.findall(run))

    assert profiles == {"$DEVKIT_DEV_PROFILE"}, (
        f"every --profile must use the resolved path, got: {sorted(profiles)}"
    )


def test_scaffolded_call_sites_pass_the_repository_variable() -> None:
    """Every managed call site sources the path from `vars`.

    The workflows are regenerated on upgrade, so a repository/organization
    variable is the only place a consumer can set this and keep it.
    """
    call_sites = 0
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        for step in _toolchain_steps(_load(workflow)):
            call_sites += 1
            assert step.get("with", {}).get(INPUT_NAME) == WIRING, (
                f"{workflow.name}: setup-devkit-toolchain call site must pass "
                f"{INPUT_NAME}: {WIRING}"
            )
    assert call_sites > 0, "no setup-devkit-toolchain call sites found"


def test_installer_generated_call_sites_pass_the_repository_variable() -> None:
    """The workflows the installer emits inline carry the same wiring."""
    text = INIT_WORKSPACE.read_text(encoding="utf-8")

    call_sites = text.count(f"uses: {TOOLCHAIN_USES}")
    wired = text.count(f"{INPUT_NAME}: \\{WIRING}")

    assert call_sites > 0, "no setup-devkit-toolchain call sites in the installer"
    assert wired == call_sites, (
        f"{wired}/{call_sites} installer-generated call sites pass {INPUT_NAME}"
    )
