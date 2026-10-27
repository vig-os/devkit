"""ADR §10 site-private gitleaks hook contract."""

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = """[[rules]]
id = "fixture-host"
description = "Private description: storage.example"
regex = 'storage\\.example'
"""


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")
    (path / ".gitignore").write_text(".site/\n")
    git(path, "add", ".gitignore")
    git(path, "-c", "core.hooksPath=/dev/null", "commit", "-m", "initial")
    monkeypatch.delenv("DEVKIT_LEAK_PATTERNS", raising=False)
    return path


def patterns(repo):
    path = repo / ".site" / "leak-patterns.toml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(PATTERNS)
    return path


def scan(repo, *args, **env):
    return subprocess.run(
        [sys.executable, "-m", "vig_utils.site_leak_check", *args],
        cwd=repo,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        check=False,
    )


def test_no_patterns_is_silent(repo):
    result = scan(repo)
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_staged_match_is_redacted_and_uses_index(repo):
    patterns(repo)
    source = repo / "config.txt"
    source.write_text("storage.example\n")
    git(repo, "add", "config.txt")
    source.write_text("clean\n")
    result = scan(repo)
    assert result.returncode == 1, result.stderr
    assert "config.txt:1: fixture-host" in result.stderr
    assert "storage.example" not in result.stdout + result.stderr
    assert "Private description" not in result.stdout + result.stderr
    assert scan(repo, "--all-files").returncode == 0


def test_environment_overrides_site_patterns(repo, tmp_path):
    patterns(repo).write_text("invalid private config")
    external = tmp_path / "patterns.toml"
    external.write_text(PATTERNS)
    (repo / "config.txt").write_text("storage.example\n")
    git(repo, "add", "config.txt")
    result = scan(repo, DEVKIT_LEAK_PATTERNS=str(external))
    assert result.returncode == 1
    assert "config.txt:1: fixture-host" in result.stderr


@pytest.mark.parametrize(
    "location,tracked", [("patterns.toml", False), (".site/leak-patterns.toml", True)]
)
def test_unsafe_pattern_location_fails(repo, location, tracked):
    path = repo / location
    path.parent.mkdir(exist_ok=True)
    path.write_text(PATTERNS)
    if tracked:
        git(repo, "add", "-f", location)
    result = scan(repo, DEVKIT_LEAK_PATTERNS=str(path))
    assert result.returncode == 2
    assert "pattern file" in result.stderr
    assert "storage.example" not in result.stderr


def test_symlink_cannot_hide_in_tree_patterns(repo):
    outside_site = repo / "patterns.toml"
    outside_site.write_text(PATTERNS)
    path = repo / ".site" / "leak-patterns.toml"
    path.parent.mkdir()
    path.symlink_to(outside_site)
    assert scan(repo).returncode == 2


def test_all_files_and_precommit_filenames_scan_working_tree(repo):
    patterns(repo)
    (repo / "notes.md").write_text("storage.example\n")
    assert scan(repo).returncode == 0
    for args in [("--all-files",), ("notes.md",)]:
        result = scan(repo, *args)
        assert result.returncode == 1
        assert "notes.md:1: fixture-host" in result.stderr
        assert "storage.example" not in result.stderr + result.stdout


@pytest.mark.parametrize("value", ["relative.toml", "/nonexistent/patterns.toml"])
def test_explicit_invalid_path_does_not_fall_back(repo, value):
    patterns(repo)
    assert scan(repo, DEVKIT_LEAK_PATTERNS=value).returncode == 2


