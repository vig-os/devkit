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
fake of the GitHub API (a release list + the tag ref), and by EVALUATING the
cleanup step's ``if:`` expression:

- the draft step runs before the tag step and targets the finalize SHA
- a create whose response was lost is adopted, never duplicated
- a failed tag-ref POST discards every draft this run created (no orphans)
- a pre-existing draft whose tag already exists is never discarded, and a
  published Release is never deleted
- a draft published between creation and the tag POST is not a failure
- re-running the step sequence after success is idempotent

Refs: #1746
"""

from __future__ import annotations

import json
import os
import re
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

# A stateful fake of the gh surface the publish steps touch. State lives under
# $FAKE_STATE: `releases.json` (the repo's release list, drafts included, as
# GET /releases returns it) and `tag` (the SHA the remote tag ref points at).
# Every invocation is logged. `gh api --jq` is served by real jq, so the
# steps' filters run for real.
FAKE_GH = r"""#!/usr/bin/env bash
state="$FAKE_STATE"
rel="$state/releases.json"
[ -f "$rel" ] || echo '[]' > "$rel"
echo "gh $*" >> "$state/log"
if [ "$1" = "release" ] && [ "$2" = "create" ]; then
  tag="$3"; shift 3
  target=""; pre=false
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --target) target="$2"; shift ;;
      --prerelease) pre=true ;;
      --verify-tag) [ -f "$state/tag" ] || { echo "tag not found" >&2; exit 1; } ;;
    esac
    shift
  done
  [ -z "${FAKE_CREATE_FAIL:-}" ] || { echo "$FAKE_CREATE_FAIL" >&2; exit 1; }
  id=$(( $(jq 'map(.id) | max // 0' "$rel") + 1 ))
  jq --arg t "$tag" --arg c "$target" --argjson p "$pre" --argjson id "$id" \
    '. + [{id: $id, tag_name: $t, draft: true, prerelease: $p, target_commitish: $c}]' \
    "$rel" > "$rel.new" && mv "$rel.new" "$rel"
  # Lost response: the server created the draft, the client saw an error.
  if [ -n "${FAKE_CREATE_LOSE_RESPONSE:-}" ] && [ ! -f "$state/lost" ]; then
    touch "$state/lost"; echo "HTTP 502: Bad Gateway" >&2; exit 1
  fi
  echo "https://github.com/acme/widget/releases/tag/untagged-$id"; exit 0
fi
if [ "$1" = "api" ]; then
  shift
  method=GET; jqf=""; path=""; sha=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      -X) method="$2"; shift ;;
      --jq) jqf="$2"; shift ;;
      --paginate) ;;
      -f) case "$2" in sha=*) sha="${2#sha=}" ;; esac; shift ;;
      *) path="$1" ;;
    esac
    shift
  done
  case "$method $path" in
    "GET repos/acme/widget/releases")
      jq -c "${jqf:-.}" "$rel"; exit 0 ;;
    "DELETE repos/acme/widget/releases/"*)
      id="${path##*/}"
      jq --argjson id "$id" 'map(select(.id != $id))' "$rel" > "$rel.new" && mv "$rel.new" "$rel"
      exit 0 ;;
    "POST repos/acme/widget/git/refs")
      [ -z "${FAKE_TAG_FAIL:-}" ] || { echo "HTTP 422: $FAKE_TAG_FAIL" >&2; exit 1; }
      [ ! -f "$state/tag" ] || { echo "gh: Reference already exists (HTTP 422)" >&2; exit 1; }
      echo "$sha" > "$state/tag"; exit 0 ;;
  esac
fi
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

