"""GitHub semantics: https://docs.github.com/en/actions/reference/workflows-and-actions/expressions.

Runner source: https://github.com/actions/runner/tree/main/src/Sdk/DTExpressions2/Expressions2
Tokens/LexicalAnalyzer.cs: lowercase keywords; ExpressionConstants.cs: G15,
case-insensitive functions; Sdk/ExpressionUtility.cs: ParseNumber hex coercion.
toJSON layout and G15 scalars: runner Sdk/Functions/ToJson.cs, WriteValue,
PrefixValue and WriteArrayEnd/WriteMappingEnd:
https://github.com/actions/runner/blob/main/src/Sdk/DTExpressions2/Expressions2/Sdk/Functions/ToJson.cs
Strings use JsonUtility/Newtonsoft default escaping, including Unicode separators:
https://github.com/JamesNK/Newtonsoft.Json/blob/master/Src/Newtonsoft.Json/Utilities/JavaScriptUtils.cs
"""

import json
import subprocess
import sys

import pytest
import yaml

from tests import github_expression
from tests.github_expression import evaluate, render, render_input
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
        ("'ß' == 'SS'", False),
        ("vars.ci_runner_small", "pool-s"),
        ("VARS.Ci_Runner_Small", "pool-s"),
        ('fromJSON(\'{"Small":"x"}\').small', "x"),
        ("fromJson('true')", True),
        ("FROMJSON('null')", None),
        ("'0x10' == 16", True),
        ("'0xFFFFFFFF' == -1", True),
        ("'0x100000000' == 0", False),
        ("'0X10' == 16", False),
        ("'1_0' == 10", False),
        ("'0o10' == 8", True),
        ("'  +.5  ' == 0.5", True),
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
        ("-2.5e2", -250.0),
        ("0xff", 255),
        ("'it''s'", "it's"),
        ("fromJSON('{\"a\":1}').a", 1),
        (
            "fromJSON('{\"release-test\":[\"ubuntu-26.04\"]}')['release-test']",
            ["ubuntu-26.04"],
        ),
        ("github.event.pull_request.head.repo.fork", None),
        ("vars.CI_RUNNER_SMALL", "pool-s"),
        ("secrets.MISSING", None),
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
        "fromJSON('NaN')",
        "fromJSON('Infinity')",
        "fromJSON('-Infinity')",
        "fromJSON('{\"a\":NaN}')",
        'fromJSON(\'{"Small":1,"small":2}\').small',
        "True",
        "FALSE",
        "Null",
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
    assert render("n=${{ 1.0 }}", {}) == "n=1"
    assert render("${{ fromJSON('[1,2]') }}", {}) == [1, 2]
    assert render("runner-${{ 'A' }}-${{ null }}-${{ true }}", {}) == "runner-A--true"
    assert render("${{ '}}' }}", {}) == "}}"
    assert render("ubuntu-26.04", {}) == "ubuntu-26.04"
    with pytest.raises(ValueError, match="position"):
        render("prefix ${{ true", {})


@pytest.mark.parametrize("as_input", [False, True])
def test_cli(tmp_path, as_input):
    context = tmp_path / "context.json"
    context.write_text('{"inputs":{"x":7}}')
    command = [
        sys.executable,
        "-m",
        "tests.github_expression",
        "--context",
        str(context),
    ]
    if as_input:
        command.append("--input")
    result = subprocess.run(
        command + ["--expr", "${{ inputs.x }}"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ("7" if as_input else 7)
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
        "secrets": {"GHCR_PULL_TOKEN": "test-token"},
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
            for value in job.get("with", {}).values():
                render_input(value, context)
            for step in job.get("steps", []):
                if "resolve-toolchain" in step.get("uses", ""):
                    resolves += 1
                    for value in step.get("with", {}).values():
                        render_input(value, context)
    assert runs and resolves and predicates


def test_context_ambiguity():
    for context in ({"vars": {"x": 1, "X": 2}}, {"vars": {}, "VARS": {}}):
        with pytest.raises(ValueError, match="[Aa]mbiguous"):
            evaluate("vars.x", context)


def test_nan_falsiness():
    assert evaluate("!inputs.x", {"inputs": {"x": float("nan")}}) is True


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("${{ null }}", ""),
        ("${{ true }}", "true"),
        ("${{ false }}", "false"),
        ("${{ 1.0 }}", "1"),
        ("${{ 1e20 }}", "1E+20"),
        ("${{ 1.2345678901234567 }}", "1.23456789012346"),
        ("${{ 0.00001 }}", "1E-05"),
        (7, "7"),
        (False, "false"),
    ],
)
def test_render_input(value, expected):
    assert github_expression.render_input(value, {}) == expected


