"""setup-devkit-toolchain on the release lane: cache parity, bounds, fail-soft.

#2010: the release-lane jobs (prepare-release, release, promote, ...) called the
composite WITHOUT ``cachix-cache``, so in direnv mode they skipped the
consumer's own binary cache, built its consumer-only derivations from source
and ran into the job timeout. The realisation had no bound of its own either:
a stalled substituter transfer hung silently until the job was cancelled, and
the prepare-release rollback hung in the same step, so it could not roll back.

#2077 (devkit part): a broken ``cachix/cachix-action`` step failed every job,
although Cachix is an optimisation correctness does not depend on.

These tests pin, per acceptance criterion:

- every call site pulls the consumer cache; release-lane call sites never
  receive the push token (#1881 owns the token policy);
- Nix's own network knobs are set, and the wall-clock realisation bound fires
  with an explicit, diagnosable ``::error::`` before any caller's job timeout;
- a failed Cachix step degrades to a named ``::warning::`` instead of failing;
- rollback/cleanup jobs never realise the dev-shell (``minimal: true``).

Refs: #2010, #2077
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import TYPE_CHECKING

import pytest

from tests.github_expression import evaluate
from tests.workflow_scaffold import (
    NIX_NETWORK_SETTINGS,
    SMOKE_WORKFLOWS,
    WORKFLOWS,
    WORKSPACE,
    load_workflow,
)

if TYPE_CHECKING:
    from pathlib import Path

ACTION = WORKSPACE / ".github" / "actions" / "setup-devkit-toolchain" / "action.yml"
TOOLCHAIN_USES = "./.github/actions/setup-devkit-toolchain"
CACHIX_CACHE_EXPR = "${{ vars.CACHIX_CACHE }}"

DEVSHELL_STEP_NAME = "Build repo flake dev-shell and export PATH"
CONTAINER_STEP_NAME = "Configure in-container toolchain env"
CACHIX_STEP_ID = "cachix"
TIMEOUT_INPUT = "realisation-timeout-minutes"
MINIMAL_INPUT = "minimal"

# Files whose call sites still pass the Cachix push token. Narrowing them is
# #1881's job; this list may only ever shrink — no release-lane file joins it.
TOKEN_ALLOWED_FILES = frozenset({"ci.yml", "direnv-smoke.yml"})

# Jobs that use only gh/git/jq/base64 and the retry helper: they must not
# depend on the toolchain they may be rolling back from (#2010).
MINIMAL_JOBS = frozenset(
    {
        ("prepare-release.yml", "rollback"),
        ("prepare-hotfix.yml", "rollback"),
        ("release.yml", "rollback"),
        ("promote-release.yml", "cleanup"),
        # Only git + retry, under a 5-minute job timeout no realisation fits.
        ("sync-main-to-dev.yml", "check"),
    }
)

# Minutes of every caller's job budget that must stay OUTSIDE the realisation
# bound: checkout, Nix install, Cachix and the job's own work. The bound only
# helps if it fires first, with a diagnosis, instead of a silent cancel.
JOB_MARGIN_MINUTES = 4

CONTAINER_MODES = ("devcontainer", "both")
HOST_MODES = ("direnv", "bare")


# ── call-site discovery ──────────────────────────────────────────────────────


def _if(
    expr: str,
    inputs: dict[str, str],
    *,
    outcomes: dict[str, str] | None = None,
    has_nix: str = "false",
) -> bool:
    """Execute a step ``if:`` with the strict managed-expression evaluator."""
    steps: dict[str, dict] = {"detect-nix": {"outputs": {"has-nix": has_nix}}}
    for step_id, outcome in (outcomes or {}).items():
        steps.setdefault(step_id, {})["outcome"] = outcome
    return bool(evaluate(expr, {"inputs": inputs, "steps": steps}))


def _call_sites() -> list[tuple[str, str, dict, dict]]:
    """(file, job id, job, toolchain step) for every scaffolded call site."""
    sites = []
    for path in sorted([*WORKFLOWS.glob("*.yml"), *SMOKE_WORKFLOWS.glob("*.yml")]):
        doc = load_workflow(path)
        for job_id, job in (doc.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                if step.get("uses") == TOOLCHAIN_USES:
                    sites.append((path.name, job_id, job, step))
    return sites


CALL_SITES = _call_sites()
SITE_IDS = [f"{f}:{j}" for f, j, _, _ in CALL_SITES]


def _with(step: dict) -> dict:
    return step.get("with") or {}


def _is_minimal(step: dict) -> bool:
    return str(_with(step).get(MINIMAL_INPUT, "false")).lower() == "true"


def test_call_site_discovery_finds_the_release_lane() -> None:
    """Guard the guard: the sweep sees the release-lane files, not just ci.yml."""
    files = {f for f, _, _, _ in CALL_SITES}
    assert {
        "ci.yml",
        "prepare-release.yml",
        "prepare-hotfix.yml",
        "release.yml",
        "release-core.yml",
        "release-publish.yml",
        "promote-release.yml",
        "abandon-release.yml",
        "sync-issues.yml",
        "sync-main-to-dev.yml",
    } <= files


# ── 1. substituter parity ────────────────────────────────────────────────────


@pytest.mark.parametrize(("wf", "job_id", "job", "step"), CALL_SITES, ids=SITE_IDS)
def test_every_call_site_pulls_the_consumer_cache(
    wf: str, job_id: str, job: dict, step: dict
) -> None:
    """The release lane realises the same closure CI does, from the same cache."""
    assert _with(step).get("cachix-cache") == CACHIX_CACHE_EXPR, (
        f"{wf}:{job_id} must pass cachix-cache: {CACHIX_CACHE_EXPR} (#2010)"
    )


@pytest.mark.parametrize(("wf", "job_id", "job", "step"), CALL_SITES, ids=SITE_IDS)
def test_release_lane_never_receives_the_cachix_token(
    wf: str, job_id: str, job: dict, step: dict
) -> None:
    """Pull-only: widening the push token is #1784/#1881's call, not this one."""
    if wf in TOKEN_ALLOWED_FILES:
        pytest.skip(f"{wf}: token policy owned by #1881")
    assert "cachix-auth-token" not in _with(step), (
        f"{wf}:{job_id} must not pass cachix-auth-token"
    )


