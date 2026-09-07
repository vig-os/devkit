"""The configurable dev-shell gcroot profile path (#1601).

``setup-devkit-toolchain``'s direnv branch realises the consumer dev-shell into
a ``--profile``. The ``--profile`` is what makes it a **gcroot** rather than a
bare ``nix develop``, and under ``RUNNER_TEMP`` that root is wiped when the job
ends. On a hosted runner that is correct — the machine is discarded too. On an
**ephemeral self-hosted** runner the trade-off inverts: ``RUNNER_TEMP`` goes but
the ``/nix/store`` stays, so nothing roots the dev-shell between jobs and the
host's ``nix.gc`` collects the closure every CI run needs (measured: a 26 s step
becoming 180–237 s, and ``ci.yml`` pays it in three lanes per run).

The knob follows ``DEVKIT_CI_RUNNER`` (#1173) exactly, because it is the same
class of fact — an infrastructure detail of the runner this repo builds on:
declared in the consumer's committed ``.vig-os``, resolved by
``resolve-toolchain``, injected into the managed workflow. No repo variable to
declare, and it round-trips a ``--force`` upgrade through the persisted-values
mechanism. Empty (the shipped default) keeps every consumer byte-identical.

Validation is deliberately split. ``resolve-toolchain`` refuses a value no host
could make persistent — relative, or inside the runner's ``_work`` tree — once,
before any lane pays a realisation. Only the toolchain step, running on the
target host, can tell whether the directory is actually creatable and writable,
so that half stays there. A silent fallback in either place would be
indistinguishable from the bug.

The step's own behavior (default, validation, every realisation moving together)
is executed bash and lives in ``test_setup_toolchain_env.py``.

Refs: #1601
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import WORKFLOWS, WORKSPACE
from tests.workflow_scaffold import exec_resolve_toolchain as _exec_resolve
from tests.workflow_scaffold import load_workflow as _load
from tests.workflow_scaffold import run_resolve_toolchain as _run_resolve

if TYPE_CHECKING:
    from pathlib import Path

ACTION = WORKSPACE / ".github" / "actions" / "setup-devkit-toolchain" / "action.yml"

MANIFEST_KEY = "DEVKIT_DEV_PROFILE_PATH"
INPUT_NAME = "dev-profile-path"
OUTPUT_NAME = "dev-profile-path"
ENV_NAME = "DEVKIT_DEV_PROFILE_PATH"
WIRING = "${{ needs.resolve-toolchain.outputs.dev-profile-path }}"
DEVSHELL_STEP_NAME = "Build repo flake dev-shell and export PATH"
TOOLCHAIN_USES = "./.github/actions/setup-devkit-toolchain"

# A plausible persistent gcroot directory on a self-hosted runner host.
PERSISTENT_PATH = "/var/lib/devkit/gcroots/dev-profile"

# The lanes DEVKIT_CI_RUNNER can move onto the consumer's own runner, and so the
# only ones where the profile path means anything: everything else in the
# scaffold stays on the hosted default, where RUNNER_TEMP is exactly right.
SELF_HOSTABLE_LANES = ("lint", "test", "commit-checks")

# `--profile "<value>"` as the step writes it.
PROFILE_RE = re.compile(r'--profile\s+"([^"]+)"')


def _devshell_step() -> dict:
    action = _load(ACTION)
    for step in action["runs"]["steps"]:
        if step.get("name") == DEVSHELL_STEP_NAME:
            return step
    raise AssertionError(f"step {DEVSHELL_STEP_NAME!r} not found in {ACTION}")


def _toolchain_step(job: dict) -> dict:
    for step in job["steps"]:
        if step.get("uses") == TOOLCHAIN_USES:
            return step
    raise AssertionError("job has no setup-devkit-toolchain step")


# ── The action's input ────────────────────────────────────────────────────────


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
    assert MANIFEST_KEY in description, (
        "the input description must name the .vig-os key that feeds it"
    )


def test_dev_profile_path_reaches_the_step_through_the_environment() -> None:
    """The input is routed via `env:`, never interpolated into `run:`.

    A consumer-supplied path expanded inline in `run:` is the template-injection
    shape the zizmor gate rejects; every other consumer-controlled value in this
    scaffold takes the same env route (#1279).
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


# ── resolve-toolchain: reading and vetting the manifest key ───────────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(None, "", id="key-absent"),
        pytest.param("", "", id="key-empty"),
        pytest.param(PERSISTENT_PATH, PERSISTENT_PATH, id="absolute-path"),
        pytest.param(f"  {PERSISTENT_PATH}  ", PERSISTENT_PATH, id="whitespace"),
        pytest.param(f'"{PERSISTENT_PATH}"', PERSISTENT_PATH, id="quoted"),
        pytest.param(f"{PERSISTENT_PATH}/", PERSISTENT_PATH, id="trailing-slash"),
    ],
)
def test_resolve_emits_the_manifest_path(
    tmp_path: Path, value: str | None, expected: str
) -> None:
    """The key round-trips to the output; absent/empty keeps today's default."""
    manifest = "DEVKIT_MODE=direnv\nDEVKIT_VERSION=1.2.3\n"
    if value is not None:
        manifest += f"{MANIFEST_KEY}={value}\n"

    outputs = _run_resolve(tmp_path, manifest)

    assert outputs[OUTPUT_NAME] == expected


