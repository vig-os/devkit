"""
Unit tests for the ``scaffold_files`` walk shared by the placeholder scans.

A scaffolded workspace is a git repository, and the scaffold commit spawns a
detached ``git maintenance run --auto`` that may repack and delete every loose
object while a test is still walking the tree. Git internals can never hold a
scaffold placeholder, so the walk skips ``.git/`` entirely (#1815).
"""

import subprocess

from .conftest import scaffold_files


def _git(cwd, *args):
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def test_scaffold_files_skips_git_directory(tmp_path):
    (tmp_path / "README.md").write_text("hello\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "script.sh").write_text("echo hi\n")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")

    files = scaffold_files(tmp_path)

    assert files == [tmp_path / "README.md", tmp_path / "sub" / "script.sh"]


def test_scaffold_files_returns_materialized_list(tmp_path):
    (tmp_path / "a.txt").write_text("a\n")

    files = scaffold_files(tmp_path)

    assert isinstance(files, list)
