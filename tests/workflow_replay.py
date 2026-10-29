"""Replay trusted workflow run steps, for pytest and bats (not a sandbox).

API: Replay(path, job, context, cwd=..., base_env=...).run(only=[id_or_name])
returns stdout/stderr/outputs/summary/skipped records. Selection is explicit;
seed context['steps'] for external boundaries. resolve_env(step) resolves env.
CLI: python -m tests.workflow_replay FILE JOB --context ctx.json [--cwd DIR]
[--only NAME ...] [--base-env env.json]. JSON stdout; invalid workflows exit 2;
failed scripts retain their exit code.

Each step uses a fresh bash -eo pipefail process. Only bash is supported;
workflow/job defaults and step working-directory are honored. Base env is PATH
(from host), plus explicit base_env; runner files, RUNNER_TEMP, GITHUB_WORKSPACE
and GITHUB_EVENT_PATH are supplied. No host secrets or other env is inherited.
Workflow/job/step env override that base; GITHUB_ENV affects subsequent steps.
An event payload belongs in context.github.event. Command files support UTF-8,
name=value and name<<DELIM. Outputs enter steps.<id>.outputs; summaries are text.

Refuses all uses (including local composites), other shells, continue-on-error,
timeouts and other unimplemented step keys. No services, checkout, containers,
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
    lines, values, index = path.read_text().split("\n"), {}, 0
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
        self.base_env = {"PATH": os.environ.get("PATH", os.defpath), **(base_env or {})}

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
        if set(step) - allowed or "run" not in step:
            raise ValueError(f"Unsupported step: {step.get('name', step)}")
        settings = {}
        for source in (self.workflow, self.job):
            settings.update(source.get("defaults", {}).get("run", {}))
        settings.update(
            {key: step[key] for key in ("shell", "working-directory") if key in step}
        )
        if settings.get("shell", "bash") != "bash":
            raise ValueError(f"Unsupported shell: {settings['shell']}")
        return settings

    def run(self, *, only=None):
        """Run all steps or explicit ids/names; fail at the first script error."""
        if only and any(
            not any(s.get("id") == name or s.get("name") == name for s in self.steps)
            for name in only
        ):
            raise ValueError(f"Unknown step selection: {only}")
        context, propagated, records = copy.deepcopy(self.context), {}, []
        context.setdefault("steps", {})
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
                env = self.resolve_env(step, context, propagated)
                context["env"] = env
                condition = step.get("if", "true")
                if isinstance(condition, str):
                    condition = condition.strip()
                    if condition.startswith("${{") and condition.endswith("}}"):
                        condition = condition[3:-2]
                    condition = evaluate(f"!!({condition})", context)
                if not condition:
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
        process = subprocess.run(
            [
                *["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c"],
                render_input(step["run"], context),
            ],
            cwd=self.cwd / settings.get("working-directory", "."),
            env={
                **self.base_env,
                **env,
                "RUNNER_TEMP": str(root),
                "GITHUB_WORKSPACE": str(self.cwd),
                "GITHUB_EVENT_PATH": str(event),
                **{name: str(path) for name, path in files.items()},
            },
            capture_output=True,
            text=True,
            check=True,
        )
        outputs = _file_values(files["GITHUB_OUTPUT"])
        propagated.update(_file_values(files["GITHUB_ENV"]))
        if "id" in step:
            context["steps"][step["id"]] = {"outputs": outputs}
        return {
            "stdout": process.stdout,
            "stderr": process.stderr,
            "outputs": outputs,
            "summary": files["GITHUB_STEP_SUMMARY"].read_text(),
            "skipped": False,
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
