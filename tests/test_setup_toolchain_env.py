"""Behavior tests: direnv-mode shellHook env forwarding in setup-devkit-toolchain.

Issue #1180: the direnv-mode CI preamble exports the dev-shell store bin dirs to
``GITHUB_PATH`` but dropped every environment variable a project's flake
``shellHook`` exports, so env defaults that exist in every local
``nix develop``/direnv session silently vanished on CI (proven in
vig-os/org-config#40, where a shellHook-seeded ``OTTERDOG_TOKEN`` placeholder
worked locally and failed on CI).

The fix diffs the ambient environment against the dev-shell environment (the
shellHook has run inside ``nix develop``) and forwards the vars the dev-shell
adds or changes to ``GITHUB_ENV``, minus a denylist of shell session state and
Nix/stdenv build machinery that must never leak into the CI environment.

These tests execute the "Build repo flake dev-shell and export PATH" step's real
``run:`` script against a stubbed ``nix`` that emits a simulated dev-shell
environment, then assert on the ``GITHUB_ENV`` the script wrote — the same
executed-bash pattern as ``test_ci_runner.py``.

Refs: #1180
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent
ACTION = (
    REPO_ROOT
    / "assets"
    / "workspace"
    / ".github"
    / "actions"
    / "setup-devkit-toolchain"
    / "action.yml"
)

# The direnv step under test.
DEVSHELL_STEP_NAME = "Build repo flake dev-shell and export PATH"

# The banner the scaffolded flake's shellHook echoes to stdout on every
# `nix develop` (assets/workspace/flake.nix). Captured stdout therefore mixes
# this line into anything the step reads from a `nix develop --command`
# pipeline (#1189).
BANNER = "devcontainer dev environment loaded (nix)"

# The simulated dev-shell environment the stub `nix` emits (null-delimited). It
# mixes shellHook exports (must forward), Nix/stdenv build machinery (must be
# denied), shell session state (must be denied), and an ambient var unchanged
# from the host env (must be filtered out, never re-forwarded — this is how host
# secrets stay out of GITHUB_ENV).
_DEVSHELL_ENV = [
    ("OTTERDOG_TOKEN", "placeholder-set-by-shellhook"),
    ("PROJECT_GREETING", "hello world"),
    ("MULTILINE_VAR", "line-one\nline-two\nline-three"),
    # Nix/stdenv build machinery — every one must be denied.
    ("buildInputs", "/nix/store/xxxxxxxx-foo"),
    ("nativeBuildInputs", "/nix/store/yyyyyyyy-bar"),
    ("stdenv", "/nix/store/zzzzzzzz-stdenv-linux"),
    ("shellHook", "export OTTERDOG_TOKEN=placeholder-set-by-shellhook"),
    ("out", "/nix/store/oooooooo-out"),
    ("system", "x86_64-linux"),
    ("NIX_CFLAGS_COMPILE", "-isystem /nix/store/aaa/include"),
    ("NIX_BUILD_CORES", "4"),
    ("dontUnpack", "1"),
    ("configurePhase", ":"),
    ("depsBuildBuild", ""),
    # Shell session state — must be denied.
    ("PATH", "/nix/store/aaaaaaaa-foo/bin:/usr/bin"),
    ("HOME", "/home/dev-shell"),
    ("SHLVL", "2"),
    ("TMPDIR", "/tmp/nix-shell"),
    # Ambient var, unchanged from the host env — must not be re-forwarded.
    ("AMBIENT_SHARED", "same-on-both-sides"),
]


def _devshell_step_script() -> str:
    action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
    for step in action["runs"]["steps"]:
        if step.get("name") == DEVSHELL_STEP_NAME:
            return step["run"]
    raise AssertionError(f"step {DEVSHELL_STEP_NAME!r} not found in {ACTION}")


def _write_nix_stub(bin_dir: Path, *, banner: bool = False) -> None:
    """A fake `nix` covering every invocation the devshell step makes.

    - `nix develop … --command true`                  -> exit 0 (profile build)
    - `nix develop … --command bash -c 'printf … PATH'`-> a fake store PATH
    - `nix develop … --command bash -c '… UV_… '`      -> the uv-download URL
    - `nix develop … --command bash -c 'env -0 > …'`   -> env dump to the file
    - `nix develop … --command env …`                  -> env dump on stdout

    With ``banner=True`` the stub echoes the shellHook banner to stdout on
    every invocation, exactly as the real scaffolded flake does (#1189).
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
    ]
    if banner:
        lines.append(f"echo {_bash_squote(BANNER)}")
    lines += [
        "# Collect the command after `--command`.",
        "cmd=()",
        "found=0",
        'for a in "$@"; do',
        '  if [ "$found" = 1 ]; then cmd+=("$a"); fi',
        '  if [ "$a" = "--command" ]; then found=1; fi',
        "done",
        'joined="${cmd[*]:-}"',
        'if [ "${cmd[0]:-}" = "true" ]; then exit 0; fi',
        "# In-shell file dump: write the records to the target file, keeping",
        "# stdout (the banner) out of the dump — the shape the action relies on.",
        'if [[ "$joined" == *"env -0 >"* ]]; then',
        '  target="${cmd[-1]}"',
        '  : > "$target"',
    ]
    for name, value in _DEVSHELL_ENV:
        lines.append(
            f"  printf '%s\\0' {_bash_squote(name + '=' + value)} >> \"$target\""
        )
    lines += [
        "  exit 0",
        "fi",
        'if [ "${cmd[0]:-}" = "env" ]; then',
    ]
    for name, value in _DEVSHELL_ENV:
        lines.append(f"  printf '%s\\0' {_bash_squote(name + '=' + value)}")
    lines += [
        "  exit 0",
        "fi",
        'case "$joined" in',
        '  *"printf \\"%s\\" \\"\\$PATH\\""*)',
        "    printf '%s' '/nix/store/aaaaaaaa-foo/bin:/nix/store/bbbbbbbb-bar/bin:/usr/bin'; exit 0 ;;",
        "  *UV_PYTHON_DOWNLOADS_JSON_URL*)",
        "    printf 'UV_PYTHON_DOWNLOADS_JSON_URL=https://example.invalid/downloads.json\\n'; exit 0 ;;",
        "esac",
        "exit 0",
    ]
    stub = bin_dir / "nix"
    stub.write_text("\n".join(lines) + "\n", encoding="utf-8")
    stub.chmod(0o755)


