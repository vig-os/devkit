"""The standalone publish seam: ``publish-release-extension.yml`` (#1746).

The third consumer-owned release seam, alongside ``release-extension.yml``
(read-only, pre-tag) and ``prepare-release-extension.yml`` (mutating,
pre-PR). It hosts **irreversible outward publishes** — crates.io, PyPI,
container registries, nix caches — and therefore fires only on
``release: published``, i.e. after ``promote-release.yml`` flips the draft.

It is a standalone workflow, NOT ``workflow_call``: crates.io and PyPI Trusted
Publishing bind the OIDC subject to the concrete workflow file path, so a
reusable-workflow indirection would change the subject for every consumer.
Retry is a native ``workflow_dispatch`` with the tag.

Pinned here:

- shape: triggers, standalone, preserved seed, deny-by-default token (the
  ``id-token: write`` / ``environment:`` opt-ins ship as comments)
- the resolve step's real bash, executed for BOTH triggers against a fake
  ``gh``: a promote-triggered ``release: published`` event and a
  ``workflow_dispatch`` retry reach the same state, and a retry on a draft or
  a missing Release is refused
- promote publishes the draft under the Release App token — a
  ``GITHUB_TOKEN``-driven publish would never fire ``release: published``
  (the tessera#438 trap), so the seam would silently never run
- the scaffold ships it, preserves a consumer's copy on upgrade, and drops it
  with the ``release`` feature group

Refs: #1746
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import TYPE_CHECKING

import pytest

from scripts.sync_manifest import load_preserve_files
from tests.workflow_scaffold import (
    INIT_WORKSPACE,
    WORKFLOWS,
    cached_tree,
    load_workflow,
    on_block,
    scaffold,
)

if TYPE_CHECKING:
    from pathlib import Path

REL = ".github/workflows/publish-release-extension.yml"
SEAM = WORKFLOWS / "publish-release-extension.yml"
PROMOTE = WORKFLOWS / "promote-release.yml"


def _doc() -> dict:
    return load_workflow(SEAM)


# ── shape ─────────────────────────────────────────────────────────────────────


def test_seam_triggers_on_release_published_and_dispatch_retry() -> None:
    on = on_block(_doc())
    assert on["release"] == {"types": ["published"]}
    tag = on["workflow_dispatch"]["inputs"]["tag"]
    assert tag["required"] is True
    assert tag["type"] == "string"


def test_seam_is_standalone_not_reusable() -> None:
    """Trusted Publishing binds the OIDC subject to THIS file's path."""
    assert "workflow_call" not in on_block(_doc())


def test_seam_is_a_preserved_consumer_seed() -> None:
    assert REL in load_preserve_files(INIT_WORKSPACE)


def test_seam_is_in_the_release_feature_group() -> None:
    text = INIT_WORKSPACE.read_text(encoding="utf-8")
    group = re.search(r"        release\)\n(.*?);;", text, re.DOTALL)
    assert group is not None
    assert f'"{REL}"' in group.group(1)


def test_seam_default_is_deny_by_default() -> None:
    doc = _doc()
    assert doc["permissions"] == {"contents": "read"}
    for name, job in doc["jobs"].items():
        perms = job.get("permissions") or {}
        assert set(perms) <= {"contents"}, f"job {name} requests {perms}"
        assert perms.get("contents", "read") == "read"
        assert "environment" not in job, f"job {name} binds an environment"


def test_seam_ships_trusted_publishing_and_environment_opt_ins_as_comments() -> None:
    text = SEAM.read_text(encoding="utf-8")
    assert re.search(r"^\s*#\s*id-token: write", text, re.MULTILINE)
    assert re.search(r"^\s*#\s*environment:", text, re.MULTILINE)


def test_publish_job_consumes_the_resolved_payload() -> None:
    jobs = _doc()["jobs"]
    resolve = jobs["resolve"]
    assert set(resolve["outputs"]) >= {"tag", "prerelease"}
    publish = jobs["publish"]
    assert publish["needs"] == "resolve" or publish["needs"] == ["resolve"]


# ── executed: the resolve step for both triggers ──────────────────────────────

FAKE_GH = r"""#!/usr/bin/env bash
echo "gh $*" >> "$FAKE_LOG"
if [ "$1 $2" = "release view" ]; then
  [ -n "${FAKE_RELEASE_JSON:-}" ] || { echo "release not found" >&2; exit 1; }
  printf '%s\n' "$FAKE_RELEASE_JSON"; exit 0
fi
echo "unexpected gh call: $*" >&2; exit 2
"""

PUBLISHED = '{"tagName":"v1.2.3","isDraft":false,"isPrerelease":false}'
PUBLISHED_PRE = '{"tagName":"v1.2.3-alpha.1","isDraft":false,"isPrerelease":true}'
DRAFT = '{"tagName":"v1.2.3","isDraft":true,"isPrerelease":false}'


