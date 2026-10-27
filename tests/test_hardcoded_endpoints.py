"""Contract for the default-on endpoint lint (ADR §10)."""

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
    "source",
    [
        'client(endpoint_url="https://storage.service/api")',
        'endpoint-url: "https://storage.service"',
        '{"endpointUrl": "http://storage.service"}',
        "export AWS_ENDPOINT_URL_S3=https://storage.service",
        "AWS_ACCESS_KEY_ID=literal",
        'AWS_SECRET_ACCESS_KEY: "literal"',
        'AWS_SESSION_TOKEN = "literal"',
        '{"AWS_ENDPOINT_URL": "https://storage.service"}',
        'os.environ["AWS_SESSION_TOKEN"] = "literal"',
    ],
)
def test_positive(tmp_path, source):
    path = tmp_path / "config"
    path.write_text(source + "\n")
    result = lint(path)
    assert result.returncode == 1
    assert f"{path}:1:" in result.stderr
    assert "literal" not in result.stderr
    assert "storage.service" not in result.stderr


@pytest.mark.parametrize(
    "source",
    [
        "AWS_ENDPOINT_URL=$ENDPOINT",
        'AWS_SECRET_ACCESS_KEY="${SECRET}"',
        "AWS_SESSION_TOKEN: ${{ secrets.TOKEN }}",
        'os.environ["AWS_ACCESS_KEY_ID"] = os.getenv("KEY")',
        'client(endpoint_url=os.environ["AWS_ENDPOINT_URL"])',
        "AWS_SESSION_TOKEN=literal # devkit: allow-endpoint",
        'endpointUrl: "https://storage.service" # devkit: allow-endpoint',
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
    path = tmp_path / "config"
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
