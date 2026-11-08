"""Every API file commit must retain the SHA its content was computed from."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.workflow_replay import Replay

ROOT = Path(__file__).resolve().parents[1]
CALLS = []
for directory in (
    ROOT / ".github/workflows",
    ROOT / "assets/workspace/.github/workflows",
):
    for path in sorted(directory.glob("*.yml")):
        for job, config in yaml.safe_load(path.read_text()).get("jobs", {}).items():
            for step in config.get("steps", []):
                if step.get("uses", "").startswith("vig-os/commit-action@"):
                    CALLS.append((path, job, step["name"]))


def replay_for(path, job, tmp_path):
    replay = Replay(path, job, {}, cwd=tmp_path)
    # Replay only capture scripts; scheduling and container setup are external.
    for key in ("if", "timeout-minutes", "outputs", "container"):
        replay.job.pop(key, None)
    return replay


def seed_checkout(replay, capture, sha):
    """Supply actions/checkout's commit output; return False for git captures."""
    source = replay.steps[replay.steps.index(capture) - 1]
    if "actions/checkout@" not in source.get("uses", ""):
        return False
    replay.context.setdefault("steps", {})[source["id"]] = {"outputs": {"commit": sha}}
    return True


def capture_for(replay, name):
    commit = next(s for s in replay.steps if s.get("name") == name)
    expression = commit["env"].get("BASE_SHA")
    assert expression, f"{name} must pin its input revision"
    capture_id = expression.removeprefix("${{ steps.").removesuffix(".outputs.sha }}")
    capture = next(s for s in replay.steps if s.get("id") == capture_id)
    index = replay.steps.index(capture)
    checkout = replay.steps[index - 1]
    assert "checkout@" in checkout.get("uses", "") or checkout["name"] in (
        "Create sync branch from main",
        "Check out dev at its current head",
    )
    assert "set -euo pipefail" in capture["run"]
    assert replay.steps.index(capture) < replay.steps.index(commit)
    # The external checkout/branch-creation gate is supplied by the runner.
    capture.pop("if", None)
    return capture, commit


@pytest.mark.parametrize("path,job,name", CALLS)
def test_api_commit_preserves_checkout_base(tmp_path, path, job, name):
    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(tmp_path), *args], text=True
        ).strip()

    git("init", "-q")

    def commit():
        git(
            "-c",
            "user.name=Test User",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--allow-empty",
            "-qm",
            "update",
        )

    commit()
    sha = git("rev-parse", "HEAD")
    replay = replay_for(path, job, tmp_path)
    capture, api_commit = capture_for(replay, name)
    seed_checkout(replay, capture, sha)
    replay.run(only=[capture["id"]])
    commit()
    assert git("rev-parse", "HEAD") != sha
    env = replay.resolve_env(
        {"env": {"BASE_SHA": api_commit["env"]["BASE_SHA"]}},
        context={"steps": replay.step_context},
    )
    assert env["BASE_SHA"] == sha


@pytest.mark.parametrize("path,job,name", CALLS)
def test_failed_sha_capture_stops_job(tmp_path, path, job, name):
    git = tmp_path / "git"
    git.write_text("#!/bin/sh\nexit 17\n")
    git.chmod(0o755)
    replay = replay_for(path, job, tmp_path)
    replay.base_env["PATH"] = str(tmp_path) + os.pathsep + os.environ["PATH"]
    capture, _ = capture_for(replay, name)
    # An empty checkout output fails closed; git captures surface git's code.
    expected = 1 if seed_checkout(replay, capture, "") else 17
    replay.steps.append({"name": "Must not run", "run": "touch continued"})
    with pytest.raises(subprocess.CalledProcessError) as error:
        replay.run(only=[capture["id"], "Must not run"])
    assert error.value.returncode == expected
    assert replay.step_context[capture["id"]]["outputs"] == {}
    assert not (tmp_path / "continued").exists()


@pytest.mark.parametrize(
    "prefix,step_id",
    [
        (".github/workflows", "pre-state"),
        ("assets/workspace/.github/workflows", "pre_state"),
    ],
)
def test_prepare_rollback_baseline_is_checkout(tmp_path, prefix, step_id):
    replay = replay_for(ROOT / prefix / "prepare-release.yml", "prepare", tmp_path)
    replay.context = {"steps": {"checkout-state": {"outputs": {"sha": "checkout-sha"}}}}
    step = next(s for s in replay.steps if s.get("id") == step_id)
    assert replay.resolve_env(step)["PREPARE_START_SHA"] == "checkout-sha"
    replay.run(only=[step_id])
    assert (
        replay.step_context[step_id]["outputs"]["prepare_start_sha"] == "checkout-sha"
    )


def assert_capture_gate(capture, commit):
    def condition(step):
        return (
            str(step.get("if", "true")).removeprefix("${{").removesuffix("}}").strip()
        )

    capture_condition = condition(capture)
    commit_condition = condition(commit)
    # A shared conjunct is required whenever the commit can run. Requiring
    # exact conjuncts deliberately rejects unfamiliar gate shapes for review.
    assert (
        capture_condition == "true"
        or capture_condition == commit_condition
        or (
            "||" not in commit_condition
            and capture_condition in commit_condition.split(" && ")
        )
    )