@pytest.mark.parametrize(
    ("value", "why"),
    [
        pytest.param("devkit-dev-profile", "relative", id="relative"),
        pytest.param("../gcroots/dev-profile", "relative", id="parent-relative"),
        pytest.param(
            "/home/runner/actions-runner/_work/_temp/devkit-dev-profile",
            "runner-temp",
            id="runner-temp",
        ),
        pytest.param(
            "/home/runner/actions-runner/_work/repo/repo/.gcroot",
            "workspace",
            id="workspace",
        ),
        pytest.param(
            "/home/runner/work/_temp/devkit-dev-profile",
            "hosted runner-temp",
            id="hosted-runner-temp",
        ),
        pytest.param("/", "root", id="filesystem-root"),
    ],
)
def test_resolve_refuses_a_path_that_cannot_persist(
    tmp_path: Path, value: str, why: str
) -> None:
    """A value no host could keep across jobs fails at resolve time.

    Once, on the cheap hosted job that produces the output — not three times
    over, after each toolchain lane has already realised the dev-shell.
    """
    manifest = f"DEVKIT_MODE=direnv\nDEVKIT_VERSION=1.2.3\n{MANIFEST_KEY}={value}\n"

    proc, outputs = _exec_resolve(tmp_path, manifest)

    assert proc.returncode != 0, f"a {why} dev-profile path must fail resolve"
    assert "::error::" in proc.stdout + proc.stderr
    assert MANIFEST_KEY in proc.stdout + proc.stderr, (
        "the refusal must name the manifest key the consumer has to fix"
    )
    assert not outputs.get(OUTPUT_NAME), (
        "a refused path must never reach the output — a lane would then use it"
    )


def test_resolve_emits_the_path_in_every_mode(tmp_path: Path) -> None:
    """The output is emitted unconditionally, like every other manifest knob."""
    for mode in ("direnv", "both", "bare", "devcontainer"):
        manifest = (
            f"DEVKIT_MODE={mode}\nDEVKIT_VERSION=1.2.3\n"
            f"{MANIFEST_KEY}={PERSISTENT_PATH}\n"
        )
        outputs = _run_resolve(tmp_path, manifest)
        assert outputs[OUTPUT_NAME] == PERSISTENT_PATH, f"missing in mode {mode}"


# ── ci.yml: the lanes that can run on the consumer's runner ───────────────────


def test_ci_resolve_job_reexports_the_dev_profile_path() -> None:
    """The resolve job re-exports the output so the lanes can consume it."""
    job = _load(WORKFLOWS / "ci.yml")["jobs"]["resolve-toolchain"]

    assert job["outputs"].get(OUTPUT_NAME) == (
        "${{ steps.resolve.outputs.dev-profile-path }}"
    )


@pytest.mark.parametrize("lane", SELF_HOSTABLE_LANES)
def test_self_hostable_lanes_pass_the_resolved_path(lane: str) -> None:
    """Every lane DEVKIT_CI_RUNNER can move off the hosted runner is wired.

    These three are exactly the jobs that pay the re-realisation, three times
    per CI run, when the gcroot did not survive the previous job.
    """
    job = _load(WORKFLOWS / "ci.yml")["jobs"][lane]

    assert _toolchain_step(job)["with"].get(INPUT_NAME) == WIRING, (
        f"the {lane} lane must pass {INPUT_NAME}: {WIRING}"
    )
