"""Replay both scaffold approval gates with the real host retry helper."""

import json
import os
import subprocess

import pytest

from tests.workflow_replay import Replay
from tests.workflow_scaffold import WORKFLOWS, WORKSPACE, load_workflow

PLAN_LIMIT = (
    "Upgrade to GitHub Pro or make this repository public to enable this feature."
)


def review(number, login="reviewer", state="APPROVED", commit="head"):
    return {
        "id": number,
        "user": {"login": login},
        "state": state,
        "commit_id": commit,
        "submitted_at": f"2026-11-03T09:00:{number:02d}Z",
    }


def replay_gate(
    tmp_path,
    job,
    *,
    status=403,
    knob="0",
    approvals=0,
    required=2,
    errors=None,
    reviews=None,
    decision=None,
):
    gh = tmp_path / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\nimport os,sys,json\nfrom pathlib import Path\na=sys.argv[1:]\n"
        "if any('rules/branches' in x for x in a):\n"
        " p=Path(os.environ['CALLS']); n=len(p.read_text().splitlines()) if p.exists() else 0\n"
        " with p.open('a') as f: f.write('call\\n')\n"
        " errors=json.loads(os.environ['ERRORS']); status,message=errors[min(n,len(errors)-1)]\n"
        " if status != 200:\n"
        "  print(f'gh: {message} (HTTP {status})',file=sys.stderr); sys.exit(1)\n"
        " print(json.dumps([{'type':'pull_request','parameters':{'required_approving_review_count':int(os.environ['REQUIRED'])}}]))\n"
        "elif a[:2]==['pr','list']: print(os.environ['PRS'])\n"
        'elif a[:2]==[\'pr\',\'view\']: print(\'{"mergeable":"MERGEABLE","mergeStateStatus":"CLEAN"}\')\n'
        "else: print(os.environ['REVIEWS'])\n"
    )
    gh.chmod(0o755)
    # Exercise the shipped host helper, with only backoff sleeping stubbed.
    action = load_workflow(
        WORKSPACE / ".github/actions/setup-devkit-toolchain/action.yml"
    )
    setup = next(
        s
        for s in action["runs"]["steps"]
        if s.get("name") == "Install retry shell helper (host modes)"
    )
    retry = tmp_path / "retry-env.sh"
    retry.write_text(setup["run"].split("<<'RETRY_EOF'\n")[1].split("\nRETRY_EOF")[0])
    sleep = tmp_path / "sleep"
    sleep.write_text("#!/usr/bin/env bash\nexit 0\n")
    sleep.chmod(0o755)
    pr = {
        "number": 42,
        "isDraft": False,
        "headRefOid": "head",
        "author": {"login": "author"},
        "reviewDecision": decision,
        "statusCheckRollup": [{"name": "CI", "conclusion": "SUCCESS"}],
    }
    replay = Replay(
        WORKFLOWS / "promote-release.yml",
        job,
        {
            "github": {"repository": "example/repo"},
            "steps": {
                "vars": {"outputs": {"version": "1.2.3"}},
                "release_app_token": {"outputs": {"token": "fake"}},
            },
            "needs": {
                "validate": {"outputs": {"version": "1.2.3"}},
                "resolve-toolchain": {"outputs": {"release-required-approvals": knob}},
            },
        },
        cwd=WORKSPACE,
        base_env={
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "BASH_ENV": str(retry),
            "ERRORS": json.dumps(errors or [(status, PLAN_LIMIT)]),
            "REQUIRED": str(required),
            "CALLS": str(tmp_path / "calls"),
            "PRS": json.dumps([pr]),
            "REVIEWS": json.dumps(
                [
                    reviews
                    if reviews is not None
                    else [review(n + 1, f"reviewer{n}") for n in range(approvals)]
                ]
            ),
        },
    )
    replay.job = {"steps": replay.steps}  # Exclude scheduling/container fields.
    try:
        records = replay.run(only=["Find and verify release PR"])
        passed, output = True, records[0]["stdout"] + records[0]["stderr"]
    except subprocess.CalledProcessError as error:
        passed, output = False, error.stdout + error.stderr
    return passed, output, len((tmp_path / "calls").read_text().splitlines())


@pytest.mark.parametrize("job", ["validate", "merge"])
@pytest.mark.parametrize(
    ("status", "knob", "approvals", "required", "ok", "calls"),
    [
        (403, "", 1, 1, True, 1),
        (403, "", 0, 1, False, 1),
        (403, "0", 0, 0, True, 1),
        (403, "2", 1, 2, False, 1),
        (403, "2", 2, 2, True, 1),
        (200, "0", 0, 1, False, 1),
        (200, "0", 1, 1, True, 1),
        (200, "2", 0, 0, True, 1),
        (500, "0", 1, 1, False, 3),
    ],
)
def test_rules_gate(tmp_path, job, status, knob, approvals, required, ok, calls):
    passed, output, actual_calls = replay_gate(
        tmp_path,
        job,
        status=status,
        knob=knob,
        approvals=approvals,
        required=required,
        decision="APPROVED" if approvals else None,
    )
    assert passed == ok, output
    assert actual_calls == calls
    if status == 403:
        assert (
            f"GitHub plan limit: rulesets unavailable; requiring {required} approving review(s)"
            in output
        )


@pytest.mark.parametrize("job", ["validate", "merge"])
@pytest.mark.parametrize(
    ("status", "message"),
    [
        (403, "API rate limit exceeded"),
        (403, "You have exceeded a secondary rate limit"),
        (403, "Resource not accessible by integration"),
        (403, "Resource protected by organization SAML enforcement"),
        (401, PLAN_LIMIT),  # Kills a broadened HTTP 4 match even with the plan text.
        (404, PLAN_LIMIT),
    ],
)
def test_only_plan_limit_403_can_skip_rules(tmp_path, job, status, message):
    passed, output, calls = replay_gate(tmp_path, job, errors=[(status, message)])
    assert not passed, output
    assert calls == 3
    assert "GitHub plan limit:" not in output


@pytest.mark.parametrize("job", ["validate", "merge"])
@pytest.mark.parametrize("status", [200, 403])
@pytest.mark.parametrize(
    ("reviews", "knob", "ok"),
    [
        ([review(1), review(2)], "2", False),
        ([review(1), review(2, state="CHANGES_REQUESTED")], "1", False),
        ([review(1), review(2, state="DISMISSED")], "1", False),
        ([review(1, commit="old")], "1", False),
        ([review(1, login="author")], "1", False),
        ([review(2, state="CHANGES_REQUESTED"), review(1)], "1", False),
        ([review(1, login="a"), review(2, login="b")], "2", True),
    ],
)
def test_current_distinct_approvals(tmp_path, job, status, reviews, knob, ok):
    passed, output, _ = replay_gate(
        tmp_path, job, status=status, knob=knob, required=int(knob), reviews=reviews
    )
    assert passed == ok, output


@pytest.mark.parametrize("job", ["validate", "merge"])
def test_host_retry_preserves_plan_limit_body(tmp_path, job):
    passed, output, calls = replay_gate(
        tmp_path, job, errors=[(500, "Server error"), (403, PLAN_LIMIT)]
    )
    assert passed, output
    assert calls == 2
    assert (
        "GitHub plan limit: rulesets unavailable; requiring 0 approving review(s)"
        in output
    )
