"""Contract for the default-on endpoint lint (ADR §10)."""

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def lint(path):
    return subprocess.run(
        [sys.executable, "-m", "vig_utils.check_hardcoded_endpoints", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("name", "source"),
    [
        ("config.py", 'client(endpoint_url="https://192.0.2.10/api")'),
        ("config.yaml", 'endpoint-url: "https://192.0.2.10"'),
        ("config.json", '{"endpointUrl": "http://192.0.2.10"}'),
        ("config.sh", "export AWS_ENDPOINT_URL_S3=https://192.0.2.10"),
        (".env", "AWS_ACCESS_KEY_ID=literal"),
        ("config.yaml", 'AWS_SECRET_ACCESS_KEY: "literal"'),
        ("config.toml", 'AWS_SESSION_TOKEN = "literal"'),
        ("config.json", '{"AWS_ENDPOINT_URL": "https://192.0.2.10"}'),
        ("config.py", 'os.environ["AWS_SESSION_TOKEN"] = "literal"'),
    ],
)
def test_positive(tmp_path, name, source):
    path = tmp_path / name
    path.write_text(source + "\n")
    result = lint(path)
    assert result.returncode == 1
    assert f"{path}:1:" in result.stderr
    assert "literal" not in result.stderr
    assert "192.0.2.10" not in result.stderr


@pytest.mark.parametrize(
    "source",
    [
        "AWS_ENDPOINT_URL=$ENDPOINT",
        'AWS_SECRET_ACCESS_KEY="${SECRET}"',
        "AWS_SESSION_TOKEN: ${{ secrets.TOKEN }}",
        'os.environ["AWS_ACCESS_KEY_ID"] = os.getenv("KEY")',
        'client(endpoint_url=os.environ["AWS_ENDPOINT_URL"])',
        "AWS_SESSION_TOKEN=literal # devkit: allow-endpoint",
        'endpointUrl: "https://192.0.2.10" # devkit: allow-endpoint',
        "runs-on: pool-s",
    ]
    + [
        f'endpoint_url = "http://{host}:9000/path"'
        for host in (
            "localhost",
            "127.0.0.1",
            "[::1]",
            "example.com",
            "storage.example",
            "storage.test",
            "storage.invalid",
        )
    ],
)
def test_exemptions(tmp_path, source):
    name = (
        "config.py" if source.startswith(("os.environ", "client(")) else "config.yaml"
    )
    if source.startswith("endpoint_url ="):
        name = "config.toml"
    path = tmp_path / name
    path.write_text(source + "\n")
    result = lint(path)
    assert result.returncode == 0, result.stderr


def test_own_tree():
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    result = subprocess.run(
        [sys.executable, "-m", "vig_utils.check_hardcoded_endpoints"]
        + [str(ROOT / p.decode()) for p in paths if p],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_hook_surfaces():
    for config in (
        ".pre-commit-config.yaml",
        "assets/workspace/.pre-commit-config.yaml",
    ):
        data = yaml.safe_load((ROOT / config).read_text())
        hooks = {h["id"]: h for repo in data["repos"] for h in repo["hooks"]}
        assert (
            hooks["no-hardcoded-endpoints"]["entry"]
            == "uv run check-hardcoded-endpoints"
        )
    source = (ROOT / "nix/hooks.nix").read_text()
    block = source.split("    no-hardcoded-endpoints = {", 1)[1].split("\n    };", 1)[0]
    assert "scaffold = true;" in block
    assert "consumer =" in block
    assert "enable = true;" in block


@pytest.mark.parametrize(
    ("name", "source"),
    [
        ("config.py", 'client(\n endpoint_url="https://192.0.2.10")'),
        ("config.py", 'os.environ["AWS_ACCESS_KEY_ID"] = "literal"'),
        ("config.yaml", "endpoint-url: https://192.0.2.10"),
        ("config.yaml", "AWS_SECRET_ACCESS_KEY: >-\n  literal"),
        ("config.json", '{"endpointUrl":\n "https://192.0.2.10"}'),
        ("config.toml", 'AWS_SESSION_TOKEN = "literal"'),
        ("config.toml", 'endpoint_url = """\nhttps://192.0.2.10"""'),
        ("config.sh", "export AWS_ENDPOINT_URL=https://192.0.2.10"),
        (".env", "AWS_ACCESS_KEY_ID=literal"),
    ],
)
def test_language_literals(tmp_path, name, source):
    path = tmp_path / name
    path.write_text(source + "\n")
    assert lint(path).returncode == 1


@pytest.mark.parametrize("name", ["README.md", "guide.rst", "notes.txt", "other.conf"])
def test_other_text_is_out_of_scope(tmp_path, name):
    path = tmp_path / name
    path.write_text("```sh\nAWS_ACCESS_KEY_ID=<your-key>\n```\n")
    result = lint(path)
    assert result.returncode == 0
    assert result.stderr == ""


@pytest.mark.parametrize(
    "source",
    [
        'AWS_ACCESS_KEY_ID="$(cat f)" cmd',
        "AWS_ACCESS_KEY_ID=$(cat f) cmd",
        "AWS_ACCESS_KEY_ID=`cat f` cmd",
        'AWS_ACCESS_KEY_ID="`cat f`" cmd',
        'AWS_ACCESS_KEY_ID="" cmd',
        "AWS_ACCESS_KEY_ID= cmd",
        'echo "AWS_ACCESS_KEY_ID: set"',
        'echo "AWS_ACCESS_KEY_ID=example"',
        "# AWS_ACCESS_KEY_ID=example",
    ],
)
def test_shell_non_literals(tmp_path, source):
    path = tmp_path / "config.sh"
    path.write_text(source + "\n")
    result = lint(path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "name,shebang",
    [
        ("config.bash", ""),
        (".env.local", ""),
        ("config.env", ""),
        ("script", "#!/bin/sh\n"),
        ("script", "#!/usr/bin/env bash\n"),
    ],
)
def test_shell_and_dotenv_discovery(tmp_path, name, shebang):
    path = tmp_path / name
    path.write_text(shebang + "AWS_ACCESS_KEY_ID=literal\n")
    assert lint(path).returncode == 1


@pytest.mark.parametrize(
    "name,kind,content",
    [
        ("template.yaml", "yaml", b"{{ .Values.foo }}\n"),
        ("legacy.py", "python", b'print "hello"\n'),
        ("config.toml", "toml", b"# \xff\n"),
    ],
)
@pytest.mark.parametrize("planted", [False, True])
def test_parse_fallback(tmp_path, name, kind, content, planted):
    path = tmp_path / name
    if planted:
        content += b'AWS_ACCESS_KEY_ID="literal"\n'
    path.write_bytes(content)
    result = lint(path)
    assert result.returncode == int(planted), result.stderr
    notice = f"env-only-lint: {path}: not parseable as {kind}, scanned line-by-line"
    assert result.stderr.count(notice) == 1
    if planted:
        assert f"{path}:2:" in result.stderr
    assert "literal" not in result.stderr


def test_compose_environment_list(tmp_path):
    path = tmp_path / "compose.yaml"
    path.write_text(
        "services:\n  app:\n    environment:\n      - AWS_ENDPOINT_URL=http://198.51.100.7\n"
    )
    result = lint(path)
    assert result.returncode == 1
    assert f"{path}:4:" in result.stderr


@pytest.mark.parametrize(
    "host",
    [
        "example.com",
        "example.org",
        "example.net",
        "example",
        "test",
        "invalid",
        "localhost",
        "sub.example.com",
        "sub.example.org",
        "sub.example.net",
        "sub.example",
        "sub.test",
        "sub.invalid",
        "sub.localhost",
    ],
)
def test_reserved_hosts(tmp_path, host):
    path = tmp_path / "config.py"
    path.write_text(f'client(endpoint_url="https://{host}/api")\n')
    assert lint(path).returncode == 0


def test_hook_file_types():
    for config in (
        ".pre-commit-config.yaml",
        "assets/workspace/.pre-commit-config.yaml",
    ):
        data = yaml.safe_load((ROOT / config).read_text())
        hooks = {h["id"]: h for repo in data["repos"] for h in repo["hooks"]}
        hook = hooks["no-hardcoded-endpoints"]
        assert set(hook["types_or"]) == {"shell", "python", "yaml", "toml", "json"}
        dotenv = hooks["no-hardcoded-endpoints-dotenv"]
        for filename in (".env", ".env.local", "settings.env"):
            assert re.search(dotenv["files"], filename)
        for filename in ("README.md", "notes.txt", "other.conf"):
            assert not re.search(dotenv["files"], filename)
