"""Container-mode consumers opt in to ``CI_RUNNER_*`` runners (#2045).

``vars.CI_RUNNER_*`` also resolves organization-level variables, and an
expression cannot tell an inherited organization variable from a repository
one. In the container-ish modes (``devcontainer``, ``both``) every lane that
runs a ``container:`` job, or ``docker run``s on the host, needs a container
runtime on the runner, and an inherited variable cannot prove its pool has
one. So ``resolve-toolchain`` places those modes' lanes on ``CI_RUNNER_*``
only when ``.vig-os`` says ``DEVKIT_CI_CONTAINER_RUNNERS=true``; otherwise
every lane stays on the hosted default, as in 1.18.x. ``direnv`` and ``bare``
are unchanged, and the fork predicate still wins.

The matrix tests execute the action's real Bash. The static scan pins that
every job needing a container runtime takes its runner from the gated
resolver output, so a future lane cannot bypass the gate.

Refs: #2045
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import pytest
import yaml

from tests.workflow_scaffold import (
    WORKFLOWS,
    load_workflow,
    needs_of,
    run_text_of_job,
)
from tests.workflow_scaffold import (
    exec_resolve_toolchain as _exec_resolve,
)

if TYPE_CHECKING:
    from pathlib import Path

HOSTED = "ubuntu-26.04"
KEY = "DEVKIT_CI_CONTAINER_RUNNERS"
CLASSES = ("small", "large", "xlarge")
LANES = ("lint", "test", "extension", "release-test")
MODES = ("devcontainer", "both", "direnv", "bare")
CONTAINER_MODES = ("devcontainer", "both")
POOLS = {"small": "self-hosted-small", "large": "self-hosted-large"}
POOLS["xlarge"] = "self-hosted-xlarge"
MIGRATION_ANCHOR = "MIGRATION.md#container-mode-ci-runners"


def _manifest(mode: str, key: str | None, extra: str = "") -> str:
    text = f"DEVKIT_MODE={mode}\nDEVKIT_VERSION=1.2.3\n"
    if key is not None:
        text += f"{KEY}={key}\n"
    return text + extra


def _set_vars(monkeypatch: pytest.MonkeyPatch, visible: bool) -> None:
    for size in CLASSES:
        monkeypatch.setenv("RUNNER_" + size.upper(), POOLS[size] if visible else "")


def _set_pr(monkeypatch: pytest.MonkeyPatch, *, fork: bool) -> None:
    """Bind the action's fork-predicate env exactly as its step env maps it."""
    head = "example/fork" if fork else "example/project"
    monkeypatch.setenv("PR_PRESENT", "true")
    monkeypatch.setenv("HEAD_REPO_FORK", str(fork).lower())
    monkeypatch.setenv("HEAD_REPOSITORY", head)
    monkeypatch.setenv("BASE_REPOSITORY", "example/project")


def _gated(mode: str, key: str | None) -> bool:
    return mode in CONTAINER_MODES and key != "true"


# ── Resolver matrix ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("fork", [False, True], ids=["same-repo", "fork"])
@pytest.mark.parametrize("visible", [False, True], ids=["vars-unset", "vars-set"])
@pytest.mark.parametrize(
    "key", [None, "true", "false"], ids=["absent", "true", "false"]
)
@pytest.mark.parametrize("mode", MODES)
def test_lane_placement_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    key: str | None,
    visible: bool,
    fork: bool,
) -> None:
    """Every class and lane follows mode × key × variables × fork."""
    _set_vars(monkeypatch, visible)
    _set_pr(monkeypatch, fork=fork)
    proc, outputs = _exec_resolve(tmp_path, _manifest(mode, key))
    assert proc.returncode == 0, proc.stdout + proc.stderr

    runners = json.loads(outputs["runners"])
    sources = json.loads(outputs["runner-sources"])
    placed = visible and not fork and not _gated(mode, key)
    for size in CLASSES:
        assert runners[size] == ([POOLS[size]] if placed else [HOSTED]), size
        expected = "fork" if fork else ("variable" if placed else "default")
        assert sources[size] == expected, size
    for lane in LANES:
        assert runners[lane] == runners["small"], lane
    assert json.loads(outputs["runner-json"]) == runners["small"]

    notices = [line for line in proc.stdout.splitlines() if KEY in line]
    assert bool(notices) == (_gated(mode, key) and visible and not fork)


