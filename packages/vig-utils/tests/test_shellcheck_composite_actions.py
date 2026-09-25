"""Tests for vig_utils.shellcheck_composite_actions.

The gate reproduces actionlint's shellcheck recipe over composite-action
``run:`` bodies, which actionlint itself refuses to read (#1704).
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from vig_utils.shellcheck_composite_actions import (
    SHELLCHECK_EXCLUDES,
    extract_steps,
    main,
    neutralise_expressions,
)

requires_shellcheck = pytest.mark.skipif(
    shutil.which("shellcheck") is None,
    reason="shellcheck is not on PATH; this gate needs the real binary",
)

CLEAN_STEP = """\
    - name: Clean step
      shell: bash
      run: |
        echo "hello"
        if [ -n "${HOME:-}" ]; then
          echo "home is set"
        fi
"""

SPLITTING_STEP = """\
    - name: Start podman socket
      shell: bash
      run: |
        podman system service unix:///run/user/$(id -u)/podman/podman.sock
"""

DISABLED_SPLITTING_STEP = """\
    - name: Deliberate splitting
      shell: bash
      run: |
        # shellcheck disable=SC2046
        podman system service unix:///run/user/$(id -u)/podman/podman.sock
"""

EXPRESSION_STEP = """\
    - name: Compare inputs
      shell: bash
      run: |
        if [ "${{ inputs.mode }}" = "full" ]; then
          echo "full"
        fi
        if [ -n "${{ inputs.label }}" ]; then
          echo "labelled"
        fi
"""

PYTHON_STEP = """\
    - name: Python step
      shell: python
      run: |
        import sys
        this is not shell( at all
        print(sys.version)
"""

USES_STEP = """\
    - name: Checkout
      uses: actions/checkout@v5
"""

OFFSET_STEP = """\
    - name: Offset probe
      shell: bash
      run: |
        cp ${{ inputs.flags }} $(ls) /tmp/probe
"""

UNQUOTED_VAR_STEP = """\
    - name: Run pytest
      shell: bash
      run: |
        TEST_ARGS=""
        echo $TEST_ARGS
"""


def write_action(path: Path, steps: str, *, using: str = "composite") -> Path:
    """Write a composite action whose ``runs.steps`` block is *steps*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"name: probe\ndescription: probe\nruns:\n  using: {using}\n  steps:\n{steps}",
        encoding="utf-8",
    )
    return path


class TestNeutraliseExpressions:
    def test_expression_becomes_underscores_of_equal_length(self):
        body = 'echo "${{ inputs.mode }}"'
        neutralised = neutralise_expressions(body)
        assert neutralised == 'echo "__________________"'
        assert len(neutralised) == len(body)

    def test_every_line_keeps_its_length(self):
        body = "A=${{ inputs.a }}\nB=${{ steps.x.outputs.y }} ${{ env.Z }}\n"
        neutralised = neutralise_expressions(body)
        assert [len(line) for line in neutralised.splitlines()] == [
            len(line) for line in body.splitlines()
        ]

    def test_multiline_expression_keeps_its_newlines(self):
        body = "A=${{ inputs.a\n  || inputs.b }}\nB=2\n"
        neutralised = neutralise_expressions(body)
        assert "${{" not in neutralised
        assert neutralised.count("\n") == body.count("\n")
        assert neutralised.splitlines()[2] == "B=2"

    def test_plain_shell_body_is_untouched(self):
        body = 'echo "$HOME"\n'
        assert neutralise_expressions(body) == body


class TestExtractSteps:
    def test_extracts_bash_bodies_with_names_and_yaml_lines(self, tmp_path: Path):
        path = write_action(tmp_path / "action.yml", CLEAN_STEP + SPLITTING_STEP)
        steps = extract_steps(path)
        assert [step.name for step in steps] == ["Clean step", "Start podman socket"]
        assert steps[0].shell == "bash"
        assert steps[0].body.startswith('echo "hello"')
        first_body_line = (
            path.read_text(encoding="utf-8").splitlines().index('        echo "hello"')
            + 1
        )
        assert steps[0].line == first_body_line

    def test_non_composite_action_yields_no_steps(self, tmp_path: Path):
        path = tmp_path / "action.yml"
        path.write_text(
            "name: probe\ndescription: probe\nruns:\n"
            "  using: node20\n  main: dist/index.js\n",
            encoding="utf-8",
        )
        assert extract_steps(path) == []

    def test_non_shell_steps_are_skipped(self, tmp_path: Path):
        path = write_action(tmp_path / "action.yml", PYTHON_STEP + USES_STEP)
        assert extract_steps(path) == []


