"""Execute the shared recovery gate with isolated GitHub API responses."""

import json
import os
import subprocess

import pytest

from tests.workflow_scaffold import REPO_ROOT, load_workflow, step_by_name, steps_of_job


@pytest.mark.parametrize(
    ("state", "decision", "reviews", "merge_on_main", "tag_on_main", "count", "ok"),
    [
        ("OPEN", "APPROVED", [], True, True, 1, True),
        ("MERGED", "APPROVED", [], True, True, 1, True),
        (
            "MERGED",
            None,
            [{"state": "APPROVED", "commit_id": "head"}],
            True,
            True,
            1,
            True,
        ),
        (
            "MERGED",
            None,
            [{"state": "APPROVED", "commit_id": "old"}],
            True,
            True,
            1,
            False,
        ),
        ("MERGED", "CHANGES_REQUESTED", [], True, True, 1, False),
        ("CLOSED", "APPROVED", [], True, True, 1, False),
        ("MERGED", "APPROVED", [], True, True, 0, False),
        ("MERGED", "APPROVED", [], True, True, 2, False),
        ("MERGED", "APPROVED", [], True, False, 1, False),
        ("MERGED", "APPROVED", [], False, True, 1, False),
    ],
)
def test_recovery_gate(
    tmp_path, state, decision, reviews, merge_on_main, tag_on_main, count, ok
):
    pr = {
        "number": 42,
        "state": state,
        "reviewDecision": decision,
        "headRefOid": "head",
        "mergeCommit": {"oid": "merge"},
        "mergedBy": {"login": "reviewer"},
        "mergedAt": "2026-11-03T09:06:00Z",
    }
    gh = tmp_path / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\nimport os,sys,json\n"
        "a=sys.argv[1:]\n"
        "if a[0]=='api' and any('reviews' in arg for arg in a): print('[' + os.environ['REVIEWS'] + ']')\n"
        "elif a[0]=='api': print(os.environ['MERGE_ON_MAIN'] if '/merge...' in a[1] else os.environ['TAG_ON_MAIN'])\n"
        "else: print(os.environ['PRS'] if '--state' in a and (a[a.index('--state')+1]=='all' or os.environ['STATE']=='OPEN') else '[]')\n"
    )
    gh.chmod(0o755)
    env = dict(
        os.environ,
        PATH=f"{tmp_path}:{os.environ['PATH']}",
        VERSION="1.2.3",
        GITHUB_REPOSITORY="example/repo",
        GITHUB_OUTPUT=str(tmp_path / "output"),
        STATE=state,
        PRS=json.dumps([pr] * count),
        REVIEWS=json.dumps(reviews),
        MERGE_ON_MAIN="ahead" if merge_on_main else "diverged",
        TAG_ON_MAIN="identical" if tag_on_main else "behind",
    )
    result = subprocess.run(
        ["bash", "-c", "source .github/scripts/find-release-pr.sh"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) == ok, result.stdout + result.stderr
    if not ok:
        assert "ERROR:" in result.stdout
    if ok and state == "MERGED":
        assert "already merged by reviewer at" in result.stdout
        assert "already_merged=true" in (tmp_path / "output").read_text()


def test_both_jobs_use_recovery_and_skip_duplicate_merge():
    workflow = load_workflow(REPO_ROOT / ".github/workflows/promote-release.yml")
    for job in ("validate", "merge"):
        step = step_by_name(steps_of_job(workflow, job), "Find and verify release PR")
        assert "source .github/scripts/find-release-pr.sh" in step["run"]
    merge = step_by_name(steps_of_job(workflow, "merge"), "Merge release PR")
    assert "steps.pr.outputs.already_merged != 'true'" in merge["if"]