def test_scanner_errors_do_not_disclose_private_config(repo):
    patterns(repo).write_text("invalid storage.example")
    result = scan(repo, "--all-files")
    assert result.returncode == 2
    assert "storage.example" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_default_hook_on_runner_and_scaffold():
    for path in [
        ROOT / ".pre-commit-config.yaml",
        ROOT / "assets/workspace/.pre-commit-config.yaml",
    ]:
        config = yaml.safe_load(path.read_text())
        hook = next(
            h
            for r in config["repos"]
            for h in r["hooks"]
            if h["id"] == "site-leak-check"
        )
        assert hook["entry"] == "uv run site-leak-check"
        assert hook["types"] == ["text"]
    source = (ROOT / "nix/hooks.nix").read_text()
    block = source.split("    site-leak-check = {", 1)[1].split(
        "    no-hardcoded-endpoints = {", 1
    )[0]
    assert block.count("enable = true;") == 2
    assert "pkgs.gitleaks" in block


def test_no_patterns_outside_git_is_silent(tmp_path):
    result = scan(tmp_path, "--all-files", "--gitleaks", "/nonexistent/gitleaks")
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_external_tracked_patterns_are_rejected(repo, tmp_path):
    private = tmp_path / "config-repo"
    private.mkdir()
    git(private, "init")
    path = private / "patterns.toml"
    path.write_text(PATTERNS)
    git(private, "add", "patterns.toml")
    result = scan(repo, DEVKIT_LEAK_PATTERNS=str(path))
    assert result.returncode == 2


@pytest.mark.parametrize("mode", [(), ("--all-files",), ("config.txt",)])
def test_gitleaks_pragma_is_an_escape_hatch(repo, mode):
    patterns(repo)
    (repo / "config.txt").write_text("storage.example # gitleaks:allow\n")
    git(repo, "add", "config.txt")
    assert scan(repo, *mode).returncode == 0


@pytest.mark.parametrize("allowed_path", ["config.txt", "^config[.]txt$"])
def test_gitleaks_allowlist_is_an_escape_hatch(repo, allowed_path):
    patterns(repo).write_text(PATTERNS + f'\n[allowlist]\npaths = ["{allowed_path}"]\n')
    (repo / "config.txt").write_text("storage.example\n")
    git(repo, "add", "config.txt")
    assert scan(repo).returncode == 0
    assert scan(repo, "--all-files").returncode == 0


def test_pattern_lookup_from_subdirectory(repo):
    patterns(repo)
    subdirectory = repo / "nested"
    subdirectory.mkdir()
    (subdirectory / "config.txt").write_text("storage.example\n")
    result = scan(subdirectory, "config.txt")
    assert result.returncode == 1
    assert "nested/config.txt:1: fixture-host" in result.stderr


def test_repository_directory_is_not_a_pattern_file(repo):
    result = scan(repo, DEVKIT_LEAK_PATTERNS=str(repo))
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


@pytest.fixture
def installed_hook(repo):
    """Install the real pre-commit-compatible hook runner used by devkit."""
    runner = shutil.which("pre-commit") or shutil.which("prek")
    assert runner, "the development environment must provide a hook runner"
    config = {
        "repos": [
            {
                "repo": "local",
                "hooks": [
                    {
                        "id": "site-leak-check",
                        "name": "site-leak-check",
                        "entry": shlex.join(
                            [sys.executable, "-m", "vig_utils.site_leak_check"]
                        ),
                        "language": "system",
                        "types": ["text"],
                    }
                ],
            }
        ]
    }
    (repo / ".pre-commit-config.yaml").write_text(yaml.safe_dump(config))
    git(repo, "add", ".pre-commit-config.yaml")
    subprocess.run([runner, "install"], cwd=repo, capture_output=True, check=True)
    return repo


