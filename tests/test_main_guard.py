"""Soft main guard (#1892): shape + executed-script tests for main-guard.yml.

The reusable workflow flags commits that reach the guarded branch without a
merged PR. Shape assertions pin the contract a caller depends on (a
``workflow_call`` with least-privilege permissions and an alert-only job); the
behaviour tests EXECUTE the real ``run:`` script against a fake ``gh`` backed by
JSON fixtures, because a plausible-looking ``jq`` filter or retry loop is not
the same as a working one.

Refs: #1892
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import REPO_ROOT, jobs, load_workflow, on_block, step_by_id

if TYPE_CHECKING:
    from pathlib import Path

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "main-guard.yml"
ZERO = "0" * 40

# A stand-in for `gh`: reads fixtures from $FIX, applies the caller's `-q` jq
# filter like the real CLI does, and logs every write to $FIX/writes.log.
FAKE_GH = r"""#!/usr/bin/env bash
set -euo pipefail
args=("$@")
log() { printf '%s\n' "$*" >> "$FIX/calls.log"; }
q=""; for ((i=0;i<${#args[@]};i++)); do [ "${args[i]}" = "-q" ] && q="${args[i+1]}"; done
case "${args[0]} ${args[1]}" in
  "api --paginate")
    [ -f "$FIX/compare.txt" ] || exit 1
    cat "$FIX/compare.txt" ;;
  "api repos/"*) ;;
esac
if [ "${args[0]}" = api ] && [ "${args[1]}" != --paginate ]; then
  path="${args[1]}"; sha="${path#*/commits/}"
  if [[ "$sha" == */pulls ]]; then
    sha="${sha%/pulls}"; log "pulls $sha"
    n=$(grep -c "^pulls $sha\$" "$FIX/calls.log")
    # lag: the Nth lookup is the first to return data (default: immediately)
    lag=$(cat "$FIX/lag.txt" 2>/dev/null || echo 1)
    if [ "$n" -lt "$lag" ]; then echo '[]' | jq -r "$q"; else jq -r "$q" "$FIX/pulls-$sha.json"; fi
  else
    jq -r "$q" "$FIX/commit-$sha.json"
  fi
  exit 0
fi
case "${args[0]} ${args[1]}" in
  "label create") log "label create ${args[2]}" ;;
  "issue list")   [ -f "$FIX/open-issue.txt" ] && cat "$FIX/open-issue.txt" || true ;;
  "issue comment") log "COMMENT #${args[2]}" ;;
  "issue create")
    log "CREATE"
    for ((i=0;i<${#args[@]};i++)); do
      if [ "${args[i]}" = "--body" ]; then printf '%s\n' "${args[i+1]}" > "$FIX/body.txt"; fi
    done ;;
esac
"""


def _script() -> str:
    doc = load_workflow(WORKFLOW)
    return str(step_by_id(jobs(doc)["guard"]["steps"], "guard")["run"])


def _fixture(
    tmp_path: Path,
    commits: dict[str, dict],
    *,
    compare: list[str] | None = None,
    lag: int = 1,
    open_issue: int | None = None,
) -> Path:
    fix = tmp_path / "fix"
    fix.mkdir()
    (fix / "calls.log").write_text("")
    (fix / "lag.txt").write_text(str(lag))
    if compare is not None:
        (fix / "compare.txt").write_text("\n".join(compare) + "\n")
    if open_issue is not None:
        (fix / "open-issue.txt").write_text(f"{open_issue}\n")
    for sha, c in commits.items():
        (fix / f"commit-{sha}.json").write_text(
            json.dumps(
                {
                    "author": {"login": c["author"]},
                    "commit": {"message": c["message"], "author": {"name": "n"}},
                }
            )
        )
        (fix / f"pulls-{sha}.json").write_text(json.dumps(c.get("pulls", [])))
    return fix


def _run(
    tmp_path: Path, fix: Path, **env: str
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)
    base = {
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "FIX": str(fix),
        "GH_TOKEN": "x",
        "REPO": "o/r",
        "BEFORE": "b" * 40,
        "AFTER": "a" * 40,
        "REF_NAME": "main",
        "DEFAULT_BRANCH": "main",
        "BRANCH_INPUT": "",
        "LABEL": "main-guard",
        "IGNORE_AUTHORS": "",
        "SERVER_URL": "https://github.com",
        "RUN_ID": "1",
        "RETRIES": "3",
        "RETRY_SLEEP": "0",
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
    }
    base.update(env)
    proc = subprocess.run(
        [shutil.which("bash") or "bash", "-c", _script()],
        env=base,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc, (fix / "calls.log").read_text().splitlines()


MERGED = [{"merged_at": "2026-01-01T00:00:00Z", "base": {"ref": "main"}}]
OPEN_PR = [{"merged_at": None, "base": {"ref": "main"}}]
OTHER_BASE = [{"merged_at": "2026-01-01T00:00:00Z", "base": {"ref": "dev"}}]


def test_workflow_is_reusable_least_privilege_and_lint_clean() -> None:
    doc = load_workflow(WORKFLOW)
    assert "workflow_call" in on_block(doc)
    assert doc["permissions"] == {"contents": "read"}
    assert jobs(doc)["guard"]["permissions"] == {
        "contents": "read",
        "issues": "write",
        "pull-requests": "read",
    }
    inputs = on_block(doc)["workflow_call"]["inputs"]
    assert set(inputs) == {"branch", "label", "ignore-authors", "runner"}


def test_alert_only_never_mutates_git() -> None:
    script = _script()
    for verb in ("git push", "git revert", "git reset", "--force"):
        assert verb not in script.replace('gh label create "$LABEL" --force', "")


@pytest.mark.skipif(
    shutil.which("actionlint") is None, reason="actionlint not installed"
)
def test_actionlint_clean() -> None:
    subprocess.run(["actionlint", str(WORKFLOW)], check=True)


def test_all_commits_via_merged_pr_is_silent(tmp_path: Path) -> None:
    fix = _fixture(
        tmp_path,
        {"c1": {"author": "al", "message": "feat: x", "pulls": MERGED}},
        compare=["c1"],
    )
    proc, calls = _run(tmp_path, fix)
    assert proc.returncode == 0, proc.stderr
    assert not [c for c in calls if c.startswith(("CREATE", "COMMENT"))]


def test_direct_push_opens_one_issue_naming_the_commit(tmp_path: Path) -> None:
    fix = _fixture(
        tmp_path,
        {
            "c1": {"author": "al", "message": "feat: via pr", "pulls": MERGED},
            "c2": {"author": "bob", "message": "oops direct push\n\nbody"},
        },
        compare=["c1", "c2"],
    )
    proc, calls = _run(tmp_path, fix)
    assert proc.returncode == 0, proc.stderr
    assert calls.count("CREATE") == 1
    body = (fix / "body.txt").read_text()
    assert "c2" in body
    assert "oops direct push" in body
    assert "@bob" in body
    assert "c1" not in body
    assert "label create main-guard" in calls


def test_open_issue_gets_a_comment_instead_of_a_duplicate(tmp_path: Path) -> None:
    fix = _fixture(
        tmp_path,
        {"c2": {"author": "bob", "message": "direct"}},
        compare=["c2"],
        open_issue=7,
    )
    proc, calls = _run(tmp_path, fix)
    assert proc.returncode == 0, proc.stderr
    assert "COMMENT #7" in calls
    assert "CREATE" not in calls


@pytest.mark.parametrize(
    "pulls", [OPEN_PR, OTHER_BASE], ids=["unmerged-pr", "other-base"]
)
def test_unmerged_or_other_base_pr_does_not_count(tmp_path: Path, pulls: list) -> None:
    fix = _fixture(
        tmp_path,
        {"c1": {"author": "al", "message": "m", "pulls": pulls}},
        compare=["c1"],
    )
    _, calls = _run(tmp_path, fix)
    assert "CREATE" in calls


def test_lagging_pulls_index_is_retried(tmp_path: Path) -> None:
    fix = _fixture(
        tmp_path,
        {"c1": {"author": "al", "message": "m", "pulls": MERGED}},
        compare=["c1"],
        lag=3,
    )
    proc, calls = _run(tmp_path, fix, RETRIES="4")
    assert proc.returncode == 0, proc.stderr
    assert "CREATE" not in calls
    assert calls.count("pulls c1") == 3


def test_ignored_author_is_not_flagged(tmp_path: Path) -> None:
    fix = _fixture(
        tmp_path,
        {"c1": {"author": "release-bot", "message": "chore: release"}},
        compare=["c1"],
    )
    _, calls = _run(tmp_path, fix, IGNORE_AUTHORS="x, release-bot")
    assert "CREATE" not in calls


def test_new_branch_or_unreachable_range_checks_head_only(tmp_path: Path) -> None:
    a = "a" * 40
    fix = _fixture(tmp_path, {a: {"author": "bob", "message": "direct"}})
    # no compare.txt -> the compare call fails (force-push): fall back to head
    _, calls = _run(tmp_path, fix)
    assert "CREATE" in calls
    zero_fix = tmp_path / "z"
    zero_fix.mkdir()
    fix2 = _fixture(zero_fix, {a: {"author": "bob", "message": "direct"}})
    _, calls2 = _run(zero_fix, fix2, BEFORE=ZERO)
    assert "CREATE" in calls2


def test_push_to_other_branch_is_ignored(tmp_path: Path) -> None:
    fix = _fixture(tmp_path, {"c1": {"author": "bob", "message": "m"}}, compare=["c1"])
    proc, calls = _run(tmp_path, fix, REF_NAME="feature/x")
    assert proc.returncode == 0
    assert calls == []


def test_explicit_branch_input_overrides_default(tmp_path: Path) -> None:
    fix = _fixture(tmp_path, {"c1": {"author": "bob", "message": "m"}}, compare=["c1"])
    _, calls = _run(tmp_path, fix, REF_NAME="trunk", BRANCH_INPUT="trunk")
    assert "CREATE" in calls