class TestShellcheckExcludes:
    def test_excludes_are_actionlints_placeholder_set(self):
        assert SHELLCHECK_EXCLUDES == (
            "SC1091",
            "SC2194",
            "SC2050",
            "SC2153",
            "SC2154",
            "SC2157",
            "SC2043",
        )


@requires_shellcheck
class TestMain:
    def test_clean_body_passes(self, tmp_path: Path, capsys):
        path = write_action(tmp_path / "action.yml", CLEAN_STEP)
        assert main([str(path)]) == 0
        assert "SC" not in capsys.readouterr().out

    def test_word_splitting_fails_and_names_the_step(self, tmp_path: Path, capsys):
        path = write_action(tmp_path / "action.yml", SPLITTING_STEP)
        assert main([str(path)]) == 1
        out = capsys.readouterr().out
        assert "SC2046" in out
        assert "Start podman socket" in out
        assert str(path) in out

    def test_finding_points_at_the_yaml_line_and_column(self, tmp_path: Path, capsys):
        path = write_action(tmp_path / "action.yml", OFFSET_STEP)
        assert main([str(path)]) == 1
        reported = [
            line for line in capsys.readouterr().out.splitlines() if "SC2046" in line
        ]
        assert len(reported) == 1
        line_no, column = (int(part) for part in reported[0].split(":")[1:3])
        source = path.read_text(encoding="utf-8").splitlines()[line_no - 1]
        assert source.strip() == "cp ${{ inputs.flags }} $(ls) /tmp/probe"
        assert source[column - 1 : column + 1] == "$("

    def test_expressions_in_test_brackets_are_not_flagged(self, tmp_path: Path):
        path = write_action(tmp_path / "action.yml", EXPRESSION_STEP)
        assert main([str(path)]) == 0

    def test_inline_disable_directive_suppresses(self, tmp_path: Path):
        path = write_action(tmp_path / "action.yml", DISABLED_SPLITTING_STEP)
        assert main([str(path)]) == 0

    def test_non_shell_step_bodies_are_never_checked(self, tmp_path: Path):
        path = write_action(tmp_path / "action.yml", PYTHON_STEP)
        assert main([str(path)]) == 0

    def test_non_composite_action_is_skipped(self, tmp_path: Path):
        path = tmp_path / "action.yml"
        path.write_text(
            "name: probe\ndescription: probe\nruns:\n"
            "  using: node20\n  main: dist/index.js\n",
            encoding="utf-8",
        )
        assert main([str(path)]) == 0

    def test_default_severity_ignores_info_findings(self, tmp_path: Path):
        path = write_action(tmp_path / "action.yml", UNQUOTED_VAR_STEP)
        assert main([str(path)]) == 0

    def test_lower_severity_surfaces_info_findings(self, tmp_path: Path, capsys):
        path = write_action(tmp_path / "action.yml", UNQUOTED_VAR_STEP)
        assert main(["--severity", "info", str(path)]) == 1
        assert "SC2086" in capsys.readouterr().out


class TestShellcheckResolution:
    def test_missing_binary_is_a_tool_error(self, tmp_path: Path, capsys):
        path = write_action(tmp_path / "action.yml", CLEAN_STEP)
        assert main(["--shellcheck", "/nonexistent/shellcheck", str(path)]) == 2
        assert "/nonexistent/shellcheck" in capsys.readouterr().err

    def test_env_var_names_the_binary(self, tmp_path: Path, capsys, monkeypatch):
        monkeypatch.setenv("SHELLCHECK", "/nonexistent/from-env")
        path = write_action(tmp_path / "action.yml", CLEAN_STEP)
        assert main([str(path)]) == 2
        assert "/nonexistent/from-env" in capsys.readouterr().err