def commit(repo):
    return subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "fixture change"],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "mode",
    [(), ("d.txt", ".gitleaksignore", ".gitleaks.toml"), ("--all-files",), "commit"],
)
def test_repository_scanner_settings_cannot_suppress_site_rules(installed_hook, mode):
    repo = installed_hook
    patterns(repo)
    (repo / "d.txt").write_text("storage.example\n")
    (repo / ".gitleaksignore").write_text("d.txt:fixture-host:1\n")
    (repo / ".gitleaks.toml").write_text(
        '[[rules]]\nid = "repo-only"\nregex = "never-match-config"\n'
        '[allowlist]\npaths = [".*"]\n'
    )
    git(repo, "add", "d.txt", ".gitleaksignore", ".gitleaks.toml")
    result = commit(repo) if mode == "commit" else scan(repo, *mode)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "d.txt:1: fixture-host" in result.stdout + result.stderr
    assert "storage.example" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "mode", [(), (".site/bindings.toml",), ("--all-files",), "commit"]
)
def test_tracked_site_bindings_are_scanned(installed_hook, mode):
    repo = installed_hook
    patterns(repo)
    (repo / ".site/bindings.toml").write_text('location = "storage.example"\n')
    git(repo, "add", "-f", ".site/bindings.toml")
    result = commit(repo) if mode == "commit" else scan(repo, *mode)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ".site/bindings.toml:1: fixture-host" in result.stdout + result.stderr
    assert "storage.example" not in result.stdout + result.stderr


def test_active_untracked_patterns_are_not_scanned_as_input(repo):
    path = patterns(repo)
    assert scan(repo, str(path)).returncode == 0


@pytest.mark.parametrize(
    "content",
    [
        "",
        '[[rule]]\nid = "fixture-host"\nregex = "storage[.]example"\n',
        "rules = []\n",
        '[[rules]]\nid = "fixture-host"\n',
    ],
)
@pytest.mark.parametrize("mode", [(), ("--all-files",), "commit"])
def test_present_patterns_need_usable_rules(installed_hook, content, mode):
    repo = installed_hook
    path = patterns(repo)
    path.write_text(content)
    (repo / "d.txt").write_text("storage.example\n")
    git(repo, "add", "d.txt")
    result = commit(repo) if mode == "commit" else scan(repo, *mode)
    output = result.stdout + result.stderr
    if mode == "commit":
        assert result.returncode == 1
        assert "exit code: 2" in output
    else:
        assert result.returncode == 2
    assert str(path) in output
    assert "no usable [[rules]]" in output
    assert "storage.example" not in output
    assert "Traceback" not in output


def test_scanner_report_is_redacted(repo, monkeypatch):
    import json

    from vig_utils import site_leak_check

    patterns(repo)
    (repo / "d.txt").write_text("storage.example\n")
    git(repo, "add", "d.txt")
    original = site_leak_check.publish_findings
    protected_fields = []

    def inspect_report(report, tree):
        for finding in json.loads(report.read_text()):
            protected_fields.extend([finding["Secret"], finding["Match"]])
        return original(report, tree)

    monkeypatch.setattr(site_leak_check, "publish_findings", inspect_report)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(sys, "argv", ["site-leak-check"])
    assert site_leak_check.main() == 1
    assert protected_fields
    assert all("storage.example" not in field for field in protected_fields)


@pytest.mark.parametrize("mode", [(), (".gitleaksignore",), ("--all-files",), "commit"])
def test_repository_ignore_file_is_still_scanned_as_data(installed_hook, mode):
    repo = installed_hook
    patterns(repo)
    (repo / ".gitleaksignore").write_text(
        ".gitleaksignore:fixture-host:2\nstorage.example\n"
    )
    git(repo, "add", ".gitleaksignore")
    result = commit(repo) if mode == "commit" else scan(repo, *mode)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ".gitleaksignore:2: fixture-host" in result.stdout + result.stderr


def test_finding_paths_are_printed_as_is(repo):
    patterns(repo)
    path = "storage.example notes.txt"
    (repo / path).write_text("storage.example\n")
    assert scan(repo, path).stderr == f"{path}:1: fixture-host\n"


def test_linked_worktree_needs_its_own_patterns_or_environment(repo, tmp_path):
    config = patterns(repo)
    linked = tmp_path / "linked"
    git(repo, "worktree", "add", "--detach", str(linked))
    (linked / "d.txt").write_text("storage.example\n")
    git(linked, "add", "d.txt")
    result = scan(linked)
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")
    configured = scan(linked, DEVKIT_LEAK_PATTERNS=str(config))
    assert configured.returncode == 1
    assert "d.txt:1: fixture-host" in configured.stderr
