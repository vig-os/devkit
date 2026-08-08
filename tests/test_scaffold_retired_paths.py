"""Retired-scaffold-path pruning on ``--force`` upgrades (#1348).

``install.sh --force`` regenerates the paths the *current* scaffold manages and
prunes what the current mode / workflow model / feature set excludes — but a
path that an OLD devkit shipped and a later devkit RETIRED is managed by
neither, so it survived every upgrade. Observed going 0.3.4 -> 1.6.0
(exo-pet/playground-carlos#9): ``.cursor/``, ``.github/actions/resolve-image/``,
``.github/workflows/renovate-changelog.yml`` and ``.hadolint.yaml`` all rode
along. The workflow file is the sharp one — it coexists with the
``renovate-changelog-build``/``-commit`` pair that replaced it and references a
pruned action, so it breaks at its next trigger rather than at upgrade time.

The fix is a cumulative retired-paths manifest (version -> paths retired in it)
consulted against the consumer's PREVIOUS pin, which the upgrade reads from
``.vig-os`` before rewriting it. Version gating is the safety property: a repo
whose pin already post-dates the retirement never had the path shipped to it, so
an identically named file there is the consumer's own and must not be deleted.

Refs: #1348
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.workflow_scaffold import INIT_WORKSPACE, scaffold

if TYPE_CHECKING:
    from pathlib import Path

# Every path the manifest retires, with the version that retired it. Kept here
# as the test's own copy so a silent edit of the shell manifest fails loudly.
RETIRED = {
    ".github/workflows/renovate-changelog.yml": "0.3.5",
    ".cursor": "0.4.0",
    ".hadolint.yaml": "0.4.0",
    ".github/actions/resolve-image": "1.1.0",
}


def _seed(tmp_path: Path, pin: str | None, *, paths: tuple[str, ...]) -> Path:
    """Build a consumer tree pinned at ``pin`` carrying the given stale paths."""
    seed = tmp_path / "seed"
    seed.mkdir()
    if pin is not None:
        (seed / ".vig-os").write_text(f"DEVKIT_VERSION={pin}\n", encoding="utf-8")
    for rel in paths:
        target = seed / rel
        if rel.endswith((".yml", ".yaml")):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# stale scaffold leftover\n", encoding="utf-8")
        else:
            target.mkdir(parents=True, exist_ok=True)
            (target / "leftover.txt").write_text("stale\n", encoding="utf-8")
    return seed


def test_manifest_declares_every_known_retired_path() -> None:
    """The shell manifest carries each retired path with its retiring version."""
    init = INIT_WORKSPACE.read_text(encoding="utf-8")
    assert "retired_paths()" in init
    for rel, version in RETIRED.items():
        assert f"{version} {rel}" in init, f"missing manifest entry: {version} {rel}"


def test_upgrade_from_an_old_pin_prunes_retired_paths(tmp_path: Path) -> None:
    """A 0.3.4 consumer loses every path retired after its pin."""
    seed = _seed(tmp_path, "0.3.4", paths=tuple(RETIRED))
    proc = scaffold(tmp_path, seed=seed, name="old-pin")
    assert proc.returncode == 0, proc.stderr
    tree = tmp_path / "old-pin"
    for rel in RETIRED:
        assert not (tree / rel).exists(), f"{rel} survived the upgrade"
    # The prune announces itself — a silent deletion is not reviewable.
    assert "#1348" in proc.stdout


def test_legacy_devcontainer_version_pin_is_honored(tmp_path: Path) -> None:
    """The pre-#781 DEVCONTAINER_VERSION key gates the prune just the same.

    Repos still on the legacy key are exactly the oldest ones, i.e. those most
    likely to carry the leftovers, so reading only DEVKIT_VERSION would miss
    the whole population this fix targets.
    """
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / ".vig-os").write_text("DEVCONTAINER_VERSION=0.3.4\n", encoding="utf-8")
    (seed / ".hadolint.yaml").write_text("# stale\n", encoding="utf-8")
    proc = scaffold(tmp_path, seed=seed, name="legacy-pin")
    assert proc.returncode == 0, proc.stderr
    assert not (tmp_path / "legacy-pin" / ".hadolint.yaml").exists()


def test_pin_past_the_retirement_keeps_the_path(tmp_path: Path) -> None:
    """A current consumer's identically named files are the consumer's own.

    Version gating is what makes the prune safe: ``.cursor/`` and
    ``.hadolint.yaml`` are generic names a repo pinned past 0.4.0 may own
    outright, and deleting those would be data loss.
    """
    seed = _seed(tmp_path, "1.6.0", paths=(".cursor", ".hadolint.yaml"))
    proc = scaffold(tmp_path, seed=seed, name="new-pin")
    assert proc.returncode == 0, proc.stderr
    tree = tmp_path / "new-pin"
    assert (tree / ".cursor").is_dir()
    assert (tree / ".hadolint.yaml").is_file()


def test_unpinned_workspace_prunes_nothing(tmp_path: Path) -> None:
    """No pin (fresh install, or a manifest-less tree) means no evidence."""
    seed = _seed(tmp_path, None, paths=(".cursor",))
    proc = scaffold(tmp_path, seed=seed, name="no-pin")
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "no-pin" / ".cursor").is_dir()


def test_preview_reports_retired_paths_without_deleting(tmp_path: Path) -> None:
    """--preview lists the prune under DELETIONS and mutates nothing (#886)."""
    seed = _seed(tmp_path, "0.3.4", paths=(".hadolint.yaml",))
    proc = scaffold(tmp_path, seed=seed, name="preview", preview=True)
    assert proc.returncode == 0, proc.stderr
    assert "DELETED" in proc.stdout
    assert ".hadolint.yaml" in proc.stdout
    assert (tmp_path / "preview" / ".hadolint.yaml").is_file()
