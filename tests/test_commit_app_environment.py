"""Scaffold-render tests: the commit-App environment binding DEVKIT_COMMIT_APP_ENVIRONMENT.

Issue #1710: the stamped workflows read ``COMMIT_APP_CLIENT_ID`` /
``COMMIT_APP_PRIVATE_KEY`` from wherever GitHub resolves the names, in practice
organization or repository secrets — readable by a workflow job on ANY branch.
The commit App typically holds a branch-protection bypass, so any account with
write access can push a branch whose workflow mints the token and writes straight
past the default branch's protection.

``DEVKIT_COMMIT_APP_ENVIRONMENT`` closes that surface: set to the name of a
deployment environment whose secrets hold the pair, the scaffold renders
``environment: <name>`` on precisely the token-minting jobs, so a job on an
unadmitted ref cannot read the credentials at all. Unset (the default) renders
exactly today's bytes.

Two shapes are load-bearing and only a render test can pin them:

- the binding lands on the jobs that MINT the token and on no other job in the
  tree (a stray binding gates an unrelated job on a deployment policy);
- the name is rendered as a **quoted** YAML scalar. The allowed charset admits
  YAML 1.1 bool/number shapes (``true``, ``no``, ``0755``, ``1e3``), which an
  unquoted scalar parses as ``True`` / ``False`` / ``493`` / ``1000.0`` — and
  ``actionlint`` does not flag it, so the first failure would be GitHub rejecting
  the dispatch in a consumer's repo;
- ``release-core.yml`` is a ``workflow_call`` CALLEE, so the key goes on its
  ``finalize`` job (``on.workflow_call`` takes no ``environment``) and its two
  ``COMMIT_APP_*`` declarations must flip to ``required: false`` — with the pair
  living only as environment secrets, the caller's ``secrets: inherit`` cannot
  satisfy ``required: true``.

The list is not simply the template grep, either: mirror mode
(``DEVKIT_SYNC_TARGET``, #1424) *renders* a ninth token-minting job into
``promote-release.yml``, which a grep over ``assets/workspace/`` cannot see. Left
unbound it would be the one job still minting from org/repo secrets — i.e. broken
the moment a consumer moves the pair into the environment.

These drive the REAL ``init-workspace.sh`` end-to-end (the executed-bash style of
``tests/test_sync_settings.py``).

Refs: #1710
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import (
    INIT_WORKSPACE,
    WORKFLOWS,
    cached_tree,
    jobs,
    load_workflow,
    scaffold,
)

if TYPE_CHECKING:
    from pathlib import Path

ENV_NAME = "commit-app"

# (workflow, job) — every scaffolded job that mints the commit App token, i.e.
# `grep COMMIT_APP assets/workspace/.github/workflows/` reduced to the job that
# owns each `create-github-app-token` step. `release-core.yml`'s `finalize` is
# the workflow_call callee's job, NOT `release.yml`'s `core:` (uses:) job.
TOKEN_MINTING_JOBS = {
    ("sync-issues.yml", "sync"),
    ("prepare-release.yml", "prepare"),
    ("prepare-release.yml", "rollback"),
    ("prepare-hotfix.yml", "prepare"),
    ("prepare-hotfix.yml", "rollback"),
    ("release.yml", "rollback"),
    ("release-core.yml", "finalize"),
    ("sync-main-to-dev.yml", "sync"),
}

# The ninth pair exists only in a mirror-mode render: render_sync_settings appends
# a `reset-sync-mirror` job to promote-release.yml (#1424) that mints the same
# token. The default render has no such job.
MIRROR_MINTING_JOB = ("promote-release.yml", "reset-sync-mirror")
MIRROR = "sync/issue-mirror"

# The trunk model copy-excludes sync-main-to-dev.yml (no dev branch) and
# prepare-hotfix.yml (#1625: every trunk release already cuts from main), so
# their jobs are not in a trunk tree at all.
TRUNK_ABSENT_WORKFLOWS = {"sync-main-to-dev.yml", "prepare-hotfix.yml"}
TRUNK_MINTING_JOBS = {
    (wf, job) for wf, job in TOKEN_MINTING_JOBS if wf not in TRUNK_ABSENT_WORKFLOWS
}


def _seed(tmp_path: Path, name: str, manifest: str) -> Path:
    """Create a seed workspace holding a ``.vig-os`` with the given manifest text."""
    seed = tmp_path / f"{name}-seed"
    seed.mkdir()
    (seed / ".vig-os").write_text(manifest, encoding="utf-8")
    return seed


def _render(
    tmp_path: Path,
    *,
    name: str,
    environment: str | None = ENV_NAME,
    workflow: str | None = None,
    extra: str = "",
) -> Path:
    """Scaffold with the knob set (unless None) and return the workspace root."""
    manifest = extra
    if environment is not None:
        manifest += f"DEVKIT_COMMIT_APP_ENVIRONMENT={environment}\n"
    seed = _seed(tmp_path, name, manifest) if manifest else None
    proc = scaffold(tmp_path, workflow=workflow, seed=seed, name=name)
    assert proc.returncode == 0, proc.stderr
    return tmp_path / name


def _bound_jobs(tree: Path) -> set[tuple[str, str]]:
    """Every (workflow, job) in the rendered tree carrying an ``environment:`` key."""
    bound: set[tuple[str, str]] = set()
    for wf in sorted((tree / ".github" / "workflows").glob("*.yml")):
        for job_name, job in jobs(load_workflow(wf)).items():
            if isinstance(job, dict) and "environment" in job:
                bound.add((wf.name, job_name))
    return bound


def _environment_of(tree: Path, workflow: str, job: str) -> object:
    return jobs(load_workflow(tree / ".github" / "workflows" / workflow))[job][
        "environment"
    ]


def _environment_line(tree: Path, workflow: str, job: str) -> str:
    """The raw line the render inserted under ``  <job>:`` (as bytes on disk)."""
    lines = (
        (tree / ".github" / "workflows" / workflow)
        .read_text(encoding="utf-8")
        .splitlines()
    )
    idx = lines.index(f"  {job}:")
    return lines[idx + 1]


def _call_secrets(tree_or_template: Path) -> dict:
    """``on.workflow_call.secrets`` of a release-core.yml copy."""
    doc = load_workflow(tree_or_template)
    on = doc.get("on", doc.get(True))
    assert isinstance(on, dict)
    return on["workflow_call"]["secrets"]


# ── production wiring seams ───────────────────────────────────────────────────


def test_init_workspace_invokes_render_commit_app_environment() -> None:
    """init-workspace.sh defines + invokes render_commit_app_environment."""
    init = INIT_WORKSPACE.read_text(encoding="utf-8")
    assert init.count("render_commit_app_environment") >= 2


# ── unset = byte-for-byte today's behavior ────────────────────────────────────


@pytest.mark.parametrize("workflow", sorted({wf for wf, _ in TOKEN_MINTING_JOBS}))
def test_unset_leaves_every_touched_workflow_byte_identical(workflow: str) -> None:
    """No key => the rendered workflow is byte-identical to the template copy."""
    rendered = cached_tree(None) / ".github" / "workflows" / workflow
    assert rendered.read_bytes() == (WORKFLOWS / workflow).read_bytes()


def test_unset_binds_no_job_anywhere() -> None:
    """No key => not one job in the rendered tree carries an `environment:` key."""
    assert _bound_jobs(cached_tree(None)) == set()


def test_unset_keeps_release_core_secrets_required() -> None:
    """No key => release-core.yml still REQUIRES the inherited COMMIT_APP pair."""
    secrets = _call_secrets(
        cached_tree(None) / ".github" / "workflows" / "release-core.yml"
    )
    assert secrets["COMMIT_APP_CLIENT_ID"]["required"] is True
    assert secrets["COMMIT_APP_PRIVATE_KEY"]["required"] is True


# ── the binding, set ─────────────────────────────────────────────────────────


def test_set_binds_exactly_the_token_minting_jobs(tmp_path: Path) -> None:
    """The knob binds the token-minting jobs — and NO other job in the tree."""
    tree = _render(tmp_path, name="bound")
    assert _bound_jobs(tree) == TOKEN_MINTING_JOBS


@pytest.mark.parametrize(
    ("workflow", "job"),
    sorted(TOKEN_MINTING_JOBS),
    ids=[f"{wf}:{job}" for wf, job in sorted(TOKEN_MINTING_JOBS)],
)
def test_set_binds_the_named_environment(
    workflow: str, job: str, tmp_path: Path
) -> None:
    """Each bound job names the configured environment verbatim, quoted."""
    tree = _render(tmp_path, name=f"named-{workflow}-{job}")
    assert _environment_of(tree, workflow, job) == ENV_NAME
    assert _environment_line(tree, workflow, job) == f"    environment: '{ENV_NAME}'"


def test_set_leaves_the_caller_uses_job_unbound(tmp_path: Path) -> None:
    """`release.yml`'s `core:` job is a `uses:` caller — `environment` there is
    not what supplies the callee's secrets, and GitHub forbids it on a
    `uses:` job."""
    tree = _render(tmp_path, name="caller")
    core = jobs(load_workflow(tree / ".github" / "workflows" / "release.yml"))["core"]
    assert "environment" not in core
    assert "uses" in core


def test_set_flips_release_core_call_secrets_optional(tmp_path: Path) -> None:
    """The callee's COMMIT_APP pair becomes optional so `secrets: inherit` may
    resolve neither — the job-level environment supplies them instead."""
    tree = _render(tmp_path, name="optional")
    secrets = _call_secrets(tree / ".github" / "workflows" / "release-core.yml")
    assert secrets["COMMIT_APP_CLIENT_ID"]["required"] is False
    assert secrets["COMMIT_APP_PRIVATE_KEY"]["required"] is False
    # Only the commit pair moves: the release App still has to be inherited.
    assert secrets["RELEASE_APP_CLIENT_ID"]["required"] is True
    assert secrets["RELEASE_APP_PRIVATE_KEY"]["required"] is True


def test_set_is_idempotent_across_a_re_render(tmp_path: Path) -> None:
    """A second scaffold over the rendered tree does not stack a second key."""
    tree = _render(tmp_path, name="idem")
    first = (tree / ".github" / "workflows" / "sync-issues.yml").read_bytes()
    proc = scaffold(tmp_path, name="idem")
    assert proc.returncode == 0, proc.stderr
    assert (tree / ".github" / "workflows" / "sync-issues.yml").read_bytes() == first
    assert _bound_jobs(tree) == TOKEN_MINTING_JOBS


# ── trunk model ──────────────────────────────────────────────────────────────


def test_trunk_binds_only_the_workflows_it_ships(tmp_path: Path) -> None:
    """Under trunk the copy-excluded workflows are absent; the rest are bound."""
    tree = _render(tmp_path, name="trunk-bound", workflow="trunk")
    for absent in TRUNK_ABSENT_WORKFLOWS:
        assert not (tree / ".github" / "workflows" / absent).exists()
    assert _bound_jobs(tree) == TRUNK_MINTING_JOBS


# ── feature opt-out composition ──────────────────────────────────────────────


def test_release_opt_out_binds_only_the_workflows_it_ships(tmp_path: Path) -> None:
    """A release-less consumer has no release workflows to bind — no failure.

    The ``release`` feature group also drops ``sync-main-to-dev.yml`` (the dev
    bridge exists for the release train), so only the sync-issues job is left.
    """
    tree = _render(
        tmp_path, name="no-release", extra="DEVKIT_FEATURES_DISABLED=release\n"
    )
    assert _bound_jobs(tree) == {("sync-issues.yml", "sync")}


# ── the name is a quoted scalar, never a YAML 1.1 bool/number ────────────────


@pytest.mark.parametrize(
    "name",
    [
        "true",  # YAML 1.1 bool -> True
        "no",  # YAML 1.1 bool -> False
        "0755",  # octal int -> 493
        "1e3",  # float -> 1000.0
    ],
)
def test_yaml_typed_name_stays_a_string(tmp_path: Path, name: str) -> None:
    """A name shaped like a YAML bool/number is rendered quoted, so it stays text.

    ``[A-Za-z0-9._-]`` admits these, and an unquoted scalar makes the job's
    ``environment`` a bool/int — a shape GitHub rejects at dispatch and
    ``actionlint`` does not flag, so it would first surface in a consumer's repo.
    """
    tree = _render(tmp_path, name=f"typed-{name}", environment=name)
    value = _environment_of(tree, "sync-issues.yml", "sync")
    assert isinstance(value, str), f"{name!r} rendered as {type(value).__name__}"
    assert value == name
    assert _environment_line(tree, "sync-issues.yml", "sync") == (
        f"    environment: '{name}'"
    )


def test_every_bound_job_carries_a_quoted_name(tmp_path: Path) -> None:
    """The quoting is the render's shape, not a per-file accident."""
    tree = _render(tmp_path, name="quoted-all")
    for workflow, job in TOKEN_MINTING_JOBS:
        assert _environment_line(tree, workflow, job) == (
            f"    environment: '{ENV_NAME}'"
        )