# ── 2. bounded realisation ───────────────────────────────────────────────────


def _action() -> dict:
    return load_workflow(ACTION)


def _steps() -> list[dict]:
    return _action()["runs"]["steps"]


def _step(name: str) -> dict:
    for step in _steps():
        if step.get("name") == name:
            return step
    raise AssertionError(f"step {name!r} not found in {ACTION}")


def _default_timeout_minutes() -> int:
    return int(_action()["inputs"][TIMEOUT_INPUT]["default"])


def test_composite_steps_carry_no_timeout_minutes() -> None:
    """Composite steps have no ``timeout-minutes`` (metadata syntax); the bound
    must come from inside the step, or it silently does nothing."""
    assert all("timeout-minutes" not in s for s in _steps())


def test_nix_transfer_bounds_fit_inside_the_realisation_bound() -> None:
    """One path's worst case under Nix's own retries ends before the bound."""
    attempts = int(NIX_NETWORK_SETTINGS["download-attempts"])
    per_attempt = int(NIX_NETWORK_SETTINGS["connect-timeout"]) + int(
        NIX_NETWORK_SETTINGS["stalled-download-timeout"]
    )
    assert attempts >= 2, "a single attempt turns every blip into a failure"
    assert attempts * per_attempt < _default_timeout_minutes() * 60


@pytest.mark.parametrize(("wf", "job_id", "job", "step"), CALL_SITES, ids=SITE_IDS)
def test_realisation_bound_fires_before_the_job_timeout(
    wf: str, job_id: str, job: dict, step: dict
) -> None:
    if _is_minimal(step):
        pytest.skip("minimal: no realisation to bound")
    timeout = job.get("timeout-minutes")
    assert isinstance(timeout, int), f"{wf}:{job_id} has no job timeout-minutes"
    bound = int(_with(step).get(TIMEOUT_INPUT, _default_timeout_minutes()))
    assert bound + JOB_MARGIN_MINUTES <= timeout, (
        f"{wf}:{job_id}: realisation bound {bound} min + {JOB_MARGIN_MINUTES} min "
        f"margin exceeds the job timeout {timeout} min"
    )


