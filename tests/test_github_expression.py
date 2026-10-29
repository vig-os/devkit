"""GitHub semantics: https://docs.github.com/en/actions/reference/workflows-and-actions/expressions."""

import json
import subprocess
import sys

import pytest
import yaml

from tests.github_expression import evaluate, render
from tests.workflow_scaffold import WORKFLOWS


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        ("'' || 'x'", "x"),
        ("null && 'x'", None),
        ("false || 7", 7),
        ("true && 'yes'", "yes"),
        ("!false", True),
        ("!0", True),
        ("!-0", True),
        ("!''", True),
        ("!null", True),
        ("!'false'", False),
        ("!' '", False),
        ("!fromJSON('[]')", False),
        ("!fromJSON('{}')", False),
        ("'HELLO' == 'hello'", True),
        ("'a' != 'A'", False),
        ("1 != 2", True),
        ("null == false", True),
        ("'2' == 2", True),
        ("'bad' == 0", False),
        ("'' == 0", True),
        ("fromJSON('{}') == fromJSON('{}')", False),
        ("true || false && false", True),
        ("(true || false) && false", False),
        ("!false == true", True),
        ("-2.5e2", -250),
        ("0xff", 255),
        ("'it''s'", "it's"),
        ("fromJSON('{\"a\":1}').a", 1),
        (
            "fromJSON('{\"release-test\":[\"ubuntu-26.04\"]}')['release-test']",
            ["ubuntu-26.04"],
        ),
        ("github.event.pull_request.head.repo.fork", None),
        ("vars.CI_RUNNER_SMALL", "pool-s"),
        ("true || fromJSON('invalid')", True),
        ("false && fromJSON('invalid')", False),
    ],
)
def test_values(expr, expected):
    result = evaluate(expr, {"vars": {"CI_RUNNER_SMALL": "pool-s"}})
    assert type(result) is type(expected)
    assert result == expected


@pytest.mark.parametrize(
    "expr",
    [
        "contains('a', 'a')",
        "format('x')",
        "vars.*.x",
        "inputs.x[0]",
        "inputs.x[inputs.y]",
        "1 + 2",
        "1 < 2",
        '"double"',
        "true garbage",
        "(true",
        "fromJSON('bad')",
        "unknown.x",
        "true || contains('a','a')",
        "false && vars.*.x",
        "fromJSON()",
        "fromJSON('1', '2')",
        "",
    ],
)
def test_rejects(expr):
    with pytest.raises(ValueError) as error:
        evaluate(expr, {})
    assert repr(expr) in str(error.value)
    assert "position" in str(error.value)


def test_render():
    assert render("${{ fromJSON('[1,2]') }}", {}) == [1, 2]
    assert render("runner-${{ 'A' }}-${{ null }}-${{ true }}", {}) == "runner-A--true"
    assert render("${{ '}}' }}", {}) == "}}"
    assert render("ubuntu-26.04", {}) == "ubuntu-26.04"
    with pytest.raises(ValueError, match="position"):
        render("prefix ${{ true", {})


def test_cli(tmp_path):
    context = tmp_path / "context.json"
    context.write_text('{"inputs":{"x":7}}')
    command = [
        sys.executable,
        "-m",
        "tests.github_expression",
        "--context",
        str(context),
    ]
    result = subprocess.run(
        command + ["--expr", "${{ inputs.x }}"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == 7
    result = subprocess.run(
        command + ["--expr", "${{ contains('x','x') }}"], capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "position" in result.stderr


@pytest.mark.parametrize("event", ["fork", "same-repo", "push"])
@pytest.mark.parametrize("configured", [False, True])
def test_shipped_workflows(event, configured):
    variables = (
        {
            f"CI_RUNNER_{size}": f"pool-{size.lower()}"
            for size in ("SMALL", "LARGE", "XLARGE")
        }
        if configured
        else {}
    )
    runners = json.dumps(
        dict.fromkeys(
            ("small", "large", "xlarge", "lint", "test", "release-test", "extension"),
            "ubuntu-26.04",
        )
    )
    context = {
        "vars": variables,
        "inputs": {"runners": runners, "runner-json": '["ubuntu-26.04"]'},
        "needs": {
            job: {"outputs": {"runners": runners}}
            for job in ("resolve-toolchain", "validate")
        },
        "github": {"repository": "example/project", "event": {}},
    }
    if event != "push":
        context["github"]["event"]["pull_request"] = {
            "head": {"repo": {"fork": event == "fork", "full_name": "example/project"}}
        }
    runs = resolves = predicates = 0
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for job in yaml.safe_load(path.read_text()).get("jobs", {}).values():
            if "runs-on" in job:
                value = job["runs-on"]
                render(value, context)
                runs += 1
                if isinstance(value, str) and "github.event.pull_request" in value:
                    predicates += 1
                    assert render(value, context) == (
                        "pool-small"
                        if configured and event != "fork"
                        else "ubuntu-26.04"
                    )
            for step in job.get("steps", []):
                if "resolve-toolchain" in step.get("uses", ""):
                    resolves += 1
                    for value in step.get("with", {}).values():
                        render(value, context)
    assert runs and resolves and predicates
