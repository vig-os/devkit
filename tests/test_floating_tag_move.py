"""Floating-tag move: the promote step's real bash against a real git remote.

Issue #1508: ``promote-release.yml``'s ``floating-tags`` job pushed with the
Release App token embedded in the push URL, while ``actions/checkout`` persisted
the default ``GITHUB_TOKEN`` as ``http.<host>.extraheader`` — and the extraheader
outranks URL userinfo. The push therefore ran under the Actions identity, which
the job denies (``contents: read``) and the Tag ruleset does not bypass.

It went unnoticed because the code is **unreachable from every current
consumer**: the push form arrived in devkit 1.7.0 (e76c31da, ``Refs: #1377``),
and the only two repos that set ``DEVKIT_FLOATING_TAGS`` — ``vig-os/commit-action``
and ``vig-os/sync-issues-action`` — are both pinned to 1.6.0, where ``move_tag``
used ``gh api`` and no checkout credentials were involved. devkit's own promote
workflow has no floating-tags job at all. So nothing has ever executed this
script, and the shape pins in ``test_promote_release.py`` asserted only that the
steps existed.

These tests execute the step's ``run:`` body against a throwaway ``file://``
remote, with ``gh`` stubbed by a shim that answers the REST ref queries from
that same remote — so create, move, skip and failure are exercised for real. An
identity bug cannot be caught locally (a local remote has no auth), which is why
identity stays pinned structurally in ``test_promote_release.py``; what is
covered here is everything downstream of it.

Refs: #1508, #1377, #1157, #1045
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import WORKFLOWS, load_workflow, steps_of_job

if TYPE_CHECKING:
    from pathlib import Path

PROMOTE = WORKFLOWS / "promote-release.yml"

REPO = "vig-os/testrepo"
VERSION = "1.2.3"
RELEASE_TAG = "v1.2.3"

# A `gh` that answers the two ref reads the step makes, straight from the local
# remote — so the stub can never drift from the fixture it describes.
GH_STUB = r"""#!/usr/bin/env python3
import json
import os
import pathlib
import subprocess
import sys

argv = sys.argv[1:]
origin = os.environ["GH_STUB_ORIGIN"]
with pathlib.Path(os.environ["GH_STUB_LOG"]).open("a") as fh:
    fh.write(json.dumps(argv) + "\n")


def refs():
    out = subprocess.run(
        ["git", "ls-remote", "--tags", origin], capture_output=True, text=True
    ).stdout
    table = {}
    for line in out.splitlines():
        sha, _, ref = line.partition("\t")
        table[ref] = sha
    return table


def emit(payload):
    jq = argv[argv.index("--jq") + 1] if "--jq" in argv else None
    if jq is None:
        print(json.dumps(payload))
        return
    proc = subprocess.run(
        ["jq", "-r", jq], input=json.dumps(payload), capture_output=True, text=True
    )
    if proc.returncode != 0:
        sys.exit(f"gh stub: jq failed for {jq!r}: {proc.stderr}")
    sys.stdout.write(proc.stdout)


if argv and argv[0] == "api":
    path = argv[1]
    table = refs()
    if "/git/ref/tags/" in path:
        name = path.split("/git/ref/tags/", 1)[1]
        ref = f"refs/tags/{name}"
        if ref not in table:
            # gh exits non-zero on 404, which the step treats as "absent".
            sys.exit(f"gh: Not Found ({ref})")
        peeled = table.get(ref + "^{}")
        kind = "tag" if peeled else "commit"
        emit({"object": {"sha": table[ref], "type": kind}})
        sys.exit(0)
    if "/git/tags/" in path:
        # Peel an annotated tag object to the commit it points at.
        sha = path.rsplit("/", 1)[1]
        for ref, value in table.items():
            if value == sha and (ref + "^{}") in table:
                emit({"object": {"sha": table[ref + "^{}"]}})
                sys.exit(0)
        sys.exit(f"gh: no annotated tag object {sha}")