@pytest.mark.parametrize(("wf", "job_id", "job", "step"), CALL_SITES, ids=SITE_IDS)
def test_cache_filling_lane_bound_is_sized_to_its_job(
    wf: str, job_id: str, job: dict, step: dict
) -> None:
    """ci.yml fills the cache, so a cold build there is legitimate: its bound is
    the job timeout minus the margin, not the pull-only release-lane default."""
    if "cachix-auth-token" not in _with(step) or wf != "ci.yml":
        pytest.skip("not a cache-filling ci.yml lane")
    bound = int(_with(step)[TIMEOUT_INPUT])
    assert bound == job["timeout-minutes"] - JOB_MARGIN_MINUTES


def _write_hanging_nix(bin_dir: Path, *, hang_on: str, ignore_term: bool) -> None:
    """A fake ``nix`` that hangs on one invocation, after printing activity."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "nix"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'joined="$*"\n'
        f'if [[ "$joined" == *{hang_on!r}* ]]; then\n'
        "  echo \"building '/nix/store/aaaaaaaa-rust-1.96.0.drv'...\" >&2\n"
        + ("  trap '' TERM\n  sleep 60\n" if ignore_term else "  exec sleep 60\n")
        + "fi\n"
        'case "$joined" in\n'
        "  *PATH*) printf '%s' /nix/store/bbbbbbbb-prek-1/bin ;;\n"
        '  *"env -0 >"*) : > "${@: -1}" ;;\n'
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)


def _run_devshell(
    tmp_path: Path, bin_dir: Path, **env_overrides: str
) -> subprocess.CompletedProcess[str]:
    runner_temp = tmp_path / "runner_temp"
    runner_temp.mkdir()
    for name in ("github_env", "github_path"):
        (tmp_path / name).touch()
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GITHUB_ENV": str(tmp_path / "github_env"),
        "GITHUB_PATH": str(tmp_path / "github_path"),
        "RUNNER_TEMP": str(runner_temp),
        "DEVKIT_NIXOS_MARKER": str(tmp_path / "etc-NIXOS"),
        "DEVKIT_DEV_PROFILE_PATH": "",
        "DEVKIT_REALISATION_TIMEOUT_MINUTES": "6",
        **env_overrides,
    }
    return subprocess.run(
        ["bash", "-c", _step(DEVSHELL_STEP_NAME)["run"]],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=50,
    )


def test_devshell_step_receives_the_bound_through_the_environment() -> None:
    step = _step(DEVSHELL_STEP_NAME)
    assert step["env"]["DEVKIT_REALISATION_TIMEOUT_MINUTES"] == (
        f"${{{{ inputs.{TIMEOUT_INPUT} }}}}"
    )
    assert "${{" not in step["run"]


@pytest.mark.parametrize("ignore_term", [False, True], ids=["term", "kill"])
@pytest.mark.parametrize(
    "hang_on", ["--command true", "PATH"], ids=["profile-build", "later-eval"]
)
def test_hung_realisation_fails_with_an_explicit_error(
    tmp_path: Path, hang_on: str, ignore_term: bool
) -> None:
    """A hang anywhere in the step ends at the bound, naming cause and activity.

    ``DEVKIT_REALISATION_BUDGET_SECONDS`` is the harness-only seconds override
    (like ``DEVKIT_NIXOS_MARKER``): CI never sets it.
    """
    bin_dir = tmp_path / "bin"
    _write_hanging_nix(bin_dir, hang_on=hang_on, ignore_term=ignore_term)
    start = time.monotonic()
    proc = _run_devshell(tmp_path, bin_dir, DEVKIT_REALISATION_BUDGET_SECONDS="2")
    elapsed = time.monotonic() - start
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert elapsed < 30, f"bound did not fire ({elapsed:.1f}s)"
    assert "::error::" in out
    assert "toolchain realisation exceeded 6 min" in out
    assert "last nix activity: building '/nix/store/aaaaaaaa-rust-1.96.0.drv'" in out


def test_nix_killed_before_the_deadline_is_not_blamed_on_the_bound(
    tmp_path: Path,
) -> None:
    """A 137 well before the deadline (e.g. the OOM killer) keeps its own exit
    code instead of a misleading "realisation exceeded" diagnosis."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "nix"
    stub.write_text("#!/usr/bin/env bash\nexit 137\n", encoding="utf-8")
    stub.chmod(0o755)
    proc = _run_devshell(tmp_path, bin_dir)
    assert proc.returncode == 137, proc.stdout + proc.stderr
    assert "realisation exceeded" not in proc.stdout + proc.stderr