def _resolve(
    tmp_path: Path,
    *,
    event: str,
    event_tag: str = "",
    input_tag: str = "",
    release_json: str | None = PUBLISHED,
) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH, encoding="utf-8")
    gh.chmod(0o755)
    out = tmp_path / f"out-{event}"
    out.write_text("", encoding="utf-8")
    (step,) = [
        s for s in _doc()["jobs"]["resolve"]["steps"] if s.get("id") == "release"
    ]
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_LOG": str(tmp_path / "gh.log"),
        "GITHUB_OUTPUT": str(out),
        "GH_TOKEN": "t",
        "GH_REPO": "acme/widget",
        "EVENT_NAME": event,
        "EVENT_TAG": event_tag,
        "INPUT_TAG": input_tag,
        "FAKE_RELEASE_JSON": release_json or "",
    }
    proc = subprocess.run(
        ["bash", "-c", step["run"]],
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


def test_resolve_step_env_maps_both_payloads() -> None:
    (step,) = [
        s for s in _doc()["jobs"]["resolve"]["steps"] if s.get("id") == "release"
    ]
    env = step["env"]
    assert env["EVENT_TAG"] == "${{ github.event.release.tag_name }}"
    assert env["INPUT_TAG"] == "${{ inputs.tag }}"
    assert env["EVENT_NAME"] == "${{ github.event_name }}"


def test_promote_triggered_event_resolves_the_release(tmp_path: Path) -> None:
    proc, outputs = _resolve(tmp_path, event="release", event_tag="v1.2.3")
    assert proc.returncode == 0, proc.stderr
    assert outputs == {"tag": "v1.2.3", "prerelease": "false"}


def test_dispatch_retry_reaches_the_same_state(tmp_path: Path) -> None:
    _, from_event = _resolve(tmp_path, event="release", event_tag="v1.2.3")
    proc, from_retry = _resolve(tmp_path, event="workflow_dispatch", input_tag="v1.2.3")
    assert proc.returncode == 0, proc.stderr
    assert from_retry == from_event


def test_prerelease_flag_is_surfaced(tmp_path: Path) -> None:
    proc, outputs = _resolve(
        tmp_path,
        event="release",
        event_tag="v1.2.3-alpha.1",
        release_json=PUBLISHED_PRE,
    )
    assert proc.returncode == 0, proc.stderr
    assert outputs["prerelease"] == "true"


def test_dispatch_on_a_draft_is_refused(tmp_path: Path) -> None:
    """The point of no return is promote: never publish from a draft."""
    proc, outputs = _resolve(
        tmp_path, event="workflow_dispatch", input_tag="v1.2.3", release_json=DRAFT
    )
    assert proc.returncode != 0
    assert "draft" in (proc.stdout + proc.stderr).lower()
    assert "tag" not in outputs


def test_dispatch_on_a_missing_release_is_refused(tmp_path: Path) -> None:
    proc, _ = _resolve(
        tmp_path, event="workflow_dispatch", input_tag="v9.9.9", release_json=None
    )
    assert proc.returncode != 0


@pytest.mark.parametrize("tag", ["", "   "])
def test_dispatch_without_a_tag_is_refused(tmp_path: Path, tag: str) -> None:
    proc, _ = _resolve(tmp_path, event="workflow_dispatch", input_tag=tag)
    assert proc.returncode != 0


# ── the promote -> release: published hand-off ────────────────────────────────


def test_promote_publishes_under_the_release_app_token() -> None:
    """``release: published`` only fires for a non-GITHUB_TOKEN actor.

    Events caused by ``GITHUB_TOKEN`` never start other workflows, so if
    promote flipped the draft with it the publish seam would silently never
    run (tessera#438).
    """
    jobs = load_workflow(PROMOTE)["jobs"]
    publishing = [
        step
        for job in jobs.values()
        for step in job.get("steps") or []
        if "--draft=false" in str(step.get("run", ""))
    ]
    assert publishing, "promote-release.yml no longer publishes the draft"
    for step in publishing:
        assert step["env"]["GH_TOKEN"] == "${{ steps.release_app_token.outputs.token }}"


# ── scaffold ──────────────────────────────────────────────────────────────────


def test_scaffold_ships_the_seed() -> None:
    shipped = cached_tree() / REL
    assert shipped.is_file()
    assert "Seeded by vigOS devkit" in shipped.read_text(encoding="utf-8")


def test_upgrade_preserves_a_consumer_implementation(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    (seed / ".github" / "workflows").mkdir(parents=True)
    custom = "name: Publish Release Extension\n# consumer implementation\n"
    (seed / REL).write_text(custom, encoding="utf-8")
    proc = scaffold(tmp_path, seed=seed, name="upgraded")
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "upgraded" / REL).read_text(encoding="utf-8") == custom


def test_release_feature_opt_out_does_not_ship_the_seed(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / ".vig-os").write_text(
        "DEVKIT_FEATURES_DISABLED=release\n", encoding="utf-8"
    )
    proc = scaffold(tmp_path, seed=seed, name="no-release")
    assert proc.returncode == 0, proc.stderr
    assert not (tmp_path / "no-release" / REL).exists()