def _bash_squote(s: str) -> str:
    """Single-quote a string for safe embedding in the generated bash stub."""
    return "'" + s.replace("'", "'\\''") + "'"


def _run_devshell_step(tmp_path: Path) -> dict[str, str]:
    """Execute the devshell step and return the parsed GITHUB_ENV map.

    Multi-line heredoc values are collapsed with `\\n` joins so a caller can
    assert on them; the presence of a heredoc is asserted separately on the raw
    text where it matters.
    """
    return _exec_devshell_step(tmp_path)[0]


def _exec_devshell_step(
    tmp_path: Path, *, banner: bool = False
) -> tuple[dict[str, str], str]:
    """Execute the devshell step; return (parsed GITHUB_ENV map, raw text)."""
    script = _devshell_step_script()

    bin_dir = tmp_path / "stub-bin"
    _write_nix_stub(bin_dir, banner=banner)

    github_env = tmp_path / "github_env"
    github_path = tmp_path / "github_path"
    runner_temp = tmp_path / "runner_temp"
    github_env.touch()
    github_path.touch()
    runner_temp.mkdir()

    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GITHUB_ENV": str(github_env),
        "GITHUB_PATH": str(github_path),
        "RUNNER_TEMP": str(runner_temp),
        # Ambient var that the dev-shell leaves unchanged: must be filtered out.
        "AMBIENT_SHARED": "same-on-both-sides",
    }

    proc = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,  # no pyproject.toml -> non-Python consumer path
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"devshell step failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    raw = github_env.read_text(encoding="utf-8")
    return _parse_github_env(raw), raw


def _parse_github_env(text: str) -> dict[str, str]:
    """Parse GITHUB_ENV supporting both `KEY=value` and heredoc blocks."""
    out: dict[str, str] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if "<<" in line and "=" not in line.split("<<", 1)[0]:
            name, _, delim = line.partition("<<")
            i += 1
            body: list[str] = []
            while i < len(lines) and lines[i] != delim:
                body.append(lines[i])
                i += 1
            out[name] = "\n".join(body)
            i += 1  # skip the closing delimiter
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            out[key] = value
        i += 1
    return out


# ── Behavior ─────────────────────────────────────────────────────────────────


def test_shellhook_scalar_exports_are_forwarded(tmp_path: Path) -> None:
    """Plain shellHook exports reach GITHUB_ENV (the org-config#40 regression)."""
    env = _run_devshell_step(tmp_path)
    assert env.get("OTTERDOG_TOKEN") == "placeholder-set-by-shellhook"
    assert env.get("PROJECT_GREETING") == "hello world"


def test_multiline_value_survives_via_heredoc(tmp_path: Path) -> None:
    """A multi-line export is forwarded intact using the GITHUB_ENV heredoc."""
    env = _run_devshell_step(tmp_path)
    assert env.get("MULTILINE_VAR") == "line-one\nline-two\nline-three"


