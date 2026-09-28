"""Draft-Release-first ordering in the scaffold's release-publish.yml (#1746).

The train is the **Release owner**: it creates the GitHub Release as a draft
and only ``promote-release.yml`` ever publishes it. Between the tag push and
promote lies the *pre-publish assets window*, in which consumer workflows
(e.g. a ``push: tags:`` binaries build, cargo-dist used as an asset builder)
upload into the draft with ``gh release upload --clobber``.

For that window to be reliable the draft must exist **before** the tag ref: a
tag-triggered workflow that starts first would otherwise find no Release to
upload into. A draft Release does not create its tag (GitHub materialises the
tag only when the draft is published), so the draft is created against the
finalize SHA (``--target``) and the tag ref is POSTed afterwards.

Invariants pinned here, by EXECUTING the steps' real bash against a stateful
``gh``/``git`` fake:

- the draft step runs before the tag step and targets the finalize SHA
- a failed tag-ref POST discards the draft this run created (no orphan draft)
- a pre-existing draft whose tag already exists is never discarded
- re-running the step sequence after success is idempotent

Refs: #1746
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import WORKFLOWS, load_workflow

if TYPE_CHECKING:
    from pathlib import Path

PUBLISH = WORKFLOWS / "release-publish.yml"
SHA = "a" * 40
OTHER_SHA = "b" * 40
TAG = "v1.2.3"

# A stateful fake of the gh/git surface the publish steps touch. State lives in
# files under $FAKE_STATE: `release` (JSON: isDraft/isPrerelease) and `tag`
# (the SHA the remote tag ref points at). Every invocation is logged.
FAKE_GH = r"""#!/usr/bin/env bash
state="$FAKE_STATE"
echo "gh $*" >> "$state/log"
case "$1 $2" in
  "release view")
    [ -f "$state/release" ] || { echo "release not found" >&2; exit 1; }
    cat "$state/release"; exit 0 ;;
  "release create")
    [ -z "${FAKE_CREATE_FAIL:-}" ] || { echo "HTTP 500" >&2; exit 1; }
    pre=false
    for a in "$@"; do [ "$a" = "--prerelease" ] && pre=true; done
    printf '{"isDraft":true,"isPrerelease":%s}\n' "$pre" > "$state/release"
    exit 0 ;;
  "release delete")
    rm -f "$state/release"; exit 0 ;;
  "api -X")
    if [ -n "${FAKE_TAG_FAIL:-}" ]; then echo "HTTP 422: $FAKE_TAG_FAIL" >&2; exit 1; fi
    for a in "$@"; do case "$a" in sha=*) echo "${a#sha=}" > "$state/tag" ;; esac; done
    exit 0 ;;
esac
echo "unexpected gh call: $*" >&2
exit 2
"""

FAKE_GIT = r"""#!/usr/bin/env bash
state="$FAKE_STATE"
echo "git $*" >> "$state/log"
if [ "$1" = "ls-remote" ]; then
  for a in "$@"; do last="$a"; done
  if [ -f "$state/tag" ]; then
    case "$last" in *'^{}') exit 0 ;; esac
    printf '%s\t%s\n' "$(cat "$state/tag")" "$last"
  fi
  exit 0
