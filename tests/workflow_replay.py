"""Replay trusted workflow run steps, for pytest and bats (not a sandbox).

API: Replay(path, job, context, cwd=..., base_env=...).run(only=[id_or_name])
returns stdout/stderr/outputs/summary/skipped records. Selection is explicit;
seed context['steps'] only for steps not replayed (external boundaries).
Replayed ids replace seeds. step_context exposes outputs/outcome/conclusion,
including failures before they raise. resolve_env(step) resolves env without
executing or validating unsupported job scheduling fields.
CLI: python -m tests.workflow_replay FILE JOB --context ctx.json [--cwd DIR]
[--only NAME ...] [--base-env env.json]. JSON stdout; invalid workflows exit 2;
failed scripts retain their exit code.

Each step uses a fresh bash script: implicit shell is bash -e; explicit bash
(including workflow/job defaults) uses --noprofile --norc -eo pipefail. Literal
working directories are relative to the workspace; expressions are refused.
Base env: host PATH and HOME, plus explicit base_env. No other host env leaks.
CI/GITHUB_ACTIONS=true; repository, repository_owner, event_name, ref, sha in
context.github supply corresponding GITHUB_* variables (missing values are
empty). GITHUB_WORKSPACE, RUNNER_TEMP and command/event files are supplied;
context.github.event is written to GITHUB_EVENT_PATH. Workflow/job/step env
layers override base env; GITHUB_ENV applies only to later steps. Own step env
is available in if. Command files decode strict UTF-8 and split on LF, keeping
CR bytes as Linux does. Outputs enter steps.<id>.outputs; summaries are text.

Refuses all uses (including local composites), other shells, continue-on-error,
timeouts and other unimplemented step keys. run() also refuses job if, timeout,
container, services, strategy, continue-on-error and outputs. No checkout,
job conditions, matrix expansion, status functions, runner expression contexts,
or stdout workflow-command processing. Callers select the job and supply its
contexts; this is a sequential script harness, not a complete Actions runner.
"""

import argparse
import copy
import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from tests.github_expression import evaluate, render_input


def _file_values(path):
    lines, values, index = path.read_bytes().decode("utf-8").split("\n"), {}, 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line:
            continue
        if "=" in line and ("<<" not in line or line.index("=") < line.index("<<")):
            name, value = line.split("=", 1)
        elif "<<" in line:
            name, delimiter = line.split("<<", 1)
            start = index
            while index < len(lines) and lines[index] != delimiter:
                index += 1
            if not delimiter or index == len(lines):
                raise ValueError(f"Unterminated environment file entry: {line}")
            value = "\n".join(lines[start:index])
            index += 1
        else:
            raise ValueError(f"Invalid environment file entry: {line}")
        if not name:
            raise ValueError("Empty environment file name")
        values[name] = value
    return values