@pytest.mark.parametrize(
    "denied",
    [
        # Nix/stdenv build machinery.
        "buildInputs",
        "nativeBuildInputs",
        "stdenv",
        "shellHook",
        "out",
        "system",
        "NIX_CFLAGS_COMPILE",
        "NIX_BUILD_CORES",
        "dontUnpack",
        "configurePhase",
        "depsBuildBuild",
        # Shell session state.
        "PATH",
        "HOME",
        "SHLVL",
        "TMPDIR",
    ],
)
def test_denylisted_vars_are_not_forwarded(tmp_path: Path, denied: str) -> None:
    """Build machinery and shell session state never leak into GITHUB_ENV."""
    env = _run_devshell_step(tmp_path)
    assert denied not in env, f"{denied} must not be forwarded to GITHUB_ENV"


def test_unchanged_ambient_var_is_not_reforwarded(tmp_path: Path) -> None:
    """A var identical to the host env is filtered — host secrets never re-leak."""
    env = _run_devshell_step(tmp_path)
    assert "AMBIENT_SHARED" not in env


def test_shellhook_stdout_banner_never_reaches_github_env(tmp_path: Path) -> None:
    """The scaffolded flake shellHook echoes a banner to stdout during every
    `nix develop`; capturing that stdout as the env dump glued the banner onto
    the first NUL record and wrote an invalid GITHUB_ENV name, failing every
    direnv consumer CI job on 1.4.0-rc2.

    Refs: #1189
    """
    env, raw = _exec_devshell_step(tmp_path, banner=True)
    assert BANNER not in raw, "shellHook stdout leaked into GITHUB_ENV"
    # The first env record must survive intact, not be eaten by the banner.
    assert env.get("OTTERDOG_TOKEN") == "placeholder-set-by-shellhook"


# ── Self-hosted runners with preinstalled Nix (#1192) ────────────────────────

INSTALL_STEP_NAME = "Install Nix (upstream CppNix)"
DETECT_STEP_ID = "detect-nix"
HOST_NIX_STEP_NAME = "Configure host Nix"

# The Nix settings the toolchain needs, identically on both paths (fresh
# install via install-nix-action's extra_nix_config, preinstalled host Nix via
# NIX_CONFIG).
_NIX_SETTINGS = {
    "experimental-features": "nix-command flakes",
    "accept-flake-config": "true",
    "extra-substituters": "https://vig-os.cachix.org",
    "extra-trusted-public-keys": (
        "vig-os.cachix.org-1:yoOYRi3bvnM6ThxO0joLt7vtzhTfkq3r6jykeUMg7Bk="
    ),
}


def _action_steps() -> list[dict]:
    action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
    return action["runs"]["steps"]


def _step_by_name(name: str) -> dict:
    for step in _action_steps():
        if step.get("name") == name:
            return step
    raise AssertionError(f"step {name!r} not found in {ACTION}")


def test_install_nix_is_gated_on_missing_host_nix() -> None:
    """install-nix-action aborts on a Nix-preinstalled self-hosted runner and
    leaves NIX_CONFIG malformed; it must be skipped when host Nix exists, with
    a detect step preceding it.

    Refs: #1192
    """
    steps = _action_steps()
    detect_idx = next(
        (i for i, s in enumerate(steps) if s.get("id") == DETECT_STEP_ID), None
    )
    assert detect_idx is not None, f"no step with id {DETECT_STEP_ID!r}"
    install_idx = next(
        i for i, s in enumerate(steps) if s.get("name") == INSTALL_STEP_NAME
    )
    assert detect_idx < install_idx, "detect step must precede the install step"
    install_if = _step_by_name(INSTALL_STEP_NAME).get("if", "")
    assert f"steps.{DETECT_STEP_ID}.outputs.has-nix != 'true'" in install_if


