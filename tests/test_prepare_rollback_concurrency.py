"""Replay prepare rollback with the exact SHA written by the freeze action."""

import base64
import os

import pytest

from tests.github_expression import render_input
from tests.test_commit_action_base_sha import ROOT, replay_for


def test_freeze_output_survives_branch_creation_failure(tmp_path):
    replay = replay_for(
        ROOT / ".github/workflows/prepare-release.yml", "prepare", tmp_path
    )
    freeze = next(
        s
        for s in replay.steps
        if s.get("name") == "Commit prepared CHANGELOG to dev via API"
    )
    assert freeze.get("id")
    output = replay.workflow["jobs"]["prepare"]["outputs"]["freeze_sha"]
    assert (
        render_input(
            output, {"steps": {freeze["id"]: {"outputs": {"commit-sha": "freeze"}}}}
        )
        == "freeze"
    )


def install_api_stubs(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text("""#!/usr/bin/env python3
import os, sys
args = ' '.join(sys.argv[1:])
with open(os.environ['GH_LOG'], 'a') as log:
    log.write(args + '\\n')
if 'contents/CHANGELOG.md' in args:
    print(os.environ['PRE_CONTENT'] if '?ref=checkout' in args else os.environ['CURRENT_CONTENT'])
elif 'git/ref/heads/dev' in args:
    print(os.environ['CURRENT_SHA'])
elif 'git/ref/heads/release/' in args:
    sys.exit(1)
else:
    sys.exit(2)
""")
    uv = bin_dir / "uv"
    uv.write_text(
        '#!/usr/bin/env bash\nwhile [[ "$1" != "--" ]]; do shift; done\nshift\nexec "$@"\n'
    )
    gh.chmod(0o755)
    uv.chmod(0o755)
    return bin_dir


@pytest.mark.parametrize(
    "freeze,current,restore,message",
    [
        ("", "concurrent", False, "freeze SHA is empty"),
        ("freeze", "freeze", True, "Prepared CHANGELOG rollback"),
        ("freeze", "concurrent", False, "dev advanced after freeze"),
    ],
)
def test_prepare_rollback_only_restores_its_own_freeze(
    tmp_path, freeze, current, restore, message
):
    bin_dir = install_api_stubs(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("current entries")
    replay = replay_for(
        ROOT / ".github/workflows/prepare-release.yml", "rollback", tmp_path
    )
    replay.context = {
        "github": {"repository": "example/project"},
        "needs": {
            "prepare": {
                "outputs": {"prepare_start_sha": "checkout", "freeze_sha": freeze}
            },
            "validate": {
                "outputs": {"version": "1.2.3", "release_branch": "release/1.2.3"}
            },
        },
        "steps": {"commit-app-token": {"outputs": {"token": "test-token"}}},
    }
    replay.base_env.update(
        {
            "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            "GH_LOG": str(tmp_path / "gh.log"),
            "CURRENT_SHA": current,
            "PRE_CONTENT": base64.b64encode(b"original entries").decode(),
            "CURRENT_CONTENT": base64.b64encode(b"current entries").decode(),
        }
    )
    step = next(s for s in replay.steps if s.get("id") == "rollback-prepare")
    # Isolate the workflow's existing scratch files for parallel replay.
    step["run"] = step["run"].replace("/tmp/changelog.", str(tmp_path / "changelog."))
    result = replay.run(only=["rollback-prepare"])[0]
    assert message in result["stdout"]
    assert result["outputs"]["changelog_rollback_needed"] == str(restore).lower()
    assert changelog.read_text() == (
        "original entries" if restore else "current entries"
    )
    calls = (tmp_path / "gh.log").read_text()
    assert ("contents/CHANGELOG.md" in calls) == restore
