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


def test_isolation_propagation_and_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("HOST_SECRET", "must-not-leak")
    path = workflow(
        tmp_path,
        [
            {
                "id": "first",
                "env": {"BASE": "step"},
                "run": """
private=hidden
printf 'plain=scalar\nvalue<<END\none\ntwo\nEND\n' >> "$GITHUB_OUTPUT"
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
    assert result[0]["outputs"] == {"plain": "scalar", "value": "one\ntwo"}
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


@pytest.mark.parametrize("job, expected", [("test", 0), ("absent", 2)])
def test_cli(tmp_path, job, expected):
    path = workflow(
        tmp_path,
        [{"run": 'cat "$GITHUB_EVENT_PATH"; echo summary >> "$GITHUB_STEP_SUMMARY"'}],
    )
    context = tmp_path / "context.json"
    context.write_text(json.dumps({"github": {"event": {"action": "test"}}}))
    command = [sys.executable, "-m", "tests.workflow_replay", str(path), job]
    command += ["--context", str(context), "--cwd", str(tmp_path)]
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == expected, process.stderr
    if expected == 0:
        assert json.loads(json.loads(process.stdout)[0]["stdout"]) == {"action": "test"}


# ScriptHandler.cs / ScriptHandlerHelpers.cs: implicit sh arguments vs explicit bash.
# https://github.com/actions/runner/tree/main/src/Runner.Worker/Handlers
@pytest.mark.parametrize("source", ["implicit", "step", "job", "workflow"])
def test_shell_defaults(tmp_path, source):
    step = {"run": "false | true; echo reached"}
    path = workflow(tmp_path, [step])
    doc = yaml.safe_load(path.read_text())
    target = {"step": step, "job": doc["jobs"]["test"], "workflow": doc}.get(source)
    if source == "step":
        doc["jobs"]["test"]["steps"][0]["shell"] = "bash"
    elif target is not None:
        target["defaults"] = {"run": {"shell": "bash"}}
    path.write_text(yaml.safe_dump(doc))
    if source == "implicit":
        assert Replay(path, "test", {}).run()[0]["stdout"] == "reached\n"
    else:
        with pytest.raises(subprocess.CalledProcessError):
            Replay(path, "test", {}).run()


# StepsRunner.cs merges step env before EvaluateStepIf and records CompleteStep results.
# https://github.com/actions/runner/blob/main/src/Runner.Worker/StepsRunner.cs
@pytest.mark.parametrize(
    "condition, result", [("true", "success"), ("false", "skipped")]
)
def test_step_results_replace_seeds(tmp_path, condition, result):
    steps = [
        {"id": "a", "if": condition, "run": "true", "env": {"OWN": "visible"}},
        {
            "if": f"steps.a.outcome == '{result}' && steps.a.conclusion == '{result}' && !steps.a.outputs.old",
            "run": "echo checked",
        },
        {
            "env": {"OWN": "visible"},
            "if": "env.OWN == 'visible'",
            "run": "echo own-env",
        },
    ]
    replay = Replay(
        workflow(tmp_path, steps),
        "test",
        {"steps": {"a": {"outputs": {"old": "stale"}}}},
    )
    records = replay.run()
    assert records[1]["stdout"] == "checked\n"
    assert records[2]["stdout"] == "own-env\n"
    assert replay.step_context["a"] == {
        "outputs": {},
        "outcome": result,
        "conclusion": result,
    }


def test_failed_step_result(tmp_path):
    replay = Replay(workflow(tmp_path, [{"id": "a", "run": "exit 7"}]), "test", {})
    with pytest.raises(subprocess.CalledProcessError):
        replay.run()
    assert replay.step_context["a"] == {
        "outputs": {},
        "outcome": "failure",
        "conclusion": "failure",
    }


# EnvFileKeyValuePairs.ReadLine has Windows-only CRLF handling.
# https://github.com/actions/runner/blob/main/src/Runner.Worker/FileCommandManager.cs
@pytest.mark.parametrize(
    "data, expected",
    [
        (b"x<<E\na\rb\nE\n", "a\rb"),
        (b"x=a\rb\n", "a\rb"),
        (b"x=1\r\n", "1\r"),
        (b"x=\xff\n", None),
    ],
)
def test_linux_command_bytes(tmp_path, data, expected):
    from tests.workflow_replay import _file_values

    path = tmp_path / "output"
    path.write_bytes(data)
    if expected is None:
        with pytest.raises(UnicodeDecodeError):
            _file_values(path)
    else:
        assert _file_values(path) == {"x": expected}


@pytest.mark.parametrize(
    "field",
    [
        "if",
        "timeout-minutes",
        "container",
        "services",
        "strategy",
        "continue-on-error",
        "outputs",
    ],
)
def test_unsupported_job_fields(tmp_path, field):
    with pytest.raises(ValueError, match=field):
        Replay(workflow(tmp_path, [{"run": "true"}], **{field: None}), "test", {}).run()


@pytest.mark.parametrize("value", [None, 4, False])
def test_non_string_run(tmp_path, value):
    with pytest.raises(ValueError, match="run"):
        Replay(workflow(tmp_path, [{"run": value}]), "test", {}).run()


def test_working_directory(tmp_path):
    (tmp_path / "sub").mkdir()
    path = workflow(tmp_path, [{"run": "pwd", "working-directory": "sub"}])
    assert Replay(path, "test", {}, cwd=tmp_path).run()[0]["stdout"].strip() == str(
        tmp_path / "sub"
    )
    path = workflow(
        tmp_path, [{"run": "true", "working-directory": "${{ inputs.dir }}"}]
    )
    with pytest.raises(ValueError, match="working-directory"):
        Replay(path, "test", {}, cwd=tmp_path).run()


# Default variables: https://docs.github.com/en/actions/reference/variables-reference
# GitHubContext.cs.GetRuntimeEnvironmentVariables exports context-derived GITHUB_*.
def test_default_runner_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    github = {
        "repository": "o/r",
        "repository_owner": "o",
        "event_name": "push",
        "ref": "refs/heads/dev",
        "sha": "abc",
    }
    script = 'REPO="${GITHUB_REPOSITORY}"; printf "%s|%s|%s|%s|%s|%s|%s|%s|%s" "$REPO" "$GITHUB_REPOSITORY_OWNER" "$GITHUB_EVENT_NAME" "$GITHUB_REF" "$GITHUB_SHA" "$CI" "$GITHUB_ACTIONS" "$HOME" "${GITHUB_ACTOR-}"'
    replay = Replay(workflow(tmp_path, [{"run": script}]), "test", {"github": github})
    assert (
        replay.run()[0]["stdout"]
        == f"o/r|o|push|refs/heads/dev|abc|true|true|{tmp_path}|"
    )