@pytest.mark.parametrize(
    "value",
    [
        "contains('x','x')",
        "prefix ${{ contains('x','x') }}",
        "a ${{ true }} b ${{ format('x') }}",
    ],
)
def test_error_positions(value):
    function = "contains" if "contains" in value else "format"
    with pytest.raises(ValueError) as error:
        (render if "${{" in value else evaluate)(value, {})
    assert repr(value) in str(error.value)
    assert f"position {value.index(function)}" in str(error.value)


@pytest.mark.parametrize("contents", [None, "directory", "[]", "null", "7", "invalid"])
def test_cli_context_errors(tmp_path, contents):
    path = tmp_path / "context.json"
    if contents == "directory":
        path.mkdir()
    elif contents is not None:
        path.write_text(contents)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.github_expression",
            "--context",
            str(path),
            "--expr",
            "true",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "error:" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("mutation", ["fork", "reusable"])
def test_workflow_mutations(tmp_path, monkeypatch, mutation):
    # Mutate copies, leaving managed workflows untouched. Both must trip the gate.
    for path in WORKFLOWS.glob("*.yml"):
        data = yaml.safe_load(path.read_text())
        if mutation == "fork" and path.name == "sync-issues.yml":
            job = next(
                job
                for job in data["jobs"].values()
                if "github.event.pull_request" in str(job.get("runs-on", ""))
            )
            job["runs-on"] = (
                "${{ (github.event.pull_request.head.repo.fork && vars.ci_runner_small) || (!github.event.pull_request.head.repo.fork && vars.CI_RUNNER_SMALL) || 'ubuntu-26.04' }}"
            )
        if mutation == "reusable" and path.name == "release.yml":
            job = next(job for job in data["jobs"].values() if "uses" in job)
            job.setdefault("with", {})["runners"] = "${{ contains('x','x') }}"
        (tmp_path / path.name).write_text(yaml.safe_dump(data))
    monkeypatch.setitem(test_shipped_workflows.__globals__, "WORKFLOWS", tmp_path)
    with pytest.raises(AssertionError if mutation == "fork" else ValueError):
        test_shipped_workflows("fork", True)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            {"a": 1, "nested": [True, None, {}]},
            '{\n  "a": 1,\n  "nested": [\n    true,\n    null,\n    {}\n  ]\n}',
        ),
        ([1, 2], "[\n  1,\n  2\n]"),
        ({}, "{}"),
        ([], "[]"),
        ('say "café 🌍"\n', '"say \\"café 🌍\\"\\n"'),
        ("\u0085\u2028\u2029", '"\\u0085\\u2028\\u2029"'),
        (float("nan"), "NaN"),
        (float("inf"), "Infinity"),
        (float("-inf"), "-Infinity"),
        (None, "null"),
        (True, "true"),
        (False, "false"),
        (1.0, "1"),
        (1e20, "1E+20"),
        (1.2345678901234567, "1.23456789012346"),
    ],
)
@pytest.mark.parametrize("function", ["toJSON", "toJson", "TOJSON"])
def test_to_json(value, expected, function):
    assert (
        evaluate(f"{function}(inputs.value)", {"inputs": {"value": value}}) == expected
    )