def assert_capture_contract(replay, name):
    commit = next(s for s in replay.steps if s.get("name") == name)
    capture_id = commit["env"]["BASE_SHA"].split("steps.")[1].split(".outputs")[0]
    capture = next(s for s in replay.steps if s.get("id") == capture_id)
    assert_capture_gate(capture, commit)
    capture, commit = capture_for(replay, name)
    checkout = replay.steps[replay.steps.index(capture) - 1]
    target = commit["env"]["TARGET_BRANCH"].removeprefix("refs/heads/")
    source = checkout.get("with", {}).get("ref")
    if checkout["name"] == "Check out dev at its current head":
        assert "git checkout --detach origin/dev" in checkout["run"]
        source = "dev"
    elif checkout["name"] == "Create sync branch from main":
        assert 'git checkout -b "${SYNC_BRANCH}" origin/main' in checkout["run"]
        source = "${{ env.SYNC_BRANCH }}"
    elif replay.workflow["name"] == "Prepare Hotfix":
        target = "main"  # New release branch is created from validated main.
    elif target.startswith("chore/update-nixpkgs"):
        target = "dev"  # Chore branch is created/reset at the dev checkout.
    assert source == target, (source, target)


@pytest.mark.parametrize("path,job,name", CALLS)
def test_capture_matches_target_and_cannot_be_narrowed(tmp_path, path, job, name):
    replay = replay_for(path, job, tmp_path)
    assert_capture_contract(replay, name)


def test_wrong_extension_capture_mutant_is_rejected(tmp_path):
    replay = replay_for(
        ROOT / ".github/workflows/prepare-release-extension.yml",
        "sync-manifest",
        tmp_path,
    )
    name = "Commit reconciled mirror to dev via API"
    commit = next(s for s in replay.steps if s.get("name") == name)
    commit["env"]["BASE_SHA"] = "${{ steps.checkout-state.outputs.sha }}"
    with pytest.raises(AssertionError):
        assert_capture_contract(replay, name)


@pytest.mark.parametrize("path,job,name", CALLS)
def test_narrowed_capture_mutant_is_rejected(tmp_path, path, job, name):
    replay = replay_for(path, job, tmp_path)
    capture, commit = capture_for(replay, name)
    capture["if"] = "false"
    replay.run(only=[capture["id"]])
    assert replay.step_context[capture["id"]]["outcome"] == "skipped"
    assert (
        replay.resolve_env(
            {"env": {"BASE_SHA": commit["env"]["BASE_SHA"]}},
            context={"steps": replay.step_context},
        )["BASE_SHA"]
        == ""
    )
    with pytest.raises(AssertionError):
        assert_capture_contract(replay, name)


def guard_for(replay, name):
    commit = next(s for s in replay.steps if s.get("name") == name)
    guard = replay.steps[replay.steps.index(commit) - 1]
    assert guard["name"].startswith("Require pinned commit base for ")
    assert guard["env"]["BASE_SHA"] == commit["env"]["BASE_SHA"]
    assert guard.get("if") == commit.get("if")
    return guard


@pytest.mark.parametrize("path,job,name", CALLS)
@pytest.mark.parametrize("sha", ["", "checkout-sha"])
def test_runtime_commit_base_guard(tmp_path, path, job, name, sha):
    replay = replay_for(path, job, tmp_path)
    guard = guard_for(replay, name)
    capture_id = guard["env"]["BASE_SHA"].split("steps.")[1].split(".outputs")[0]
    replay.context = {"steps": {capture_id: {"outputs": {"sha": sha}}}}
    guard.pop("if", None)  # Exercise the run body whenever its commit is eligible.
    replay.steps.append({"name": "API boundary", "run": "touch api-reached"})
    if sha:
        replay.run(only=[guard["name"], "API boundary"])
        assert (tmp_path / "api-reached").exists()
    else:
        with pytest.raises(subprocess.CalledProcessError) as error:
            replay.run(only=[guard["name"], "API boundary"])
        assert error.value.returncode == 1
        assert "::error::" in error.value.stdout
        assert not (tmp_path / "api-reached").exists()


@pytest.mark.parametrize(
    "prefix", [".github/workflows", "assets/workspace/.github/workflows"]
)
def test_sync_issues_future_output_capture_mutant_fails_at_runtime(tmp_path, prefix):
    replay = replay_for(ROOT / prefix / "sync-issues.yml", "sync", tmp_path)
    name = "Commit and push changes via API"
    guard = guard_for(replay, name)
    capture, _ = capture_for(replay, name)
    capture["if"] = "steps.sync.outputs.modified-files != ''"
    replay.run(only=[capture["id"]])
    assert replay.step_context[capture["id"]]["outcome"] == "skipped"
    replay.context = {
        "steps": {
            **replay.step_context,
            "sync": {"outputs": {"modified-files": "docs/issues/1.md"}},
        }
    }
    with pytest.raises(subprocess.CalledProcessError) as error:
        replay.run(only=[guard["name"]])
    assert error.value.returncode == 1
    assert "::error::" in error.value.stdout
