#!/usr/bin/env python3
"""Shellcheck the ``run:`` bodies of composite GitHub Actions.

``actionlint`` shellchecks the ``run:`` steps of *workflows*, but a composite
action is not a workflow: it refuses ``.github/actions/*/action.yml`` outright
(``unexpected key "runs" for "workflow" section``) and has no composite mode.
Every shell body a repo moves out of a workflow and into a composite therefore
loses its lint. This gate restores it by reproducing actionlint's own
shellcheck recipe over the bodies actionlint will not read:

* each ``${{ … }}`` expression is replaced by underscores of the same length
  (newlines kept), so shellcheck parses a syntactically valid script and every
  line and column still points at the real source;
* the script is prefixed with the options GitHub's own shell invocation sets
  (``set -eo pipefail`` for ``bash``, ``set -e`` for ``sh``);
* shellcheck runs with ``--norc -f json -x`` and actionlint's exclude list —
  precisely the checks the placeholder substitution would otherwise trip.

Findings are reported in the coordinates of the ``action.yml`` itself, so an
editor jumps straight to the offending line. Inline ``# shellcheck disable=``
directives inside a body work as they do in any script: the body reaches
shellcheck verbatim.

Exit codes:
    0 — no finding at or above the severity gate
    1 — at least one finding
    2 — tool error (shellcheck missing, unreadable file, unparsable YAML)

Usage:
    shellcheck-composite-actions .github/actions/*/action.yml
    shellcheck-composite-actions --severity info path/to/action.yml
    shellcheck-composite-actions --shellcheck /path/to/shellcheck action.yml

Refs: #1704
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# actionlint's exclude list, verbatim: the checks its `${{ }}` placeholder
# substitution would otherwise trip (a placeholder reads as an unassigned or
# constant word to shellcheck). Mirroring it is what makes this gate
# actionlint-equivalent rather than an approximation of one.
SHELLCHECK_EXCLUDES = (
    "SC1091",
    "SC2194",
    "SC2050",
    "SC2153",
    "SC2154",
    "SC2157",
    "SC2043",
)

# Non-greedy and DOTALL: a `${{ }}` expression may span lines.
EXPRESSION_RE = re.compile(r"\$\{\{.*?\}\}", re.DOTALL)

# The options GitHub's own shell invocation sets, per `shell:` value
# (`bash --noprofile --norc -eo pipefail {0}` and `sh -e {0}`). Doubles as the
# set of shells this gate checks: `python`, `pwsh` and friends are skipped.
SHELL_PRELUDES = {
    "bash": "set -eo pipefail\n",
    "sh": "set -e\n",
}

# Every prelude above is exactly one line; findings shift back by that much.
PRELUDE_LINES = 1

# `shell:` values that are legitimately not this gate's business. Anything
# else outside SHELL_PRELUDES (a typo, a custom `bash {0}` template) is skipped
# WITH a note, so a misspelling cannot quietly unlint a body.
NON_SHELL_SHELLS = frozenset({"python", "pwsh", "powershell", "cmd", "node"})

SEVERITIES = ("error", "warning", "info", "style")


class ShellcheckError(RuntimeError):
    """shellcheck could not be run, or did not answer with findings."""


@dataclass(frozen=True)
class Step:
    """One composite step's shell body, anchored in its ``action.yml``."""

    name: str
    shell: str
    body: str
    # 1-based YAML coordinates of the body's very first character.
    line: int
    column: int


@dataclass(frozen=True)
class Finding:
    """One shellcheck finding, in the coordinates of the ``action.yml``."""

    path: Path
    step: str
    code: str
    level: str
    message: str
    line: int
    column: int


def neutralise_expressions(body: str) -> str:
    """Replace every ``${{ … }}`` with same-length underscores.

    Newlines survive, so both line numbers and column offsets of everything
    around the expression are preserved exactly.
    """

    def blank(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else "_" for char in match.group(0))

    return EXPRESSION_RE.sub(blank, body)


def _mapping_get(node: yaml.Node | None, key: str) -> yaml.Node | None:
    """The value node for *key*, or None when *node* is not that mapping."""
    if not isinstance(node, yaml.MappingNode):
        return None
    for key_node, value_node in node.value:
        if isinstance(key_node, yaml.ScalarNode) and key_node.value == key:
            return value_node
    return None


def _body_origin(node: yaml.ScalarNode, lines: list[str]) -> tuple[int, int]:
    """1-based YAML line and column of the scalar body's first character.

    For a block scalar (``run: |``) the body starts on the line after the
    indicator, indented uniformly — that indentation is the column offset
    shellcheck's own columns need. For any other style the scalar starts where
    the node does.
    """
    if node.style in {"|", ">"}:
        first = node.start_mark.line + 2
        indent = next(
            (len(raw) - len(raw.lstrip()) for raw in lines[first - 1 :] if raw.strip()),
            0,
        )
        return first, indent + 1
    return node.start_mark.line + 1, node.start_mark.column + 1