# ── sync-mirror composition (#1424) ──────────────────────────────────────────


def test_mirror_mode_binds_the_rendered_reset_job(tmp_path: Path) -> None:
    """Mirror mode renders a ninth token-minting job; it is bound too.

    ``render_sync_settings`` appends ``reset-sync-mirror`` to
    ``promote-release.yml``, and it mints the commit App token like the eight
    template jobs. Unbound, it would be the only job left reading the pair from
    org/repo secrets — so it breaks the instant a consumer moves them into the
    environment, at promote time, after the release is already published.
    """
    tree = _render(tmp_path, name="mirror", extra=f"DEVKIT_SYNC_TARGET={MIRROR}\n")
    assert _bound_jobs(tree) == TOKEN_MINTING_JOBS | {MIRROR_MINTING_JOB}
    assert _environment_of(tree, *MIRROR_MINTING_JOB) == ENV_NAME


def test_default_render_ships_no_mirror_reset_job() -> None:
    """Without the mirror knob there is no such job to bind (hence no binding)."""
    promote = cached_tree(None) / ".github" / "workflows" / "promote-release.yml"
    assert MIRROR_MINTING_JOB[1] not in jobs(load_workflow(promote))


# ── guards (format validation, loud at scaffold time) ────────────────────────


@pytest.mark.parametrize(
    "hostile",
    [
        "prod/eu",  # a slash: not a ref-shaped name, and a sed delimiter hazard
        "prod eu",  # inner whitespace: unquoted YAML scalar, sed replacement
        "-prod",  # leading dash: a YAML sequence token
        "prod'eu",  # single quote
        'prod"eu',  # double quote
        "x$(id)y",  # command substitution
        "a`id`b",  # backtick command substitution
        "a;b",  # shell statement separator
        "a&b",  # sed replacement metacharacter
        "a|b",  # sed delimiter collision
        "a#b",  # YAML comment token
        "c{d}",  # expression/brace tokens
    ],
)
def test_guard_rejects_hostile_environment_name(tmp_path: Path, hostile: str) -> None:
    """A name that would break the render (or inject into it) is refused loudly.

    GitHub documents only "≤ 255 characters, case-insensitive, unique per
    repository" for environment names, so it accepts values that would render
    invalid YAML or mis-splice the render sed. The scaffold guard is therefore a
    strict allowlist, refused before any mutation.
    """
    seed = _seed(tmp_path, "hostile", f"DEVKIT_COMMIT_APP_ENVIRONMENT={hostile}\n")
    proc = scaffold(tmp_path, seed=seed, name="hostile", check=False)
    assert proc.returncode != 0, f"scaffold accepted hostile environment: {hostile!r}"
    assert "Invalid DEVKIT_COMMIT_APP_ENVIRONMENT" in proc.stderr