def test_host_nix_config_step_writes_wellformed_nix_config(tmp_path: Path) -> None:
    """On the preinstalled-Nix path, the action must export the same Nix
    settings via a well-formed multi-line NIX_CONFIG (the malformed one from
    the aborted installer broke `nix develop` on exo-fleet's runner).

    Refs: #1192
    """
    step = _step_by_name(HOST_NIX_STEP_NAME)
    assert f"steps.{DETECT_STEP_ID}.outputs.has-nix == 'true'" in step.get("if", "")

    github_env = tmp_path / "github_env"
    github_env.touch()
    proc = subprocess.run(
        ["bash", "-c", step["run"]],
        env={**os.environ, "GITHUB_ENV": str(github_env)},
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    parsed = _parse_github_env(github_env.read_text(encoding="utf-8"))
    nix_config = parsed.get("NIX_CONFIG")
    assert nix_config, "NIX_CONFIG not written to GITHUB_ENV"
    got = {}
    for line in nix_config.splitlines():
        assert " = " in line, f"malformed NIX_CONFIG line: {line!r}"
        key, _, value = line.partition(" = ")
        got[key] = value
    assert got == _NIX_SETTINGS


def test_install_and_host_paths_carry_identical_settings() -> None:
    """The fresh-install extra_nix_config and the test's expected host-path
    settings must stay in lockstep — drift would give the two runner classes
    different Nix behavior."""
    install = _step_by_name(INSTALL_STEP_NAME)
    extra = install["with"]["extra_nix_config"]
    got = {}
    for line in extra.strip().splitlines():
        key, _, value = line.partition(" = ")
        got[key] = value
    assert got == _NIX_SETTINGS


# ── Host Nix version capture in the detect step (#1198) ──────────────────────

DETECT_STEP_NAME = "Detect host Nix"

# A representative multi-user host Nix version banner. exo-fleet's wrapper writes
# it to stderr, so a plain `$(nix --version)` capture came back empty.
HOST_NIX_VERSION = "nix (Nix) 2.18.1"


def _write_stderr_version_nix_stub(bin_dir: Path) -> None:
    """A fake `nix` whose `--version` prints ONLY to stderr, mimicking the
    exo-fleet multi-user host wrapper that produced the empty `()` log (#1198).
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "nix"
    stub.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                'if [ "${1:-}" = "--version" ]; then',
                f"  echo {_bash_squote(HOST_NIX_VERSION)} >&2",
                "  exit 0",
                "fi",
                "exit 0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)


def test_detect_step_captures_version_from_stderr(tmp_path: Path) -> None:
    """On a host Nix that writes `--version` to stderr, the detect step must
    still log the real version, not an empty `()`.

    Refs: #1198
    """
    step = _step_by_name(DETECT_STEP_NAME)

    bin_dir = tmp_path / "stub-bin"
    _write_stderr_version_nix_stub(bin_dir)

    github_output = tmp_path / "github_output"
    github_output.touch()

    proc = subprocess.run(
        ["bash", "-c", step["run"]],
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "GITHUB_OUTPUT": str(github_output),
        },
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Host Nix present:" in proc.stdout
    assert HOST_NIX_VERSION in proc.stdout, (
        f"version missing from log line:\n{proc.stdout}"
    )
    assert "()" not in proc.stdout, f"empty version parens in log:\n{proc.stdout}"


# ── Ambient NIX_CONFIG must not corrupt the version probe (#1216) ─────────────

# A malformed ambient NIX_CONFIG as carried by a self-hosted runner's service
# environment (exo-fleet's meatgrinder, exo-pet/exo-fleet#230): nix rejects it
# before printing the version.
MALFORMED_NIX_CONFIG = "experimental-features"
NIX_CONFIG_PARSE_ERROR = (
    "error: syntax error in configuration line "
    "'experimental-features' in \"NIX_CONFIG\""
)


def _write_nix_config_sensitive_nix_stub(bin_dir: Path) -> None:
    """A fake `nix` mimicking nix on exo-fleet's meatgrinder: a malformed ambient
    `NIX_CONFIG` makes `--version` fail with a config parse error *before* the
    version is printed, so a probe that inherits the ambient config captures the
    error instead of the version. With `NIX_CONFIG` scrubbed it prints the
    version normally (#1216).
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "nix"
    stub.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                'if [ "${1:-}" = "--version" ]; then',
                '  if [ -n "${NIX_CONFIG:-}" ]; then',
                f"    echo {_bash_squote(NIX_CONFIG_PARSE_ERROR)} >&2",
                "    exit 1",
                "  fi",
                f"  echo {_bash_squote(HOST_NIX_VERSION)}",
                "  exit 0",
                "fi",
                "exit 0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)


def test_detect_step_probe_scrubs_ambient_nix_config(tmp_path: Path) -> None:
    """A malformed ambient `NIX_CONFIG` (self-hosted runner service env) must not
    corrupt the version probe: the detect log must show the real version, not the
    config parse error the ambient value provokes.

    Refs: #1216
    """
    step = _step_by_name(DETECT_STEP_NAME)

    bin_dir = tmp_path / "stub-bin"
    _write_nix_config_sensitive_nix_stub(bin_dir)

    github_output = tmp_path / "github_output"
    github_output.touch()

    proc = subprocess.run(
        ["bash", "-c", step["run"]],
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "GITHUB_OUTPUT": str(github_output),
            "NIX_CONFIG": MALFORMED_NIX_CONFIG,
        },
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Host Nix present:" in proc.stdout
    assert HOST_NIX_VERSION in proc.stdout, (
        f"version missing from log line:\n{proc.stdout}"
    )
    assert "syntax error in configuration" not in proc.stdout, (
        f"ambient NIX_CONFIG parse error leaked into probe:\n{proc.stdout}"
    )
