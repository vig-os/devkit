"""Replay both scaffold approval gates against plan-limited rules APIs."""

import json
import os
import subprocess

import pytest

from tests.workflow_replay import Replay
from tests.workflow_scaffold import WORKFLOWS, WORKSPACE


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
        (500, "0", 1, 1, False, 3),
    ],
)
def test_rules_gate(tmp_path, job, status, knob, approvals, required, ok, calls):
    gh = tmp_path / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\nimport os,sys,json\na=sys.argv[1:]\n"
        "if any('rules/branches' in x for x in a):\n"
        " with open(os.environ['CALLS'], 'a') as f: f.write('call\\n')\n"
        " if os.environ['STATUS'] != '200':\n"
        "  print('gh: plan limit (HTTP '+os.environ['STATUS']+')',file=sys.stderr); sys.exit(1)\n"
        " print(json.dumps([{'type':'pull_request','parameters':{'required_approving_review_count':1}}]))\n"
        "elif a[:2]==['pr','list']: print(os.environ['PRS'])\n"
        'elif a[:2]==[\'pr\',\'view\']: print(\'{"mergeable":"MERGEABLE","mergeStateStatus":"CLEAN"}\')\n'
        "else: print(json.dumps([[{'state':'APPROVED'}]*int(os.environ['APPROVALS'])]))\n"
    )
    gh.chmod(0o755)
    retry = tmp_path / "retry"
    retry.write_text(
        '#!/usr/bin/env bash\nwhile [ "$1" != -- ]; do shift; done\nshift\n'
        'for attempt in 1 2 3; do if "$@"; then exit 0; fi; done\nexit 1\n'
    )
    retry.chmod(0o755)
    pr = {
        "number": 42,
        "isDraft": False,
        "reviewDecision": None,
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
                "resolve-toolchain": {"outputs": {"release-required-approvals": knob}}
            },
        },
        cwd=WORKSPACE,
        base_env={
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "STATUS": str(status),
            "CALLS": str(tmp_path / "calls"),
            "PRS": json.dumps([pr]),
            "APPROVALS": str(approvals),
        },
    )
    # Scheduling/container fields are outside the replay boundary.
    replay.job = {"steps": replay.steps}
    try:
        records = replay.run(only=["Find and verify release PR"])
        passed, output = True, records[0]["stdout"]
    except subprocess.CalledProcessError as error:
        passed, output = False, error.stdout + error.stderr
    assert passed == ok, output
    assert len((tmp_path / "calls").read_text().splitlines()) == calls
    if status == 403:
        assert (
            f"GitHub plan limit: rulesets unavailable; requiring {required} approving review(s)"
            in output
        )