@pytest.mark.parametrize("value", ["yes", "True", "1", "on", "false,true", "maybe"])
@pytest.mark.parametrize("visible", [False, True], ids=["vars-unset", "vars-set"])
@pytest.mark.parametrize("fork", [False, True], ids=["same-repo", "fork"])
@pytest.mark.parametrize("mode", MODES)
def test_invalid_value_fails_in_every_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    fork: bool,
    visible: bool,
    value: str,
) -> None:
    """Anything but true/false/empty is a loud error, never a silent default."""
    _set_vars(monkeypatch, visible)
    _set_pr(monkeypatch, fork=fork)
    proc, outputs = _exec_resolve(tmp_path, _manifest(mode, value))
    assert proc.returncode == 1
    error = next(line for line in proc.stdout.splitlines() if "::error::" in line)
    assert f"Invalid {KEY}" in error
    assert "true | false" in error
    assert "runners" not in outputs


@pytest.mark.parametrize("quoted", ['"true"', "'true'", " true "])
def test_value_parses_like_every_other_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quoted: str
) -> None:
    """Quotes and surrounding whitespace follow the shared KEY=VALUE parser."""
    _set_vars(monkeypatch, True)
    proc, outputs = _exec_resolve(tmp_path, _manifest("both", quoted))
    assert proc.returncode == 0, proc.stdout
    assert json.loads(outputs["runners"])["small"] == [POOLS["small"]]


def test_empty_value_is_the_default(tmp_path, monkeypatch) -> None:
    _set_vars(monkeypatch, True)
    proc, outputs = _exec_resolve(tmp_path, _manifest("both", ""))
    assert proc.returncode == 0, proc.stdout
    assert json.loads(outputs["runners"])["small"] == [HOSTED]


# ── The notice ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("mode", CONTAINER_MODES)
def test_gate_notice_names_the_key_and_why(tmp_path, monkeypatch, mode) -> None:
    _set_vars(monkeypatch, True)
    proc, _ = _exec_resolve(tmp_path, _manifest(mode, None))
    notices = [line for line in proc.stdout.splitlines() if KEY in line]
    assert len(notices) == 1
    notice = notices[0]
    assert notice.startswith("::notice::")
    for text in (
        "CI_RUNNER_*",
        f"DEVKIT_MODE={mode}",
        f"{KEY}=true",
        ".vig-os",
        "container runtime",
        "organization variable",
        MIGRATION_ANCHOR,
    ):
        assert text in notice, text
    # Diagnostics name variables, never their values.
    assert not any(pool in proc.stdout for pool in POOLS.values())


def test_gated_run_drops_placement_diagnostics(tmp_path, monkeypatch) -> None:
    """Partial-setup and opted-in-class hints are about placement, which is off."""
    monkeypatch.setenv("RUNNER_SMALL", POOLS["small"])
    proc, outputs = _exec_resolve(
        tmp_path, _manifest("both", None, "DEVKIT_CI_LANE_SIZES=test=large\n")
    )
    assert proc.returncode == 0, proc.stdout
    assert "::warning::" not in proc.stdout
    assert "Partial CI runner setup" not in proc.stdout
    assert all(v == [HOSTED] for v in json.loads(outputs["runners"]).values())


def test_gated_run_still_validates_lane_sizes(tmp_path, monkeypatch) -> None:
    """Ignoring the override for placement never hides a manifest typo."""
    proc, _ = _exec_resolve(
        tmp_path, _manifest("both", None, "DEVKIT_CI_LANE_SIZES=test=huge\n")
    )
    assert proc.returncode == 1
    assert "DEVKIT_CI_LANE_SIZES" in proc.stdout


