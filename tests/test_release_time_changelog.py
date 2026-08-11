"""Workflow-shape contract: release-time bot changelog synthesis (Refs: #1423).

The per-PR Renovate changelog pipeline (build + privileged commit) is replaced
by ``synthesize-bot-changelog`` running at the two dispatch points that already
own changelog mutation: release cut (``prepare-release.yml``) and finalize
(``release.yml`` at the devkit root, ``release-core.yml`` in the scaffold).
These tests pin the wiring: pipeline gone, synthesis ordered before the
``prepare-changelog`` call it feeds, full-depth checkout for the tag window,
and PR-metadata read access for the enumeration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from tests.workflow_scaffold import REPO_ROOT, WORKFLOWS, load_workflow

ROOT_WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SYNTH = "synthesize-bot-changelog"


def _steps(workflow: Path, job: str) -> list[dict]:
    return load_workflow(workflow)["jobs"][job]["steps"]


def _job(workflow: Path, job: str) -> dict:
    return load_workflow(workflow)["jobs"][job]


def _step_index(steps: list[dict], fragment: str) -> int:
    for i, step in enumerate(steps):
        if fragment in str(step.get("run", "")):
            return i
    raise AssertionError(f"no step running {fragment!r}")


def _checkout_fetch_depth(steps: list[dict]) -> object:
    for step in steps:
        uses = str(step.get("uses", ""))
        if uses.startswith("actions/checkout@"):
            return (step.get("with") or {}).get("fetch-depth")
    raise AssertionError("no checkout step")


# ── the per-PR pipeline is gone ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        ROOT_WORKFLOWS / "renovate-changelog-build.yml",
        ROOT_WORKFLOWS / "renovate-changelog-commit.yml",
        WORKFLOWS / "renovate-changelog-build.yml",
        WORKFLOWS / "renovate-changelog-commit.yml",
    ],
    ids=lambda p: str(p.relative_to(REPO_ROOT)),
)
def test_per_pr_changelog_workflows_are_gone(path: Path) -> None:
    assert not path.exists(), (
        f"{path.name} should be replaced by release-time synthesis"
    )


def test_manifest_no_longer_syncs_the_commit_workflow() -> None:
    manifest = (REPO_ROOT / "scripts" / "manifest.toml").read_text(encoding="utf-8")
    assert "renovate-changelog" not in manifest


def test_renovate_feature_no_longer_lists_the_pair() -> None:
    init = (REPO_ROOT / "assets" / "init-workspace.sh").read_text(encoding="utf-8")
    renovate_block = init[init.index("renovate)") : init.index("sync-issues)")]
    assert "renovate-changelog-build.yml" not in renovate_block
    assert "renovate-changelog-commit.yml" not in renovate_block


@pytest.mark.parametrize(
    "path",
    [REPO_ROOT / "zizmor.yml", REPO_ROOT / "assets" / "workspace" / "zizmor.yml"],
    ids=("root", "scaffold"),
)
def test_zizmor_configs_carry_no_stale_pipeline_entries(path: Path) -> None:
    assert "renovate-changelog" not in path.read_text(encoding="utf-8")


# ── synthesis at cut: prepare-release.yml (root + scaffold) ───────────────────


@pytest.mark.parametrize(
    "workflow",
    [ROOT_WORKFLOWS / "prepare-release.yml", WORKFLOWS / "prepare-release.yml"],
    ids=("root", "scaffold"),
)
class TestSynthesisAtCut:
    def test_validate_synthesizes_before_validating_content(
        self, workflow: Path
    ) -> None:
        # A train whose only content is bot PRs must pass the non-empty gate.
        steps = _steps(workflow, "validate")
        assert _step_index(steps, SYNTH) < _step_index(
            steps, "prepare-changelog validate"
        )

    def test_prepare_synthesizes_before_freezing(self, workflow: Path) -> None:
        steps = _steps(workflow, "prepare")
        assert _step_index(steps, SYNTH) < _step_index(
            steps, "prepare-changelog prepare"
        )

    @pytest.mark.parametrize("job", ["validate", "prepare"])
    def test_jobs_fetch_full_history_for_the_tag_window(
        self, workflow: Path, job: str
    ) -> None:
        assert _checkout_fetch_depth(_steps(workflow, job)) == 0

    @pytest.mark.parametrize("job", ["validate", "prepare"])
    def test_jobs_may_read_pr_metadata(self, workflow: Path, job: str) -> None:
        permissions = _job(workflow, job).get("permissions") or {}
        assert permissions.get("pull-requests") == "read"

    @pytest.mark.parametrize("job", ["validate", "prepare"])
    def test_synthesis_step_authenticates_gh(self, workflow: Path, job: str) -> None:
        steps = _steps(workflow, job)
        env = steps[_step_index(steps, SYNTH)].get("env") or {}
        assert "GH_TOKEN" in env


# ── synthesis at finalize: release.yml (root) / release-core.yml (scaffold) ───


@pytest.mark.parametrize(
    ("workflow", "job"),
    [
        (ROOT_WORKFLOWS / "release.yml", "finalize"),
        (WORKFLOWS / "release-core.yml", "finalize"),
    ],
    ids=("root", "scaffold"),
)
class TestSynthesisAtFinalize:
    def test_finalize_synthesizes_into_the_version_section_first(
        self, workflow: Path, job: str
    ) -> None:
        steps = _steps(workflow, job)
        synth = _step_index(steps, SYNTH)
        assert synth < _step_index(steps, "prepare-changelog finalize")
        assert "--version" in str(steps[synth]["run"])

    def test_finalize_fetches_full_history_for_the_tag_window(
        self, workflow: Path, job: str
    ) -> None:
        assert _checkout_fetch_depth(_steps(workflow, job)) == 0

    def test_finalize_may_read_pr_metadata(self, workflow: Path, job: str) -> None:
        permissions = _job(workflow, job).get("permissions") or {}
        assert permissions.get("pull-requests") == "read"

    def test_synthesis_step_authenticates_gh(self, workflow: Path, job: str) -> None:
        steps = _steps(workflow, job)
        env = steps[_step_index(steps, SYNTH)].get("env") or {}
        assert "GH_TOKEN" in env

    def test_candidates_stay_changelog_neutral(self, workflow: Path, job: str) -> None:
        # Synthesis rides the finalize pass only; candidate dispatches must not
        # gain changelog mutation through this change.
        steps = _steps(workflow, job)
        step = steps[_step_index(steps, SYNTH)]
        assert "release_kind == 'final'" in str(step.get("if", "")).replace('"', "'")


# ── operator preview (read-only mid-cycle visibility) ─────────────────────────


@pytest.mark.parametrize(
    "justfile",
    [
        REPO_ROOT / "justfile.gh",
        REPO_ROOT / "assets" / "workspace" / ".devcontainer" / "justfile.gh",
    ],
    ids=("root", "scaffold"),
)
def test_changelog_preview_recipe_exists_and_is_dry(justfile: Path) -> None:
    text = justfile.read_text(encoding="utf-8")
    assert "changelog-preview" in text
    recipe = text[text.index("changelog-preview") :]
    assert "--dry-run" in recipe.split("\n\n")[0]