sys.exit(f"gh stub: unsupported invocation {argv!r}")
"""


def _move_step_script() -> str:
    steps = steps_of_job(load_workflow(PROMOTE), "floating-tags")
    move = next(s for s in steps if "floating" in str(s.get("name", "")).lower())
    return str(move["run"])


def _git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


class _Remote:
    """A throwaway origin plus a workspace, mimicking the promote checkout."""

    def __init__(self, tmp_path: Path, *, annotated: bool = False) -> None:
        self.origin = tmp_path / "origin.git"
        self.work = tmp_path / "work"
        seed = tmp_path / "seed"
        subprocess.run(
            ["git", "init", "-q", "-b", "main", "--bare", str(self.origin)], check=True
        )
        # `file://` (not a bare path): a local-path clone silently ignores
        # --depth, and the step's shallow fetch is part of what is under test.
        self.url = f"file://{self.origin}"
        subprocess.run(["git", "clone", "-q", self.url, str(seed)], check=True)
        for key, value in (
            ("user.email", "test@example.com"),
            ("user.name", "Test User"),
            ("commit.gpgsign", "false"),
            ("tag.gpgsign", "false"),
        ):
            _git("config", key, value, cwd=seed)

        (seed / "README.md").write_text("old\n", encoding="utf-8")
        _git("add", "-A", cwd=seed)
        _git("commit", "-qm", "chore: previous release", cwd=seed)
        self.previous_sha = _git("rev-parse", "HEAD", cwd=seed)
        (seed / "README.md").write_text("new\n", encoding="utf-8")
        _git("commit", "-qam", "chore: release 1.2.3", cwd=seed)
        self.target_sha = _git("rev-parse", "HEAD", cwd=seed)
        _git("push", "-q", "origin", "HEAD:refs/heads/main", cwd=seed)

        if annotated:
            _git("tag", "-a", RELEASE_TAG, "-m", "release", cwd=seed)
        else:
            _git("tag", RELEASE_TAG, cwd=seed)
        _git("push", "-q", "origin", f"refs/tags/{RELEASE_TAG}", cwd=seed)
        self._seed = seed

        # The workspace the job pushes from: a fresh checkout of the remote.
        subprocess.run(["git", "clone", "-q", self.url, str(self.work)], check=True)

        stub_dir = tmp_path / "stub-bin"
        stub_dir.mkdir()
        gh = stub_dir / "gh"
        gh.write_text(GH_STUB, encoding="utf-8")
        gh.chmod(0o755)
        self._log = tmp_path / "gh-calls.jsonl"
        self._env = {
            **os.environ,
            "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}",
            "GH_STUB_ORIGIN": self.url,
            "GH_STUB_LOG": str(self._log),
            "GH_TOKEN": "stub-token",
            "GITHUB_REPOSITORY": REPO,
            "VERSION": VERSION,
            "TAG_PREFIX": "v",
            "FLOATING_TAGS": "major,minor",
        }

    def place_tag(self, name: str, sha: str) -> None:
        """Pre-existing floating tag on the remote."""
        _git("push", "-q", "-f", "origin", f"{sha}:refs/tags/{name}", cwd=self._seed)

    def reject_pushes(self) -> None:
        """Make the remote refuse every push, standing in for a ruleset denial."""
        hook = self.origin / "hooks" / "pre-receive"
        hook.write_text(
            "#!/usr/bin/env bash\necho 'refusing (test)' >&2\nexit 1\n",
            encoding="utf-8",
        )
        hook.chmod(0o755)

    def remote_tag(self, name: str) -> str:
        out = _git("ls-remote", self.url, f"refs/tags/{name}", cwd=self.work)
        return out.split()[0] if out else ""

    def run(self, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-c", _move_step_script()],
            cwd=self.work,
            env={**self._env, **env},
            capture_output=True,
            text=True,
            check=False,
        )

    @property
    def pushes(self) -> list[list[str]]:
        if not self._log.exists():
            return []
        return [json.loads(line) for line in self._log.read_text().splitlines()]


def _ok(proc: subprocess.CompletedProcess[str]) -> None:
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"


def test_first_release_of_a_level_creates_the_tag(tmp_path: Path) -> None:
    """The #1157 case: a floating level that does not exist yet must be created.

    This is the scenario the whole push rewrite (#1377) exists for, and the one
    that still needed a manual fix on ``sync-issues-action`` v0.5.0.
    """
    remote = _Remote(tmp_path)

    proc = remote.run()

    _ok(proc)
    assert remote.remote_tag("v1") == remote.target_sha, (
        "the major floating tag must be created at the release commit"
    )
    assert remote.remote_tag("v1.2") == remote.target_sha, (
        "the minor floating tag must be created at the release commit"
    )


def test_existing_level_is_force_moved(tmp_path: Path) -> None:
    """A floating tag from the previous release moves to the new commit."""
    remote = _Remote(tmp_path)
    remote.place_tag("v1", remote.previous_sha)

    proc = remote.run()

    _ok(proc)
    assert remote.remote_tag("v1") == remote.target_sha
    assert "v1 -> " in proc.stdout


def test_tag_already_at_target_is_skipped(tmp_path: Path) -> None:
    """Re-running promote must be a no-op, not a redundant force-push."""
    remote = _Remote(tmp_path)
    remote.place_tag("v1", remote.target_sha)
    remote.place_tag("v1.2", remote.target_sha)

    proc = remote.run()

    _ok(proc)
    assert "already at" in proc.stdout
    assert remote.remote_tag("v1") == remote.target_sha


def test_annotated_release_tag_is_peeled_to_its_commit(tmp_path: Path) -> None:
    """Older scaffolds published ANNOTATED release tags; floating tags are
    lightweight refs at the commit, so the tag object must be peeled first."""
    remote = _Remote(tmp_path, annotated=True)

    proc = remote.run()

    _ok(proc)
    assert remote.remote_tag("v1") == remote.target_sha, (
        "a floating tag must point at the commit, never at the tag object"
    )


def test_refused_push_fails_loud_with_remediation(tmp_path: Path) -> None:
    """A denied push must not pass silently: the release is already published,
    so only the advertised ``@v1`` pin would be missing (#1157, #1158)."""
    remote = _Remote(tmp_path)
    remote.reject_pushes()

    proc = remote.run()

    assert proc.returncode != 0, "a refused tag push must fail the job"
    combined = proc.stdout + proc.stderr
    assert "::error title=Floating tag" in combined
    assert "ruleset" in combined.lower()


def test_unknown_level_warns_without_failing(tmp_path: Path) -> None:
    """An unrecognised DEVKIT_FLOATING_TAGS entry is a warning, not a failure."""
    remote = _Remote(tmp_path)

    proc = remote.run(FLOATING_TAGS="major,patch")

    _ok(proc)
    assert "::warning::Unknown DEVKIT_FLOATING_TAGS level 'patch'" in proc.stdout
    assert remote.remote_tag("v1") == remote.target_sha


@pytest.mark.parametrize("levels", ["major", "minor"])
def test_single_level_moves_only_that_level(tmp_path: Path, levels: str) -> None:
    """Each opt-in level is independent."""
    remote = _Remote(tmp_path)

    proc = remote.run(FLOATING_TAGS=levels)

    _ok(proc)
    moved, untouched = ("v1", "v1.2") if levels == "major" else ("v1.2", "v1")
    assert remote.remote_tag(moved) == remote.target_sha
    assert remote.remote_tag(untouched) == ""