fi
echo "unexpected git call: $*" >&2
exit 2
"""

# `retry --retries N ... -- cmd` => run cmd once (no backoff sleeps in tests).
FAKE_RETRY = r"""#!/usr/bin/env bash
while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do shift; done
shift
exec "$@"
"""


def _steps() -> list[dict]:
    (job,) = load_workflow(PUBLISH)["jobs"].values()
    return job["steps"]


def _step(step_id: str) -> dict:
    matches = [s for s in _steps() if s.get("id") == step_id]
    assert len(matches) == 1, f"expected exactly one step with id {step_id!r}"
    return matches[0]


@dataclass
class Fake:
    root: Path

    @property
    def state(self) -> Path:
        return self.root / "state"

    def release(self) -> dict | None:
        path = self.state / "release"
        return json.loads(path.read_text()) if path.exists() else None

    def tag(self) -> str | None:
        path = self.state / "tag"
        return path.read_text().strip() if path.exists() else None

    def log(self) -> str:
        path = self.state / "log"
        return path.read_text() if path.exists() else ""

    def run(
        self, step_id: str, *, extra_env: dict[str, str] | None = None
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
        step = _step(step_id)
        out = self.root / f"out-{step_id}"
        out.write_text("", encoding="utf-8")
        env = {
            **os.environ,
            "PATH": f"{self.root / 'bin'}{os.pathsep}{os.environ['PATH']}",
            "FAKE_STATE": str(self.state),
            "GITHUB_OUTPUT": str(out),
            "GITHUB_REPOSITORY": "acme/widget",
            "GITHUB_SERVER_URL": "https://github.com",
            "GH_TOKEN": "t",
            "PUBLISH_VERSION": "1.2.3",
            "VERSION": "1.2.3",
            "TAG_PREFIX": "v",
            "FINALIZE_SHA": SHA,
            "RELEASE_KIND": "final",
            **{k: v for k, v in (step.get("env") or {}).items() if "${{" not in str(v)},
            **(extra_env or {}),
        }
        notes = self.root / "release-notes.md"
        notes.write_text("notes\n", encoding="utf-8")
        script = step["run"].replace("/tmp/release-notes.md", str(notes))
        proc = subprocess.run(
            ["bash", "-c", script],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        outputs = dict(
            line.split("=", 1)
            for line in out.read_text(encoding="utf-8").splitlines()
            if "=" in line
        )
        return proc, outputs


@pytest.fixture
def fake(tmp_path: Path) -> Fake:
    (tmp_path / "state").mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("gh", FAKE_GH), ("git", FAKE_GIT), ("retry", FAKE_RETRY)):
        path = bin_dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
    return Fake(tmp_path)


# ── shape: ordering + targeting ───────────────────────────────────────────────


def test_draft_step_precedes_tag_step() -> None:
    ids = [s.get("id") for s in _steps()]
    assert "draft" in ids and "tag" in ids
    assert ids.index("draft") < ids.index("tag"), (
        "the draft Release must exist before the tag ref is pushed (#1746)"
    )


def test_release_notes_extracted_before_draft() -> None:
    names = [s.get("name", "") for s in _steps()]
    notes = names.index("Extract release notes from CHANGELOG")
    assert notes < [s.get("id") for s in _steps()].index("draft")


def test_draft_targets_finalize_sha_without_verify_tag() -> None:
    run = _step("draft")["run"]
    assert '--target "$FINALIZE_SHA"' in run
    # --verify-tag would demand the tag BEFORE the draft — the old ordering.
    assert "--verify-tag" not in run
    assert _step("draft")["env"]["FINALIZE_SHA"] == "${{ inputs.finalize_sha }}"


def test_orphan_cleanup_runs_only_on_tag_failure() -> None:
    step = _step("discard_orphan_draft")
    assert "failure()" in step["if"]
    assert "steps.tag.outcome == 'failure'" in step["if"]


# ── executed ──────────────────────────────────────────────────────────────────


def test_happy_path_creates_draft_then_tag(fake: Fake) -> None:
    proc, outputs = fake.run("draft")
    assert proc.returncode == 0, proc.stderr
    assert outputs["created"] == "true"
    assert fake.release() == {"isDraft": True, "isPrerelease": False}
    assert fake.tag() is None, "a draft must not create its tag"

    proc, _ = fake.run("tag")
    assert proc.returncode == 0, proc.stderr
    assert fake.tag() == SHA

    log = fake.log()
    assert log.index("gh release create") < log.index("gh api -X POST")
    assert f"--target {SHA}" in log


def test_candidate_draft_is_prerelease(fake: Fake) -> None:
    proc, _ = fake.run("draft", extra_env={"RELEASE_KIND": "candidate"})
    assert proc.returncode == 0, proc.stderr
    assert fake.release() == {"isDraft": True, "isPrerelease": True}


def test_rerun_with_existing_draft_is_idempotent(fake: Fake) -> None:
    """Retry path: the draft (and tag) from a previous attempt are reused."""
    fake.run("draft")
    fake.run("tag")
    creates = fake.log().count("gh release create")

    proc, outputs = fake.run("draft")
    assert proc.returncode == 0, proc.stderr
    assert outputs["created"] == "false"
    assert fake.log().count("gh release create") == creates
    assert fake.release() == {"isDraft": True, "isPrerelease": False}


def test_published_release_for_tag_is_refused(fake: Fake) -> None:
    (fake.state / "release").write_text('{"isDraft":false,"isPrerelease":false}')
    proc, _ = fake.run("draft")
    assert proc.returncode != 0
    assert "Published (non-draft) GitHub Release already exists" in proc.stdout


def test_failed_tag_post_discards_the_draft_this_run_created(fake: Fake) -> None:
    proc, outputs = fake.run("draft")
    assert proc.returncode == 0, proc.stderr

    proc, _ = fake.run("tag", extra_env={"FAKE_TAG_FAIL": "Reference update failed"})
    assert proc.returncode != 0

    proc, _ = fake.run(
        "discard_orphan_draft", extra_env={"DRAFT_CREATED": outputs["created"]}
    )
    assert proc.returncode == 0, proc.stderr
    assert fake.release() is None, "orphan draft left behind after tag failure"
    assert "--cleanup-tag" not in fake.log()


def test_tombstoned_tag_discards_the_draft(fake: Fake) -> None:
    proc, outputs = fake.run("draft")
    proc, _ = fake.run(
        "tag", extra_env={"FAKE_TAG_FAIL": "GH013 creations being restricted"}
    )
    assert proc.returncode != 0
    assert "tombstoned" in proc.stdout
    fake.run("discard_orphan_draft", extra_env={"DRAFT_CREATED": outputs["created"]})
    assert fake.release() is None


def test_preexisting_draft_with_live_tag_is_kept(fake: Fake) -> None:
    """A draft this run did not create, whose tag exists, is not ours to drop."""
    (fake.state / "release").write_text('{"isDraft":true,"isPrerelease":false}')
    (fake.state / "tag").write_text(OTHER_SHA)
    proc, _ = fake.run("discard_orphan_draft", extra_env={"DRAFT_CREATED": "false"})
    assert proc.returncode == 0, proc.stderr
    assert fake.release() is not None


def test_preexisting_tagless_draft_is_discarded(fake: Fake) -> None:
    """A draft with no tag behind it is an orphan whoever created it."""
    (fake.state / "release").write_text('{"isDraft":true,"isPrerelease":false}')
    proc, _ = fake.run("discard_orphan_draft", extra_env={"DRAFT_CREATED": "false"})
    assert proc.returncode == 0, proc.stderr
    assert fake.release() is None


def test_cleanup_never_deletes_a_published_release(fake: Fake) -> None:
    (fake.state / "release").write_text('{"isDraft":false,"isPrerelease":false}')
    proc, _ = fake.run("discard_orphan_draft", extra_env={"DRAFT_CREATED": "true"})
    assert proc.returncode == 0, proc.stderr
    assert fake.release() is not None
    assert "gh release delete" not in fake.log()
