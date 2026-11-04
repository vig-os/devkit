"""Consumer-matrix wiring for the strict expression and workflow replay helpers.

Run as a module from render-cell.sh. Scheduling/checkouts are not executed:
runner labels are evaluated and asserted separately. Adoption replays only the
upgrade and PR steps, adapting curl, docker and gh through install-transport.sh.
"""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

from tests.github_expression import render, render_input
from tests.workflow_replay import Replay

ROOT = Path(__file__).resolve().parents[1]
HOSTED = "ubuntu-26.04"


def context(labels, fork=False):
    return {
        "vars": dict(
            zip(
                ("CI_RUNNER_SMALL", "CI_RUNNER_LARGE", "CI_RUNNER_XLARGE"),
                labels,
                strict=True,
            )
        ),
        "github": {
            "repository": "example/consumer",
            "actor": "consumer-matrix",
            "event_name": "pull_request",
            "event": {
                "repository": {"private": True},
                "pull_request": {
                    "head": {
                        "repo": {
                            "fork": fork,
                            "full_name": "example/fork" if fork else "example/consumer",
                        }
                    }
                },
            },
        },
        "inputs": {},
        "secrets": {},
        "steps": {},
        "needs": {},
    }


def action_outputs(step, ctx, evidence):
    """Feed evaluated workflow with inputs through the real composite run body."""
    action = yaml.safe_load(
        Path(".github/actions/resolve-toolchain/action.yml").read_text()
    )
    ctx = copy.deepcopy(ctx)
    ctx["inputs"] = {
        key: render_input(value, ctx) for key, value in step["with"].items()
    }
    resolve = next(s for s in action["runs"]["steps"] if s.get("id") == "resolve")
    output = evidence / "outputs"
    output.write_text("")
    result = subprocess.run(
        ["bash", "-eo", "pipefail", "-c", resolve["run"]],
        env={
            **os.environ,
            **{key: render_input(value, ctx) for key, value in resolve["env"].items()},
            "GITHUB_OUTPUT": str(output),
            "GITHUB_STEP_SUMMARY": str(evidence / "summary"),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    result.check_returncode()
    raw = dict(line.split("=", 1) for line in output.read_text().splitlines())
    ctx["steps"] = {"resolve": {"outputs": raw}}
    return {
        key: render_input(value["value"], ctx)
        for key, value in action["outputs"].items()
    }


def resolve_workflows(workflows, ctx, evidence, expected):
    """Validate each resolve step and retain its real job output mappings."""
    resolved = {}
    for name, doc in workflows.items():
        for job_id, job in doc["jobs"].items():
            for step in job.get("steps", []):
                if not step.get("uses", "").endswith("/resolve-toolchain"):
                    continue
                outputs = action_outputs(step, ctx, evidence)
                actual = json.loads(outputs["runners"])
                assert all(actual[size] == value for size, value in expected.items()), (
                    name,
                    actual,
                    expected,
                )
                assert all(
                    actual[lane] == expected["small"]
                    for lane in ("lint", "test", "extension", "release-test")
                ), name
                step_ctx = {**ctx, "steps": {step["id"]: {"outputs": outputs}}}
                job_outputs = {
                    key: render_input(value, step_ctx)
                    for key, value in job["outputs"].items()
                }
                resolved[name] = (job_id, job_outputs)
    return resolved


def expected_job_runner(name, job_id, is_resolver, ctx, labels, expected):
    """Independent lane contract for hosted, bootstrap and resolved jobs."""
    # Expected lanes come from the contract, never the expression under test.
    hosted = (name, job_id) in {
        ("ci.yml", "dependency-review"),
        ("codeql.yml", "analyze"),
        ("scorecard.yml", "analysis"),
    }
    bootstrap = is_resolver or name in {
        "devkit-upgrade.yml",
        "prepare-release-extension.yml",
        "release-extension.yml",
        "publish-release-extension.yml",
    }
    expected_label = (
        [HOSTED]
        if hosted
        else [
            HOSTED
            if ctx["github"]["event"]["pull_request"]["head"]["repo"]["fork"]
            else labels[0] or HOSTED
        ]
        if bootstrap
        else expected["small"]
    )
    return expected_label


def assert_job_runners(workflows, ctx, resolved, labels, expected):
    """Compare every job's evaluated runs-on to the ADR's default SMALL lanes."""
    assert "ci.yml" in resolved, "ci.yml resolve action not found"
    canonical = resolved["ci.yml"][1]
    for name, doc in workflows.items():
        local = copy.deepcopy(ctx)
        local["needs"] = {
            key: {"outputs": canonical} for key in ("resolve-toolchain", "validate")
        }
        if name in resolved:
            job_id, outputs = resolved[name]
            local["needs"][job_id] = {"outputs": outputs}
        local["inputs"] = {
            "runners": canonical["runners"],
            "runner-json": canonical["runner-json"],
        }
        for job_id, job in doc["jobs"].items():
            if "runs-on" not in job:
                continue
            expression = job["runs-on"]
            actual = render(expression, local)
            actual = actual if isinstance(actual, list) else [actual]
            expected_label = expected_job_runner(
                name,
                job_id,
                name in resolved and job_id == resolved[name][0],
                ctx,
                labels,
                expected,
            )
            assert actual == expected_label, (name, job_id, actual, expected_label)


def runners(labels, evidence):
    """Check all shipped workflow inputs, class outputs, and job runner labels."""
    workflows = {
        p.name: yaml.safe_load(p.read_text())
        for p in Path(".github/workflows").glob("*.yml")
    }
    legacy = (
        "pool-legacy"
        if any(
            line == "DEVKIT_CI_RUNNER=pool-legacy"
            for line in Path(".vig-os").read_text().splitlines()
        )
        else ""
    )
    for fork in (False, True):
        ctx = context(labels, fork)
        expected = {
            size: [HOSTED if fork else label or legacy or HOSTED]
            for size, label in zip(("small", "large", "xlarge"), labels, strict=True)
        }
        resolved = resolve_workflows(workflows, ctx, evidence, expected)
        assert_job_runners(workflows, ctx, resolved, labels, expected)
        print(f"verified managed workflow wiring (fork={fork})")
    # Preserve the non-fork CI outputs for render-cell.sh's full diagnostic check.
    action_outputs(
        next(
            s
            for s in workflows["ci.yml"]["jobs"]["resolve-toolchain"]["steps"]
            if s.get("uses", "").endswith("/resolve-toolchain")
        ),
        context(labels),
        evidence,
    )


def adoption(evidence):
    """Each real step evaluates its own env and consumes only command-file outputs."""
    target = dict(
        line.split("=", 1)
        for line in (ROOT / ".vig-os").read_text().splitlines()
        if line.startswith("DEVKIT_VERSION=")
    )["DEVKIT_VERSION"]
    ctx = context(("", "", ""))
    ctx["steps"] = {
        key: {"outputs": value}
        for key, value in {
            "resolve": {"target": target, "proceed": "true"},
            "branch": {"name": "chore/adopt-devkit"},
            "commit": {"changed": "true"},
            "app-token": {"token": ""},
        }.items()
    }
    replay = Replay(
        evidence / "pre-n.yml",
        "upgrade",
        ctx,
        base_env={
            "PATH": f"{evidence / 'bin'}:{os.environ['PATH']}",
            "MATRIX_ROOT": str(ROOT),
            "MATRIX_EVIDENCE": str(evidence),
            "MATRIX_TARGET": target,
        },
    )
    # Scheduling and cross-job outputs are checked outside the sequential replay.
    del replay.job["timeout-minutes"], replay.job["outputs"]
    records = replay.run(only=["upgrade", "Open or update the adoption PR"])
    (evidence / "install.log").write_text(records[0]["stdout"])
    for record in records:
        print(record["stdout"], end="")
        print(record["stderr"], end="", file=sys.stderr)


if __name__ == "__main__":
    if sys.argv[1] == "runners":
        runners(sys.argv[2:5], Path(sys.argv[5]))
    elif sys.argv[1] == "adoption":
        adoption(Path(sys.argv[2]))
    else:
        raise ValueError(f"Unknown matrix operation: {sys.argv[1]}")
