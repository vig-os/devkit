"""Site configuration and initializer contract tests (ADR §8–§9)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def cli(root, command, *args):
    result = subprocess.run(
        [sys.executable, "-m", "vig_utils.site_config", command, *args],
        cwd=root,
        input="",
        capture_output=True,
        text=True,
        check=False,
    )
    assert "No module named" not in result.stderr, result.stderr
    return result


def config(root, name="fixture", extra=""):
    path = root / ".site" / f"{name}.toml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(f'schema = 1\nsite = "{name}"\n' + extra)
    return path


@pytest.mark.parametrize("location", ["", "/srv/data", "s3://bucket/data"])
def test_valid_bindings(tmp_path, location):
    config(tmp_path, extra=f'[datasets.raw]\nlocation = "{location}"\n')
    result = cli(tmp_path, "check-site-config")
    assert result.returncode == 0, result.stderr
    assert ("unbound" in result.stderr) == (location == "")
    if not location:
        assert "raw" in result.stderr


@pytest.mark.parametrize(
    "extra",
    [
        '[datasets.raw]\nlocation = "relative/data"\n',
        '[datasets.raw]\nlocation = "s3://user:pw@bucket/data"\n',
        '[hints]\nACCESS_KEY = "hidden"\n',
        "[hints]\nrunner = 1\n",
        "[datasets.raw]\nlocation = 2\n",
    ],
)
def test_invalid_bindings(tmp_path, extra):
    config(tmp_path, extra=extra)
    assert cli(tmp_path, "check-site-config").returncode != 0


@pytest.mark.parametrize(
    "text",
    [
        'schema = 2\nsite = "fixture"',
        'schema = true\nsite = "fixture"',
        'schema = 1\nsite = "other"',
    ],
)
def test_schema(tmp_path, text):
    config(tmp_path).write_text(text)
    assert cli(tmp_path, "check-site-config").returncode != 0


def test_lookup(tmp_path, monkeypatch):
    monkeypatch.delenv("DEVKIT_SITE", raising=False)
    assert cli(tmp_path, "check-site-config", "--print-path").stdout == ""
    first = config(tmp_path)
    (first.parent / "leak-patterns.toml").write_text("")
    assert cli(tmp_path, "check-site-config", "--print-path").stdout.strip() == str(
        first
    )
    config(tmp_path, "second")
    result = cli(tmp_path, "check-site-config")
    assert result.returncode != 0
    assert "fixture" in result.stderr and "second" in result.stderr
    monkeypatch.setenv("DEVKIT_SITE", "fixture")
    assert cli(tmp_path, "check-site-config").returncode == 0
    monkeypatch.setenv("DEVKIT_SITE", "missing")
    assert cli(tmp_path, "check-site-config").returncode != 0


def initializer(tmp_path, monkeypatch, name="fixture", body=None):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    script = bindir / f"devkit-site-init-{name}"
    script.write_text(
        "#!/bin/sh\n"
        + (
            body
            or (
                'test "$PWD" = "$(dirname "$DEVKIT_SITE_DIR" | xargs dirname)" || exit 8\n'
                'test "$DEVKIT_DATA_MANIFEST" = "$PWD/data.toml" || exit 9\n'
                'printf \'schema = 1\\nsite = "%s"\\n\' "$DEVKIT_SITE" > "$DEVKIT_SITE_DIR/$DEVKIT_SITE.toml"\n'
            )
        )
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    (tmp_path / "data.toml").write_text("[datasets.raw]\n")


def test_discovery_force_and_ambiguity(tmp_path, monkeypatch):
    initializer(tmp_path, monkeypatch)
    assert cli(tmp_path, "site-init").returncode == 0
    path = tmp_path / ".site/fixture.toml"
    before = path.read_bytes()
    assert cli(tmp_path, "site-init").returncode != 0
    assert path.read_bytes() == before
    assert cli(tmp_path, "site-init", "--force").returncode == 0
    initializer(tmp_path, monkeypatch, "second")
    result = cli(tmp_path, "site-init")
    assert result.returncode != 0
    assert "fixture" in result.stderr and "second" in result.stderr
    assert cli(tmp_path, "site-init", "second").returncode == 0


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ('touch "$DEVKIT_SITE_DIR/partial"\nexit 7\n', 7),
        ('echo "schema = 2" > "$DEVKIT_SITE_DIR/$DEVKIT_SITE.toml"\n', 1),
    ],
)
def test_failed_initializer_cleans_up(tmp_path, monkeypatch, body, code):
    initializer(tmp_path, monkeypatch, body=body)
    result = cli(tmp_path, "site-init")
    assert result.returncode == code, result.stderr
    assert not list((tmp_path / ".site").iterdir())


def test_non_tty_fallback_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    (tmp_path / "data.toml").write_text("[datasets.raw]\n[datasets.processed]\n")
    result = cli(tmp_path, "site-init")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(tmp_path / ".site/local.toml")
    result = cli(tmp_path, "check-site-config")
    assert result.returncode == 0
    assert all(name in result.stderr for name in ("unbound", "raw", "processed"))


def test_scaffold_integration(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(
        (ROOT / "assets/workspace/.gitignore").read_text()
    )
    for directory in (".site", ".aws"):
        result = subprocess.run(
            ["git", "check-ignore", directory + "/fixture"],
            cwd=tmp_path,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0
    recipe = (ROOT / "assets/workspace/justfile").read_text()
    assert "site-init" in recipe
    scripts = (ROOT / "packages/vig-utils/pyproject.toml").read_text()
    assert 'check-site-config = "vig_utils.site_config:main"' in scripts
    assert 'site-init = "vig_utils.site_config:site_init"' in scripts