def test_guard_rejects_over_long_environment_name(tmp_path: Path) -> None:
    """GitHub caps an environment name at 255 characters."""
    seed = _seed(tmp_path, "too-long", f"DEVKIT_COMMIT_APP_ENVIRONMENT={'e' * 256}\n")
    proc = scaffold(tmp_path, seed=seed, name="too-long", check=False)
    assert proc.returncode != 0
    assert "Invalid DEVKIT_COMMIT_APP_ENVIRONMENT" in proc.stderr


@pytest.mark.parametrize("name", ["commit-app", "Commit_App.2", "production"])
def test_guard_accepts_reasonable_environment_names(tmp_path: Path, name: str) -> None:
    """The allowlist admits the names a consumer actually uses."""
    tree = _render(tmp_path, name=f"ok-{name}", environment=name)
    assert _environment_of(tree, "sync-issues.yml", "sync") == name


# ── manifest round-trip ──────────────────────────────────────────────────────


def test_environment_persisted_in_manifest(tmp_path: Path) -> None:
    """The value is written back to .vig-os (upgrade-persistent)."""
    tree = _render(tmp_path, name="persist")
    text = (tree / ".vig-os").read_text(encoding="utf-8")
    assert f"DEVKIT_COMMIT_APP_ENVIRONMENT={ENV_NAME}" in text


def test_unset_manifest_keeps_the_bare_template_line() -> None:
    """An unconfigured scaffold keeps the bare key (no value invented)."""
    text = (cached_tree(None) / ".vig-os").read_text(encoding="utf-8")
    assert "DEVKIT_COMMIT_APP_ENVIRONMENT=\n" in text