@pytest.mark.parametrize("value", ["", "0", "abc", "-3", "1.5"])
def test_invalid_realisation_bound_fails_loudly(tmp_path: Path, value: str) -> None:
    bin_dir = tmp_path / "bin"
    _write_hanging_nix(bin_dir, hang_on="never-matches", ignore_term=False)
    proc = _run_devshell(tmp_path, bin_dir, DEVKIT_REALISATION_TIMEOUT_MINUTES=value)
    assert proc.returncode != 0
    assert "::error::" in proc.stdout + proc.stderr
    assert TIMEOUT_INPUT in proc.stdout + proc.stderr


def test_healthy_realisation_is_unaffected(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    _write_hanging_nix(bin_dir, hang_on="never-matches", ignore_term=False)
    proc = _run_devshell(tmp_path, bin_dir)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "::error::" not in proc.stdout + proc.stderr


# ── 3. fail-soft Cachix ──────────────────────────────────────────────────────

DIRENV_INPUTS = {"mode": "direnv", "cachix-cache": "acme", MINIMAL_INPUT: "false"}


def _cachix_step() -> dict:
    return next(s for s in _steps() if s.get("id") == CACHIX_STEP_ID)


def _degradation_step() -> dict:
    matches = [
        s for s in _steps() if f"steps.{CACHIX_STEP_ID}.outcome" in str(s.get("if"))
    ]
    assert len(matches) == 1, "exactly one step must report a Cachix failure"
    return matches[0]


def test_cachix_step_failure_does_not_fail_the_job() -> None:
    step = _cachix_step()
    assert "cachix/cachix-action@" in step["uses"]
    assert step.get("continue-on-error") is True


@pytest.mark.parametrize(
    ("outcome", "expected"), [("failure", True), ("success", False)]
)
def test_cachix_degradation_is_reported_only_on_failure(
    outcome: str, expected: bool
) -> None:
    got = _if(
        _degradation_step()["if"], DIRENV_INPUTS, outcomes={CACHIX_STEP_ID: outcome}
    )
    assert got is expected


def test_realisation_proceeds_after_a_cachix_failure() -> None:
    for name in (DEVSHELL_STEP_NAME, "Verify toolchain (prek present in dev-shell)"):
        assert _if(
            _step(name)["if"], DIRENV_INPUTS, outcomes={CACHIX_STEP_ID: "failure"}
        ), f"{name} must still run when Cachix failed"


def _stub(bin_dir: Path, name: str, rc: int) -> None:
    path = bin_dir / name
    path.write_text(f"#!/bin/sh\nexit {rc}\n", encoding="utf-8")
    path.chmod(0o755)


@pytest.mark.parametrize(
    ("has_cachix", "curl_rc", "reason"),
    [
        (False, 0, "cachix binary is not available"),
        (True, 7, "https://acme.cachix.org is unreachable"),
        (True, 0, "see the Configure Cachix step log"),
    ],
    ids=["no-binary", "unreachable", "other"],
)
def test_cachix_degradation_warning_names_the_reason(
    tmp_path: Path, has_cachix: bool, curl_rc: int, reason: str
) -> None:
    step = _degradation_step()
    assert step["env"]["DEVKIT_CACHIX_CACHE"] == "${{ inputs.cachix-cache }}"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub(bin_dir, "curl", curl_rc)
    if has_cachix:
        _stub(bin_dir, "cachix", 0)
    proc = subprocess.run(
        [shutil.which("bash") or "/bin/sh", "-c", step["run"]],
        env={"PATH": str(bin_dir), "DEVKIT_CACHIX_CACHE": "acme"},
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("::warning::")
    assert "'acme'" in proc.stdout
    assert reason in proc.stdout
    assert "continuing without it" in proc.stdout


# ── 4. rollback/cleanup jobs never realise the dev-shell ─────────────────────


def _realises_or_provisions(step: dict) -> bool:
    uses = str(step.get("uses", ""))
    run = str(step.get("run", ""))
    return (
        "install-nix-action" in uses
        or "cachix-action" in uses
        or "setup-uv" in uses
        or "nix develop" in run
        or "uv tool install" in run
    )


def _running_steps(mode: str, minimal: str, has_nix: str) -> list[dict]:
    inputs = {"mode": mode, "cachix-cache": "acme", MINIMAL_INPUT: minimal}
    return [
        s for s in _steps() if _if(str(s.get("if", "true")), inputs, has_nix=has_nix)
    ]


def test_minimal_input_defaults_to_the_full_toolchain() -> None:
    spec = _action()["inputs"][MINIMAL_INPUT]
    assert str(spec["default"]).lower() == "false"


@pytest.mark.parametrize("has_nix", ["true", "false"])
@pytest.mark.parametrize("mode", [*CONTAINER_MODES, *HOST_MODES])
def test_minimal_never_realises_the_dev_shell(mode: str, has_nix: str) -> None:
    running = _running_steps(mode, "true", has_nix)
    offenders = [s.get("name") for s in running if _realises_or_provisions(s)]
    assert not offenders, f"minimal {mode} still provisions: {offenders}"
    names = {s.get("name") for s in running}
    if mode in HOST_MODES:
        assert "Install retry shell helper (host modes)" in names
    else:
        assert CONTAINER_STEP_NAME in names


def test_full_direnv_still_realises_the_dev_shell() -> None:
    names = {s.get("name") for s in _running_steps("direnv", "false", "false")}
    assert DEVSHELL_STEP_NAME in names


@pytest.mark.parametrize(("wf", "job_id", "job", "step"), CALL_SITES, ids=SITE_IDS)
def test_only_rollback_and_cleanup_jobs_are_minimal(
    wf: str, job_id: str, job: dict, step: dict
) -> None:
    assert _is_minimal(step) is ((wf, job_id) in MINIMAL_JOBS), (
        f"{wf}:{job_id}: minimal must be true exactly for the rollback/cleanup set"
    )


def _run_container_step(
    tmp_path: Path, minimal: str
) -> subprocess.CompletedProcess[str]:
    step = _step(CONTAINER_STEP_NAME)
    assert step["env"]["DEVKIT_MINIMAL"] == f"${{{{ inputs.{MINIMAL_INPUT} }}}}"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = shutil.which("git")
    assert git, "git is required for this test"
    (bin_dir / "git").symlink_to(git)
    (tmp_path / "github_env").touch()
    return subprocess.run(
        [shutil.which("bash") or "/bin/bash", "-c", step["run"]],
        cwd=tmp_path,
        env={
            "PATH": str(bin_dir),  # no prek on purpose
            "HOME": str(tmp_path),
            "GITHUB_ENV": str(tmp_path / "github_env"),
            "GITHUB_WORKSPACE": str(tmp_path),
            "DEVKIT_MINIMAL": minimal,
        },
        capture_output=True,
        text=True,
    )


def test_minimal_container_job_does_not_need_prek(tmp_path: Path) -> None:
    """A rollback in an old image must not die on the prek skew guard."""
    proc = _run_container_step(tmp_path, "true")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (tmp_path / ".gitconfig").read_text().count("safe") == 1


def test_full_container_job_keeps_the_prek_guard(tmp_path: Path) -> None:
    proc = _run_container_step(tmp_path, "false")
    assert proc.returncode == 1
    assert "'prek' not found" in proc.stdout