def test_gated_run_still_validates_variables(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RUNNER_LARGE", "a,b")
    proc, _ = _exec_resolve(tmp_path, _manifest("both", None))
    assert proc.returncode == 1
    assert "::error::Invalid CI_RUNNER_LARGE" in proc.stdout


@pytest.mark.parametrize("key", [None, "true"], ids=["gated", "opted-in"])
def test_private_repo_notice_names_the_key_when_gated(tmp_path, monkeypatch, key):
    """The private-repo hint must not send a gated repo down a dead end."""
    monkeypatch.setenv("REPOSITORY_PRIVATE", "true")
    proc, _ = _exec_resolve(tmp_path, _manifest("both", key))
    notice = next(
        line
        for line in proc.stdout.splitlines()
        if "::notice::CI runs on hosted" in line
    )
    assert (f"{KEY}=true" in notice) == (key is None)


@pytest.mark.parametrize("mode", ["direnv", "bare"])
def test_host_modes_ignore_the_key(tmp_path, monkeypatch, mode) -> None:
    _set_vars(monkeypatch, True)
    for key in (None, "false", "true"):
        proc, outputs = _exec_resolve(tmp_path, _manifest(mode, key))
        assert proc.returncode == 0, proc.stdout
        assert json.loads(outputs["runners"])["test"] == [POOLS["small"]]
        assert KEY not in proc.stdout


# ── Legacy key: 1.18.x parity ─────────────────────────────────────────────────


@pytest.mark.parametrize("visible", [False, True], ids=["vars-unset", "vars-set"])
@pytest.mark.parametrize("mode", CONTAINER_MODES)
def test_gated_legacy_key_keeps_its_1_18_runners(
    tmp_path, monkeypatch, mode, visible
) -> None:
    """DEVKIT_CI_RUNNER is a repo statement that 1.18.x already honoured.

    The gate ignores inherited variables, not the repo's own legacy key, so a
    container-mode repo that ran self-hosted in 1.18.x keeps those runners.
    Its migration text must say the variables need the opt-in key too, or
    following it would move the repo onto hosted runners.
    """
    _set_vars(monkeypatch, visible)
    proc, outputs = _exec_resolve(
        tmp_path, _manifest(mode, None, "DEVKIT_CI_RUNNER=legacy-pool\n")
    )
    assert proc.returncode == 0, proc.stdout
    runners = json.loads(outputs["runners"])
    assert all(runners[size] == ["legacy-pool"] for size in (*CLASSES, *LANES))
    assert set(json.loads(outputs["runner-sources"]).values()) == {"legacy-key"}
    migration = next(
        line
        for line in proc.stdout.splitlines()
        if line.startswith("::warning::DEVKIT_CI_RUNNER is deprecated")
    )
    assert f"{KEY}=true" in migration
    # A visible variable is not "unset": the text names only what is missing.
    unset_hint = "gh variable set CI_RUNNER_SMALL --body <label>"
    assert (unset_hint in migration) == (not visible)
    assert ("Unset required class" in migration) == (not visible)
    assert "already overrides" not in migration
    assert "the key decides nothing" not in migration
    assert "legacy-pool" not in proc.stdout


def test_opted_in_legacy_migration_is_unchanged(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RUNNER_SMALL", POOLS["small"])
    proc, outputs = _exec_resolve(
        tmp_path, _manifest("both", "true", "DEVKIT_CI_RUNNER=legacy-pool\n")
    )
    assert json.loads(outputs["runners"])["small"] == [POOLS["small"]]
    migration = next(line for line in proc.stdout.splitlines() if "deprecated" in line)
    assert "CI_RUNNER_SMALL already overrides the key" in migration
    assert KEY not in migration


# ── Static scan: no container lane bypasses the gate ──────────────────────────

# A job needs a container runtime on its runner when it declares `container:`,
# or a step talks to a daemon / runs the installer (which pulls the image in
# every mode but direnv).
_RUNTIME_RE = re.compile(
    r"\b(?:docker|podman)\s+(?:run|pull|create|exec|build|compose|load)\b"
    r"|\bdocker-compose\b|\binstall\.sh\b"
)
_RESOLVER_LANE_RE = re.compile(
    r"^\$\{\{ fromJSON\(needs\.(?P<job>[a-z-]+)\.outputs\.runners\)"
    r"(?:\.[a-z]+|\['[a-z-]+'\]) \}\}$"
)
_INPUT_LANE_RE = re.compile(
    r"^\$\{\{ fromJSON\(inputs\.runners\)(?:\.[a-z]+|\['[a-z-]+'\]) \}\}$"
)


def _is_resolver(job: dict) -> bool:
    return any(
        str(step.get("uses", "")).endswith("/resolve-toolchain")
        for step in job.get("steps", [])
    )


def _needs_runtime(job: dict) -> bool:
    if "container" in job:
        return True
    for step in job.get("steps", []):
        uses = str(step.get("uses", ""))
        # A container action (`docker://…`) or a docker/* action drives the
        # daemon without any `run:` text.
        if uses.startswith(("docker://", "docker/")):
            return True
    return bool(_RUNTIME_RE.search(run_text_of_job(job)))


@pytest.mark.parametrize(
    "job",
    [
        {"container": {"image": "x"}},
        {"steps": [{"run": "docker run --rm img true"}]},
        {"steps": [{"run": "docker compose up -d"}]},
        {"steps": [{"run": "curl -sSfL x/install.sh | bash"}]},
        {"steps": [{"uses": "docker://alpine:3"}]},
        {"steps": [{"uses": "docker/login-action@0123"}]},
    ],
    ids=[
        "container",
        "docker-run",
        "compose",
        "installer",
        "docker-uses",
        "docker-action",
    ],
)
def test_runtime_predicate_catches_every_daemon_shape(job: dict) -> None:
    assert _needs_runtime(job)


def test_runtime_predicate_ignores_shell_only_jobs() -> None:
    assert not _needs_runtime(
        {"steps": [{"run": "gh pr list"}, {"uses": "actions/checkout@0"}]}
    )


@pytest.mark.parametrize(
    "job",
    [
        {"services": {"db": {"image": "postgres:17"}}},
        {"steps": [{"run": "docker buildx build --push ."}]},
        {"steps": [{"run": "docker info"}]},
        {"steps": [{"run": "docker push ghcr.io/example/img:1"}]},
        {"steps": [{"run": "set -e\npodman image ls"}]},
    ],
    ids=["services", "buildx", "docker-info", "docker-push", "podman-image"],
)
def test_runtime_predicate_catches_any_cli_subcommand(job: dict) -> None:
    """Mutation guard: every daemon/CLI shape the run text can take is caught."""
    assert _needs_runtime(job)


def _composite(root: Path, name: str, steps: list[dict]) -> str:
    action = root / ".github" / "actions" / name / "action.yml"
    action.parent.mkdir(parents=True)
    action.write_text(
        yaml.safe_dump({"runs": {"using": "composite", "steps": steps}}),
        encoding="utf-8",
    )
    return f"./.github/actions/{name}"


@pytest.mark.parametrize(
    "steps",
    [
        [{"shell": "bash", "run": "docker info"}],
        [{"shell": "bash", "run": "docker manifest inspect img"}],
        [{"uses": "docker/setup-buildx-action@0123"}],
    ],
    ids=["run-cli", "registry-probe", "docker-action"],
)
def test_runtime_predicate_resolves_local_composites(
    tmp_path: Path, steps: list[dict]
) -> None:
    """A local composite action's own steps count as the calling job's."""
    uses = _composite(tmp_path, "probe", steps)
    assert _needs_runtime({"steps": [{"uses": uses}]}, root=tmp_path)


def test_runtime_predicate_passes_shell_only_composites(tmp_path: Path) -> None:
    uses = _composite(tmp_path, "shell", [{"shell": "bash", "run": "gh pr list"}])
    assert not _needs_runtime({"steps": [{"uses": uses}]}, root=tmp_path)


def test_runtime_predicate_ignores_comments() -> None:
    """Prose about docker in a comment is not an invocation."""
    assert not _needs_runtime(
        {"steps": [{"run": "# docker is present on hosted runners\ngh pr list"}]}
    )


def _callers(workflow: str) -> list[tuple[str, str, dict, dict]]:
    """Every (caller file, job id, job, caller jobs) that `uses:` this workflow."""
    found = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        jobs = load_workflow(path).get("jobs") or {}
        for name, job in jobs.items():
            if job.get("uses") == f"./.github/workflows/{workflow}":
                found.append((path.name, name, job, jobs))
    return found


def _assert_gated(workflow: str, name: str, job: dict, jobs: dict) -> None:
    expr = job["runs-on"]
    lane = _RESOLVER_LANE_RE.match(expr)
    if lane:
        producer = lane["job"]
        assert producer in needs_of(job), (workflow, name)
        assert _is_resolver(jobs[producer]), (workflow, name, producer)
        return
    if _INPUT_LANE_RE.match(expr):
        callers = _callers(workflow)
        assert callers, (workflow, name)
        for caller, caller_job, call, caller_jobs in callers:
            passed = call["with"]["runners"]
            producer = re.fullmatch(
                r"\$\{\{ needs\.([a-z-]+)\.outputs\.runners \}\}", passed
            )
            assert producer, (caller, caller_job, passed)
            assert producer[1] in needs_of(call), (caller, caller_job)
            assert _is_resolver(caller_jobs[producer[1]]), (caller, caller_job)
        return
    pytest.fail(
        f"{workflow} job {name!r} needs a container runtime but runs on {expr!r}, "
        "not on the gated resolve-toolchain `runners` output (#2045)"
    )


CONTAINER_JOBS = sorted(
    (path.name, name)
    for path in WORKFLOWS.glob("*.yml")
    for name, job in (load_workflow(path).get("jobs") or {}).items()
    if "runs-on" in job and job["runs-on"] != HOSTED and _needs_runtime(job)
)


def test_container_job_scan_finds_the_known_lanes() -> None:
    """The scan is not vacuous: it sees the lanes the #2045 audit lists."""
    assert {
        ("ci.yml", "lint"),
        ("ci.yml", "test"),
        ("ci.yml", "commit-checks"),
        ("ci.yml", "scaffold-drift"),
        ("devkit-upgrade.yml", "upgrade"),
        ("release-core.yml", "test"),
        ("release-publish.yml", "publish"),
        ("sync-issues.yml", "sync"),
    } <= set(CONTAINER_JOBS)


@pytest.mark.parametrize(("workflow", "name"), CONTAINER_JOBS)
def test_container_jobs_take_the_gated_runner(workflow: str, name: str) -> None:
    jobs = load_workflow(WORKFLOWS / workflow)["jobs"]
    _assert_gated(workflow, name, jobs[name], jobs)


def test_ci_extension_receives_the_gated_lane() -> None:
    """ci-extension's stock hook needs no runtime, but a consumer's may."""
    call = load_workflow(WORKFLOWS / "ci.yml")["jobs"]["extension"]
    assert call["with"]["runner-json"] == (
        "${{ toJSON(fromJSON(needs.resolve-toolchain.outputs.runners).extension) }}"
    )
    assert "resolve-toolchain" in needs_of(call)


# ── devkit-upgrade routes the installer through the resolver ──────────────────


def test_devkit_upgrade_resolves_before_installing() -> None:
    """install.sh --docker needs a daemon, so the upgrade lane is gated too."""
    jobs = load_workflow(WORKFLOWS / "devkit-upgrade.yml")["jobs"]
    resolve = jobs["resolve-toolchain"]
    assert _is_resolver(resolve)
    step = next(s for s in resolve["steps"] if s.get("id") == "resolve")
    for size in CLASSES:
        assert (
            step["with"]["runner-" + size]
            == f"${{{{ vars.CI_RUNNER_{size.upper()} }}}}"
        )
    assert resolve["outputs"]["runners"] == "${{ steps.resolve.outputs.runners }}"
    # The gate reads the same branch the upgrade rewrites (dev, or main once
    # the trunk retarget rewrites every `ref: dev` line), never the default
    # branch's possibly different DEVKIT_MODE.
    upgrade = jobs["upgrade"]
    base = next(s for s in upgrade["steps"] if s.get("name") == "Checkout base branch")
    checkout = next(
        s for s in resolve["steps"] if "actions/checkout" in str(s.get("uses"))
    )
    assert checkout["with"]["ref"] == base["with"]["ref"] == "dev"
    assert needs_of(upgrade) == ["resolve-toolchain"]
    assert upgrade["runs-on"] == (
        "${{ fromJSON(needs.resolve-toolchain.outputs.runners).small }}"
    )


def test_devkit_upgrade_reports_a_failed_resolve() -> None:
    """A resolve failure (e.g. an invalid key) still files the tracking issue."""
    report = load_workflow(WORKFLOWS / "devkit-upgrade.yml")["jobs"]["report"]
    assert needs_of(report) == ["resolve-toolchain", "upgrade"]
    assert "needs.resolve-toolchain.result == 'failure'" in report["if"]
    filing = next(s for s in report["steps"] if s["name"].startswith("File or update"))
    assert filing["if"] == (
        "needs.upgrade.result == 'failure' || needs.resolve-toolchain.result == 'failure'"
    )
