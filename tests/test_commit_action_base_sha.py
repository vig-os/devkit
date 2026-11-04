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
    replay.steps.append({"name": "Must not run", "run": "touch continued"})
    with pytest.raises(subprocess.CalledProcessError) as error:
        replay.run(only=[capture["id"], "Must not run"])
    assert error.value.returncode == 17
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


def assert_capture_contract(replay, name):
    commit = next(s for s in replay.steps if s.get("name") == name)
    capture_id = commit["env"]["BASE_SHA"].split("steps.")[1].split(".outputs")[0]
    capture = next(s for s in replay.steps if s.get("id") == capture_id)
    assert "if" not in capture
    capture, commit = capture_for(replay, name)
    checkout = replay.steps[replay.steps.index(capture) - 1]
    target = commit["env"]["TARGET_BRANCH"].removeprefix("refs/heads/")
    source = checkout.get("with", {}).get("ref")
    if checkout["name"] == "Check out dev at its current head":
        source = "dev"
    elif checkout["name"] == "Create sync branch from main":
        source = "${{ env.SYNC_BRANCH }}"
    elif replay.workflow["name"] == "Prepare Hotfix":
        target = "main"  # New release branch is created from validated main.
    elif target.startswith("chore/update-nixpkgs"):
        target = "dev"  # Chore branch is created/reset at the dev checkout.
    assert source == target, (source, target)


@pytest.mark.parametrize("path,job,name", CALLS)
def test_capture_matches_target_and_cannot_be_narrowed(tmp_path, path, job, name):
    replay = replay_for(path, job, tmp_path)
    # Capture is unconditional within the job: a later commit gate cannot
    # allow an API write after this capture was skipped.
    commit = next(s for s in replay.steps if s.get("name") == name)
    capture_id = commit["env"]["BASE_SHA"].split("steps.")[1].split(".outputs")[0]
    capture = next(s for s in replay.steps if s.get("id") == capture_id)
    assert "if" not in capture
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


def test_narrowed_capture_mutant_is_rejected(tmp_path):
    path, job, name = CALLS[0]
    replay = replay_for(path, job, tmp_path)
    capture, _ = capture_for(replay, name)
    capture["if"] = "false"
    replay.run(only=[capture["id"]])
    assert replay.step_context[capture["id"]]["outcome"] == "skipped"
    with pytest.raises(AssertionError):
        assert_capture_contract(replay, name)
