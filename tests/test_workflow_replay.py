"""Runner contracts used by replay tests:
https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#environment-files
https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepsshell
https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#context-availability
"""

import json
import subprocess
import sys

import pytest
import yaml

from tests.workflow_replay import Replay


def workflow(tmp_path, steps, **job):
    path = tmp_path / "workflow.yml"
    path.write_text(yaml.safe_dump({"jobs": {"test": {**job, "steps": steps}}}))
    return path


def test_isolation_propagation_and_precedence(tmp_path):
    path = workflow(
        tmp_path,
        [
            {
                "id": "first",
                "env": {"BASE": "step"},
                "run": """
private=hidden
printf 'value<<END\none\ntwo\nEND\n' >> "$GITHUB_OUTPUT"
printf 'LATER<<END\nthree\nfour\nEND\n' >> "$GITHUB_ENV"
test "${LATER-unset}" = unset
printf '%s' "$BASE" >> "$GITHUB_STEP_SUMMARY"
""",
            },
            {
                "id": "second",
                "env": {"PREVIOUS": "${{ steps.first.outputs.value }}"},
                "run": """
test "${private-unset}" = unset
test "${HOST_SECRET-unset}" = unset
test "$BASE" = job
printf '%s|%s' "$PREVIOUS" "$LATER"
""",
            },
        ],
        env={"BASE": "job"},
    )
    replay = Replay(path, "test", {}, cwd=tmp_path)
    result = replay.run()
    assert result[0]["summary"] == "step"
    assert result[0]["outputs"] == {"value": "one\ntwo"}
    assert result[1]["stdout"] == "one\ntwo|three\nfour"


def test_conditions_and_mutation(tmp_path):
    path = workflow(
        tmp_path,
        [
            {"id": "skip", "if": "inputs.enabled", "run": "exit 99"},
            {
                "id": "base",
                "env": {"BASE": "dev", "FLAG": "${{ true }}"},
                "if": "${{ github.event_name == 'push' }}",
                "run": 'printf "%s:%s" "$BASE" "$FLAG"',
            },
        ],
    )
    context = {"inputs": {"enabled": False}, "github": {"event_name": "push"}}
    assert Replay(path, "test", context).run()[1]["stdout"] == "dev:true"
    path.write_text(path.read_text().replace("BASE: dev", "BASE: main"))
    assert Replay(path, "test", context).run()[1]["stdout"] == "main:true"


@pytest.mark.parametrize(
    "step",
    [
        {"uses": "actions/checkout@v4"},
        {"uses": "./local-action"},
        {"run": "true", "shell": "python"},
        {"run": "true", "continue-on-error": True},
        {"run": "true", "if": "success()"},
    ],
)
def test_unsupported(tmp_path, step):
    with pytest.raises(ValueError):
        Replay(workflow(tmp_path, [step]), "test", {}).run()


def test_shell_failure_and_defaults(tmp_path):
    path = workflow(
        tmp_path, [{"run": "false | true"}], defaults={"run": {"shell": "bash"}}
    )
    with pytest.raises(subprocess.CalledProcessError) as error:
        Replay(path, "test", {}).run()
    assert error.value.returncode == 1


@pytest.mark.parametrize("command", ["echo broken", "printf 'x<<END\\nmissing\\n'"])
def test_malformed_files(tmp_path, command):
    path = workflow(tmp_path, [{"run": command + ' >> "$GITHUB_OUTPUT"'}])
    with pytest.raises(ValueError, match="environment file"):
        Replay(path, "test", {}).run()


def test_real_pre_n_env_and_selection(tmp_path):
    tag = subprocess.run(
        ["git", "show", "1.18.0:assets/workspace/.github/workflows/devkit-upgrade.yml"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert tag.returncode == 0, (
        "Required tag 1.18.0 missing: git fetch --depth=1 origin tag 1.18.0"
    )
    path = tmp_path / "pre-n.yml"
    path.write_text(tag.stdout)
    context = {
        "steps": {
            "resolve": {"outputs": {"target": "1.19.0"}},
            "upgrade": {"outputs": {"hook-drift": "a\nb"}},
        }
    }
    replay = Replay(path, "upgrade", context)
    upgrade = next(s for s in replay.steps if s.get("id") == "upgrade")
    body = next(
        s for s in replay.steps if s.get("name") == "Open or update the adoption PR"
    )
    assert replay.resolve_env(upgrade)["TARGET"] == "1.19.0"
    assert replay.resolve_env(body)["HOOK_DRIFT"] == "a\nb"
    assert replay.resolve_env(body)["BASE"] == "dev"
    # Explicit selection permits boundary adapters without silently skipping uses.
    path = workflow(
        tmp_path,
        [{"uses": "actions/checkout@v4"}, {"id": "local", "run": "echo local"}],
    )
    assert Replay(path, "test", {}).run(only=["local"])[0]["stdout"] == "local\n"
    with pytest.raises(ValueError, match="Unknown step"):
        Replay(path, "test", {}).run(only=["typo"])


def test_cli(tmp_path):
    path = workflow(
        tmp_path,
        [{"run": 'cat "$GITHUB_EVENT_PATH"; echo summary >> "$GITHUB_STEP_SUMMARY"'}],
    )
    context = tmp_path / "context.json"
    context.write_text(json.dumps({"github": {"event": {"action": "test"}}}))
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.workflow_replay",
            str(path),
            "test",
            "--context",
            str(context),
            "--cwd",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(json.loads(process.stdout)[0]["stdout"]) == {"action": "test"}
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.workflow_replay",
            str(path),
            "absent",
            "--context",
            str(context),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 2