class Replay:
    """Load one job; each run starts with a fresh copy of the supplied context."""

    def __init__(self, workflow, job, context, *, cwd=None, base_env=None):
        self.workflow = yaml.safe_load(Path(workflow).read_text())
        if job not in self.workflow.get("jobs", {}):
            raise ValueError(f"Unknown job: {job}")
        self.job = self.workflow["jobs"][job]
        self.steps = self.job["steps"]
        self.context = copy.deepcopy(context)
        self.cwd = Path(cwd or Path.cwd()).resolve()
        self.base_env = {
            "PATH": os.environ.get("PATH", os.defpath),
            "HOME": str(Path.home()),
            **(base_env or {}),
        }

    def resolve_env(self, step, context=None, propagated=None):
        """Stringify env layers with step precedence, using the shared evaluator."""
        context = copy.deepcopy(self.context if context is None else context)
        env = {}
        for layer in (self.workflow.get("env", {}), self.job.get("env", {})):
            env.update(
                {key: render_input(value, context) for key, value in layer.items()}
            )
        env.update(propagated or {})
        context["env"] = env
        return {
            **env,
            **{
                key: render_input(value, context)
                for key, value in step.get("env", {}).items()
            },
        }

    def _settings(self, step):
        allowed = {"name", "id", "if", "env", "run", "shell", "working-directory"}
        if set(step) - allowed:
            raise ValueError(f"Unsupported step fields: {sorted(set(step) - allowed)}")
        if not isinstance(step.get("run"), str):
            raise ValueError("Unsupported run: expected a string")
        settings = {}
        for source in (self.workflow, self.job):
            settings.update(source.get("defaults", {}).get("run", {}))
        settings.update(
            {key: step[key] for key in ("shell", "working-directory") if key in step}
        )
        if settings.get("shell", "bash") != "bash":
            raise ValueError(f"Unsupported shell: {settings['shell']}")
        directory = settings.get("working-directory", ".")
        if (
            not isinstance(directory, str)
            or "${{" in directory
            or Path(directory).is_absolute()
        ):
            raise ValueError(
                "Unsupported working-directory: expected a relative literal"
            )
        return settings

    def _validate_job(self):
        """Reject scheduling and job features the script harness cannot simulate."""
        unsupported = {
            "if",
            "timeout-minutes",
            "container",
            "services",
            "strategy",
            "continue-on-error",
            "outputs",
        } & self.job.keys()
        if unsupported:
            raise ValueError(f"Unsupported job fields: {sorted(unsupported)}")

    def run(self, *, only=None):
        """Run all steps or explicit ids/names; fail at the first script error."""
        self._validate_job()
        if only and any(
            not any(s.get("id") == name or s.get("name") == name for s in self.steps)
            for name in only
        ):
            raise ValueError(f"Unknown step selection: {only}")
        context, propagated, records = copy.deepcopy(self.context), {}, []
        self.step_context = context.setdefault("steps", {})
        with TemporaryDirectory(prefix="workflow-replay-") as temporary:
            root = Path(temporary)
            event = root / "event.json"
            event.write_text(json.dumps(context.get("github", {}).get("event", {})))
            for index, step in enumerate(self.steps):
                if only is not None and not any(
                    step.get("id") == name or step.get("name") == name for name in only
                ):
                    continue
                settings = self._settings(step)
                if "id" in step:
                    context["steps"].pop(step["id"], None)
                env = self.resolve_env(step, context, propagated)
                context["env"] = env
                condition = step.get("if", "true")
                if isinstance(condition, str):
                    condition = condition.strip()
                    if condition.startswith("${{") and condition.endswith("}}"):
                        condition = condition[3:-2]
                    condition = evaluate(f"!!({condition})", context)
                if not condition:
                    self._result(step, context, {}, "skipped")
                    records.append({"skipped": True})
                    continue
                records.append(
                    self._execute(
                        step, settings, env, context, propagated, root, event, index
                    )
                )
        return records

    def _execute(self, step, settings, env, context, propagated, root, event, index):
        """Run one shell and collect its command files."""
        files = {
            name: root / f"{index}-{name}"
            for name in ("GITHUB_OUTPUT", "GITHUB_ENV", "GITHUB_STEP_SUMMARY")
        }
        for path in files.values():
            path.touch()
        script = root / f"{index}.sh"
        script.write_text(render_input(step["run"], context), encoding="utf-8")
        shell = (
            ["bash", "--noprofile", "--norc", "-eo", "pipefail"]
            if settings.get("shell") == "bash"
            else ["bash", "-e"]
        )
        process = subprocess.run(
            [*shell, str(script)],
            cwd=self.cwd / settings.get("working-directory", "."),
            env={
                **self._runner_env(context),
                **env,
                "RUNNER_TEMP": str(root),
                "GITHUB_WORKSPACE": str(self.cwd),
                "GITHUB_EVENT_PATH": str(event),
                **{name: str(path) for name, path in files.items()},
            },
            capture_output=True,
            text=True,
            check=False,
        )
        outputs = _file_values(files["GITHUB_OUTPUT"])
        propagated.update(_file_values(files["GITHUB_ENV"]))
        self._result(
            step, context, outputs, "failure" if process.returncode else "success"
        )
        process.check_returncode()
        return {
            "stdout": process.stdout,
            "stderr": process.stderr,
            "outputs": outputs,
            "summary": files["GITHUB_STEP_SUMMARY"].read_text(),
            "skipped": False,
        }

    def _runner_env(self, context):
        """Export the documented minimal base and context-derived default variables."""
        github = context.get("github", {})
        defaults = {
            "GITHUB_" + key.upper(): render_input(github.get(key), {})
            for key in ("repository", "repository_owner", "event_name", "ref", "sha")
        }
        return {**self.base_env, "CI": "true", "GITHUB_ACTIONS": "true", **defaults}

    @staticmethod
    def _result(step, context, outputs, result):
        if "id" in step:
            context["steps"][step["id"]] = {
                "outputs": outputs,
                "outcome": result,
                "conclusion": result,
            }


def main():
    """Expose replay records as JSON for shell callers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", type=Path)
    parser.add_argument("job")
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("--base-env", type=Path)
    parser.add_argument("--only", nargs="+")
    args = parser.parse_args()
    try:
        replay = Replay(
            args.workflow,
            args.job,
            json.loads(args.context.read_text()),
            cwd=args.cwd,
            base_env=json.loads(args.base_env.read_text()) if args.base_env else None,
        )
        print(json.dumps(replay.run(only=args.only)))
    except subprocess.CalledProcessError as error:
        parser.exit(error.returncode, error.stdout + error.stderr)
    except (ValueError, OSError, KeyError, TypeError, yaml.YAMLError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