def _note_skipped_shell(path: Path, name: object, shell: object) -> None:
    """Say on stderr when a `run:` step is skipped for a shell this gate does not know."""
    shell_value = shell.value if isinstance(shell, yaml.ScalarNode) else None
    if shell_value in NON_SHELL_SHELLS:
        return
    step = name.value if isinstance(name, yaml.ScalarNode) else "<unnamed>"
    what = f"shell {shell_value!r}" if shell_value is not None else "no shell:"
    print(
        f"note: {path}: step {step!r} skipped ({what} is not one of "
        f"{sorted(SHELL_PRELUDES)}; not shellchecked)",
        file=sys.stderr,
    )


def extract_steps(path: Path) -> list[Step]:
    """The shell bodies of *path*, empty unless it is a composite action."""
    text = path.read_text(encoding="utf-8")
    root = yaml.compose(text, Loader=yaml.SafeLoader)
    runs = _mapping_get(root, "runs")
    using = _mapping_get(runs, "using")
    if not isinstance(using, yaml.ScalarNode) or using.value != "composite":
        return []
    steps_node = _mapping_get(runs, "steps")
    if not isinstance(steps_node, yaml.SequenceNode):
        return []

    lines = text.splitlines()
    steps: list[Step] = []
    for step_node in steps_node.value:
        run = _mapping_get(step_node, "run")
        if not isinstance(run, yaml.ScalarNode):
            continue
        shell = _mapping_get(step_node, "shell")
        name = _mapping_get(step_node, "name")
        if not isinstance(shell, yaml.ScalarNode) or shell.value not in SHELL_PRELUDES:
            _note_skipped_shell(path, name, shell)
            continue
        line, column = _body_origin(run, lines)
        steps.append(
            Step(
                name=name.value if isinstance(name, yaml.ScalarNode) else "<unnamed>",
                # nosec B604 - the step's `shell:` value, not a subprocess flag
                shell=shell.value,
                body=run.value,
                line=line,
                column=column,
            )
        )
    return steps


def check_step(
    path: Path, step: Step, *, shellcheck: str, severity: str
) -> list[Finding]:
    """Run shellcheck over one step's body and map the findings back."""
    script = SHELL_PRELUDES[step.shell] + neutralise_expressions(step.body)
    argv = [
        shellcheck,
        "--norc",
        "-f",
        "json",
        "-x",
        "--shell",
        step.shell,
        "-e",
        ",".join(SHELLCHECK_EXCLUDES),
        "-S",
        severity,
        "-",
    ]
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, shell=False
            argv,
            input=script,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        msg = f"cannot run {shellcheck}: {exc}"
        raise ShellcheckError(msg) from exc

    try:
        reported = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        msg = (
            f"{shellcheck} produced no parseable JSON for step {step.name!r} "
            f"(exit {result.returncode}): {result.stderr.strip() or result.stdout!r}"
        )
        raise ShellcheckError(msg) from exc

    return [
        Finding(
            path=path,
            step=step.name,
            code=f"SC{item['code']}",
            level=item["level"],
            message=item["message"],
            # The body starts one prelude line into the script, and body
            # column 1 sits at the block scalar's indentation.
            line=step.line + max(item["line"] - PRELUDE_LINES, 1) - 1,
            column=step.column + item["column"] - 1,
        )
        for item in reported
    ]


def check_file(path: Path, *, shellcheck: str, severity: str) -> list[Finding]:
    """Shellcheck every shell body of one ``action.yml``."""
    findings: list[Finding] = []
    for step in extract_steps(path):
        findings.extend(
            check_step(path, step, shellcheck=shellcheck, severity=severity)
        )
    return findings


def format_finding(finding: Finding) -> str:
    """One finding as an editor-jumpable line."""
    return (
        f"{finding.path}:{finding.line}:{finding.column}: "
        f"{finding.code} ({finding.level}): {finding.message} "
        f"[step: {finding.step}]"
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: shellcheck the composite actions named on argv."""
    parser = argparse.ArgumentParser(
        prog="shellcheck-composite-actions",
        description="Shellcheck the run bodies of composite GitHub Actions.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="action.yml paths (non-composite files are skipped)",
    )
    parser.add_argument(
        "--shellcheck",
        default=os.environ.get("SHELLCHECK", "shellcheck"),
        help="shellcheck binary to use (default: $SHELLCHECK, else PATH)",
    )
    parser.add_argument(
        "-S",
        "--severity",
        default="warning",
        choices=SEVERITIES,
        help="minimum severity that fails the gate (default: warning)",
    )
    args = parser.parse_args(argv)

    findings: list[Finding] = []
    for path in args.files:
        try:
            findings.extend(
                check_file(path, shellcheck=args.shellcheck, severity=args.severity)
            )
        except (OSError, yaml.YAMLError) as exc:
            print(f"error: cannot read {path}: {exc}", file=sys.stderr)
            return 2
        except ShellcheckError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    for finding in findings:
        print(format_finding(finding))

    if findings:
        print(
            f"error: {len(findings)} shellcheck finding(s) at or above "
            f"{args.severity} in composite-action run bodies",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