# `retry --retries N ... -- cmd`: up to N attempts, no backoff sleeps.
FAKE_RETRY = r"""#!/usr/bin/env bash
n=1
while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do
  [ "$1" = "--retries" ] && n="$2"
  shift
done
shift
for _ in $(seq 1 "$n"); do "$@" && exit 0; done
exit 1
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

    def releases(self) -> list[dict]:
        path = self.state / "releases.json"
        return json.loads(path.read_text()) if path.exists() else []

    def drafts(self) -> list[dict]:
        return [r for r in self.releases() if r["draft"]]

    def seed(self, *, draft: bool, target: str = SHA, prerelease: bool = False) -> None:
        releases = self.releases()
        releases.append(
            {
                "id": len(releases) + 100,
                "tag_name": TAG,
                "draft": draft,
                "prerelease": prerelease,
                "target_commitish": target,
            }
        )
        (self.state / "releases.json").write_text(json.dumps(releases))

    def publish_all(self) -> None:
        """What publishing a draft does on GitHub: the tag materialises."""
        releases = self.releases()
        for r in releases:
            r["draft"] = False
            (self.state / "tag").write_text(r["target_commitish"])
        (self.state / "releases.json").write_text(json.dumps(releases))

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

    def cleanup_after(self, draft_created: str) -> subprocess.CompletedProcess[str]:
        proc, _ = self.run(
            "discard_orphan_draft", extra_env={"DRAFT_CREATED": draft_created}
        )
        return proc


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


# ── the cleanup step's `if:`, evaluated ───────────────────────────────────────


def _evaluate_if(expr: str, *, failure: bool, outcomes: dict[str, str]) -> bool:
    """Evaluate the GitHub-expression subset the cleanup ``if:`` uses.

    Supports ``failure()``, ``steps.<id>.outcome``, string literals, ``==``,
    ``!=``, ``&&``, ``||``, ``!`` and parentheses — enough to execute the
    condition instead of pattern-matching its text.
    """
    body = expr.strip()
    body = re.sub(r"^\$\{\{\s*|\s*\}\}$", "", body)
    body = body.replace("failure()", repr(failure))

    def outcome(m: re.Match[str]) -> str:
        return repr(outcomes.get(m.group(1), "skipped"))

    body = re.sub(r"steps\.(\w+)\.outcome", outcome, body)
    body = body.replace("&&", " and ").replace("||", " or ")
    body = re.sub(r"!(?!=)", " not ", body)
    assert re.fullmatch(r"[\sA-Za-z_'()=!]*", body), f"unsupported expression: {expr}"
    return bool(eval(body, {"__builtins__": {}}, {}))  # noqa: S307


CLEANUP_CASES = [
    # (failure(), draft outcome, tag outcome, expected)
    pytest.param(True, "success", "failure", True, id="tag-failed-after-draft"),
    pytest.param(False, "success", "success", False, id="happy-path"),
    pytest.param(True, "skipped", "failure", False, id="tag-only-candidate"),
    pytest.param(False, "success", "skipped", False, id="tag-already-existed"),
    pytest.param(True, "failure", "skipped", False, id="draft-step-failed"),
]


@pytest.mark.parametrize(("failed", "draft", "tag", "expected"), CLEANUP_CASES)
def test_cleanup_if_condition(
    failed: bool, draft: str, tag: str, expected: bool
) -> None:
    expr = _step("discard_orphan_draft")["if"]
    got = _evaluate_if(expr, failure=failed, outcomes={"draft": draft, "tag": tag})
    assert got is expected


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


# ── executed: draft creation ──────────────────────────────────────────────────


def test_happy_path_creates_draft_then_tag(fake: Fake) -> None:
    proc, outputs = fake.run("draft")
    assert proc.returncode == 0, proc.stderr
    assert outputs["created"] == "true"
    (draft,) = fake.drafts()
    assert draft["target_commitish"] == SHA
    assert draft["prerelease"] is False
    assert fake.tag() is None, "a draft must not create its tag"

    proc, _ = fake.run("tag")
    assert proc.returncode == 0, proc.stderr
    assert fake.tag() == SHA

    log = fake.log()
    assert log.index("gh release create") < log.index("gh api -X POST")


def test_candidate_draft_is_prerelease(fake: Fake) -> None:
    proc, _ = fake.run("draft", extra_env={"RELEASE_KIND": "candidate"})
    assert proc.returncode == 0, proc.stderr
    (draft,) = fake.drafts()
    assert draft["prerelease"] is True


def test_rerun_with_existing_draft_is_idempotent(fake: Fake) -> None:
    """Retry path: the draft (and tag) from a previous attempt are reused."""
    fake.run("draft")
    fake.run("tag")
    proc, outputs = fake.run("draft")
    assert proc.returncode == 0, proc.stderr
    assert outputs["created"] == "false"
    assert len(fake.releases()) == 1
    assert fake.log().count("gh release create") == 1


def test_lost_create_response_is_adopted_not_duplicated(fake: Fake) -> None:
    """The server created the draft but the client saw an error: no second draft."""
    proc, outputs = fake.run("draft", extra_env={"FAKE_CREATE_LOSE_RESPONSE": "1"})
    assert proc.returncode == 0, proc.stderr
    assert outputs["created"] == "true"
    assert len(fake.drafts()) == 1, fake.releases()


def test_published_release_for_tag_is_refused(fake: Fake) -> None:
    fake.seed(draft=False)
    proc, _ = fake.run("draft")
    assert proc.returncode != 0
    assert "Published (non-draft) GitHub Release already exists" in proc.stdout


def test_published_prerelease_is_the_candidate_retry_path(fake: Fake) -> None:
    fake.seed(draft=False, prerelease=True)
    proc, outputs = fake.run("draft", extra_env={"RELEASE_KIND": "candidate"})
    assert proc.returncode == 0, proc.stderr
    assert outputs["created"] == "false"


def test_tombstoned_release_create_is_diagnosed(fake: Fake) -> None:
    proc, _ = fake.run(
        "draft", extra_env={"FAKE_CREATE_FAIL": "GH013 creations restricted"}
    )
    assert proc.returncode != 0
    assert "tombstoned" in proc.stdout


# ── executed: orphan cleanup ──────────────────────────────────────────────────


def test_failed_tag_post_discards_the_draft_this_run_created(fake: Fake) -> None:
    proc, outputs = fake.run("draft")
    assert proc.returncode == 0, proc.stderr
    proc, _ = fake.run("tag", extra_env={"FAKE_TAG_FAIL": "Reference update failed"})
    assert proc.returncode != 0
    proc = fake.cleanup_after(outputs["created"])
    assert proc.returncode == 0, proc.stderr
    assert fake.releases() == [], "orphan draft left behind after tag failure"


def test_cleanup_removes_every_draft_of_a_lost_response_run(fake: Fake) -> None:
    """Belt and braces: even duplicated drafts for this tag+target all go."""
    fake.seed(draft=True)
    fake.seed(draft=True)
    proc = fake.cleanup_after("true")
    assert proc.returncode == 0, proc.stderr
    assert fake.drafts() == []


def test_tag_on_another_sha_discards_this_runs_draft(fake: Fake) -> None:
    (fake.state / "tag").write_text(OTHER_SHA)
    proc, outputs = fake.run("draft")
    assert outputs["created"] == "true"
    proc, _ = fake.run("tag")
    assert proc.returncode != 0
    assert "mismatch" in proc.stdout
    proc = fake.cleanup_after(outputs["created"])
    assert proc.returncode == 0, proc.stderr
    assert fake.drafts() == []
    assert fake.tag() == OTHER_SHA, "cleanup must never touch the tag ref"


def test_draft_published_before_tag_post_is_not_a_failure(fake: Fake) -> None:
    """Publishing the draft materialises the tag at the finalize SHA first."""
    proc, _ = fake.run("draft")
    fake.publish_all()
    proc, _ = fake.run("tag")
    assert proc.returncode == 0, proc.stderr
    assert "already present" in proc.stdout
    expr = _step("discard_orphan_draft")["if"]
    assert not _evaluate_if(
        expr, failure=False, outcomes={"draft": "success", "tag": "success"}
    )


def test_cleanup_never_deletes_a_published_release(fake: Fake) -> None:
    """Even if cleanup runs after the draft was published, it stays."""
    fake.run("draft")
    fake.publish_all()
    proc = fake.cleanup_after("true")
    assert proc.returncode == 0, proc.stderr
    assert len(fake.releases()) == 1
    assert "-X DELETE" not in fake.log()


def test_tombstoned_tag_discards_the_draft(fake: Fake) -> None:
    proc, outputs = fake.run("draft")
    proc, _ = fake.run(
        "tag", extra_env={"FAKE_TAG_FAIL": "GH013 creations being restricted"}
    )
    assert proc.returncode != 0
    assert "tombstoned" in proc.stdout
    fake.cleanup_after(outputs["created"])
    assert fake.drafts() == []


def test_preexisting_draft_with_live_tag_is_kept(fake: Fake) -> None:
    """A draft this run did not create, whose tag exists, is not ours to drop."""
    fake.seed(draft=True)
    (fake.state / "tag").write_text(OTHER_SHA)
    proc = fake.cleanup_after("false")
    assert proc.returncode == 0, proc.stderr
    assert len(fake.drafts()) == 1


def test_preexisting_tagless_draft_is_discarded(fake: Fake) -> None:
    """A draft for this target with no tag behind it is an orphan either way."""
    fake.seed(draft=True)
    proc = fake.cleanup_after("false")
    assert proc.returncode == 0, proc.stderr
    assert fake.drafts() == []


def test_draft_for_another_target_is_never_touched(fake: Fake) -> None:
    fake.seed(draft=True, target=OTHER_SHA)
    proc = fake.cleanup_after("true")
    assert proc.returncode == 0, proc.stderr
    assert len(fake.drafts()) == 1
