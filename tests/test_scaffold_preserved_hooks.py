"""Reconciling a preserved ``.pre-commit-config.yaml`` on upgrade (#1654).

A preserved hook config (#878) keeps the consumer's ``exclude:`` patterns and,
by the same token, blocks every kind of template evolution. Two divergences
result, and neither self-heals:

**Case 1 — a retired block that breaks.** The pre-#1170 ``pymarkdown`` hook is
``language: python``, so ``prek`` builds its venv on its own base interpreter
while the flake toolchain's ``pymarkdownlnt`` targets
``default_language_version``. The C-extension import then fails and breaks
``just precommit``, markdown commits **and** the ``devkit-upgrade.yml`` commit
step — which runs in the project shell with the hooks live, so those repos never
reach a PR where #1652's warning could be read. The fold replaces the block, and
gates on a **byte-identical** match against the historical template text: that
is the only evidence that the bytes being overwritten are devkit's own output
and not the consumer's.

**Case 2 — a hook the consumer never received.** ``actionlint`` (#1660) reaches
new scaffolds only; existing repos lint their workflows with nothing. Absence is
ambiguous, so the insert mirrors ``retired_prune_paths()`` (#1348): insert only
when ``PREVIOUS_PIN`` predates the release that started shipping the hook — the
tree was generated before the hook existed, so its absence cannot be a decision.
A repo at or past that release has seen the hook and is left alone, which also
makes a hand-deletion durable (the #1651 defect). ``DEVKIT_FEATURES_DISABLED``
is the declarative opt-out and is honoured before anything is written.

Refs: #1654
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.workflow_scaffold import INIT_WORKSPACE, scaffold

if TYPE_CHECKING:
    import subprocess
    from pathlib import Path

# The `jackdewinter/pymarkdown` block byte-for-byte as the template shipped it
# from 0.3.0 through 1.3.x — the shape every realistically-pinned consumer
# received, and the only one the fold accepts.
RETIRED_PYMARKDOWN_BLOCK = r"""  - repo: https://github.com/jackdewinter/pymarkdown
    rev: f93643d339dfee2a1022e7b05e8b5a281bfac553  # v0.9.23
    hooks:
      - id: pymarkdown
        name: pymarkdown
        args: ["-c", ".pymarkdown", "fix"]
        exclude: ^(README\.md|CONTRIBUTE\.md|TESTING\.md)
"""

# The release that first ships the `actionlint` hook to consumers (#1660).
ACTIONLINT_SINCE = "1.16.0"

# A consumer config with the consumer's own global exclude, their own
# `shellcheck` exception, a hand-written comment, and the retired block.
_CONSUMER_HEAD = r"""# SENTINEL-1654 consumer hook config
exclude: ^docs/generated/

default_language_version:
  python: python3.14

repos:
  - repo: local
    hooks:
      - id: shellcheck
        name: shellcheck
        entry: shellcheck
        language: system
        types: [shell]
        args: ["-x"]
        exclude: (^|/)\.envrc$|^vendor/

  # Markdown Linting (excludes auto-generated docs)
"""

_CONSUMER_TAIL = r"""
  - repo: local
    hooks:
      - id: typos
        name: typos (source typo checker)
        entry: typos --force-exclude
        language: system
        stages: [pre-commit]
"""


def _seed(
    tmp_path: Path,
    *,
    block: str = RETIRED_PYMARKDOWN_BLOCK,
    manifest: str | None = None,
    name: str = "seed",
) -> Path:
    """A consumer tree whose preserved hook config carries ``block``."""
    seed = tmp_path / name
    seed.mkdir()
    (seed / ".pre-commit-config.yaml").write_text(
        _CONSUMER_HEAD + block + _CONSUMER_TAIL, encoding="utf-8"
    )
    if manifest is not None:
        (seed / ".vig-os").write_text(manifest, encoding="utf-8")
    return seed


def _upgrade(
    tmp_path: Path, seed: Path, *, name: str, preview: bool = False
) -> subprocess.CompletedProcess[str]:
    proc = scaffold(tmp_path, seed=seed, name=name, check=False, preview=preview)
    assert proc.returncode == 0, proc.stderr
    return proc


def _config(tmp_path: Path, name: str) -> str:
    return (tmp_path / name / ".pre-commit-config.yaml").read_text(encoding="utf-8")


def _hook_order(text: str) -> list[str]:
    """The hook ids of a config, in file order."""
    return [
        line.split("- id:", 1)[1].strip()
        for line in text.splitlines()
        if line.strip().startswith("- id:")
    ]


# ── the tables are the knowledge; pin them structurally ───────────────────────


def test_the_retired_block_table_carries_the_verbatim_historical_text() -> None:
    """The fold's evidence is the exact bytes, so the script must carry them.

    A silent edit of the heredoc (a re-indent, a "tidied" ``rev:``) would stop
    the fold matching the very repos it exists for, with no test failing.
    """
    init = INIT_WORKSPACE.read_text(encoding="utf-8")
    assert "retired_hook_blocks()" in init
    assert RETIRED_PYMARKDOWN_BLOCK in init


def test_the_insert_table_declares_the_release_that_first_ships_each_hook() -> None:
    """Case 2's version gate reads a ``<version> <hook> <feature>`` manifest."""
    init = INIT_WORKSPACE.read_text(encoding="utf-8")
    assert "inserted_hook_blocks()" in init
    assert f"{ACTIONLINT_SINCE} actionlint actionlint" in init


# ── Case 1: fold a retired block ──────────────────────────────────────────────


def test_a_byte_exact_retired_block_is_folded(tmp_path: Path) -> None:
    """The pre-#1170 block becomes the template's ``language: system`` hook."""
    proc = _upgrade(tmp_path, _seed(tmp_path), name="fold")
    text = _config(tmp_path, "fold")

    assert "jackdewinter" not in text
    assert "entry: pymarkdown" in text
    assert "language: system" in text
    assert "types: [markdown]" in text
    # The fold announces itself on the machine channel #1652 opened.
    assert "preserved-hook-fold: pymarkdown-pre-1170 in .pre-commit-config.yaml" in (
        proc.stdout
    )
    # ... and stops claiming the consumer must hand-fold what was just folded.
    assert "preserved-hook-drift:" not in proc.stdout


def test_the_fold_touches_nothing_but_the_retired_block(tmp_path: Path) -> None:
    """Their global exclude, their hook exceptions, their comments all survive."""
    _upgrade(tmp_path, _seed(tmp_path), name="surgical")
    text = _config(tmp_path, "surgical")

    assert "# SENTINEL-1654 consumer hook config" in text
    assert "exclude: ^docs/generated/" in text
    assert r"exclude: (^|/)\.envrc$|^vendor/" in text
    assert "# Markdown Linting (excludes auto-generated docs)" in text
    # Ordering is preserved: the replacement lands where the retired block was.
    assert _hook_order(text) == ["shellcheck", "pymarkdown", "typos"]


def test_a_customized_retired_block_is_never_rewritten(tmp_path: Path) -> None:
    """One edited byte and the fold declines — the #1652 warning stands.

    Observed in the field: a consumer added their own vendored-doc paths to the
    block's ``exclude:``. Folding it would have deleted that exception list, so
    "provably devkit's own output" has to mean every byte.
    """
    customized = RETIRED_PYMARKDOWN_BLOCK.replace(
        r"exclude: ^(README\.md|CONTRIBUTE\.md|TESTING\.md)",
        r"exclude: ^(README\.md|CONTRIBUTE\.md|TESTING\.md|docs/vendor/.*\.md)",
    )
    proc = _upgrade(tmp_path, _seed(tmp_path, block=customized), name="custom")
    text = _config(tmp_path, "custom")

    assert "jackdewinter" in text
    assert r"docs/vendor/.*\.md" in text
    assert "preserved-hook-fold:" not in proc.stdout
    assert "preserved-hook-drift: pymarkdown-pre-1170" in proc.stdout


def test_a_renovate_bumped_rev_falls_through_to_the_warning(tmp_path: Path) -> None:
    """Deliberate under-folding: no heuristic decides whose bytes those are."""
    bumped = RETIRED_PYMARKDOWN_BLOCK.replace(
        "rev: f93643d339dfee2a1022e7b05e8b5a281bfac553  # v0.9.23",
        "rev: 8f8c2f2b0a6b4b0d9d3f6a1a0c4e2d7b9e5a1c3d  # v0.9.29",
    )
    proc = _upgrade(tmp_path, _seed(tmp_path, block=bumped), name="bumped")

    assert "jackdewinter" in _config(tmp_path, "bumped")
    assert "preserved-hook-fold:" not in proc.stdout
    assert "preserved-hook-drift: pymarkdown-pre-1170" in proc.stdout


def test_the_fold_is_idempotent(tmp_path: Path) -> None:
    """A second upgrade finds nothing to fold and says nothing."""
    seed = _seed(tmp_path)
    _upgrade(tmp_path, seed, name="twice")
    first = _config(tmp_path, "twice")
    again = scaffold(tmp_path, name="twice", check=False)
    assert again.returncode == 0, again.stderr

    assert _config(tmp_path, "twice") == first
    assert "preserved-hook-fold:" not in again.stdout


def test_the_fold_marker_rides_stdout_and_the_prose_is_reviewable(
    tmp_path: Path,
) -> None:
    """``devkit-upgrade.yml`` greps the tee'd stdout, so the marker must be there."""
    proc = _upgrade(tmp_path, _seed(tmp_path), name="channel")

    assert "preserved-hook-fold:" in proc.stdout
    assert "preserved-hook-fold:" not in proc.stderr


# ── Case 2: insert a hook the consumer never received ─────────────────────────


def _insert_seed(tmp_path: Path, manifest: str, name: str = "seed") -> Path:
    """A consumer tree with no ``actionlint`` hook and no retired block."""
    seed = tmp_path / name
    seed.mkdir()
    (seed / ".pre-commit-config.yaml").write_text(
        _CONSUMER_HEAD.replace(
            "  # Markdown Linting (excludes auto-generated docs)\n", ""
        )
        + _CONSUMER_TAIL.lstrip("\n"),
        encoding="utf-8",
    )
    (seed / ".vig-os").write_text(manifest, encoding="utf-8")
    return seed


def test_a_pin_predating_the_release_receives_the_hook(tmp_path: Path) -> None:
    """The tree was generated before the hook existed: absence is not a choice."""
    seed = _insert_seed(tmp_path, "DEVKIT_VERSION=1.15.1\n")
    proc = _upgrade(tmp_path, seed, name="insert")
    text = _config(tmp_path, "insert")

    assert "- id: actionlint" in text
    assert "entry: actionlint" in text
    assert "preserved-hook-insert: actionlint in .pre-commit-config.yaml" in proc.stdout


def test_the_hook_lands_at_its_template_position(tmp_path: Path) -> None:
    """After its template neighbour, never appended — hook order is observable."""
    seed = _insert_seed(tmp_path, "DEVKIT_VERSION=1.15.1\n")
    _upgrade(tmp_path, seed, name="position")

    assert _hook_order(_config(tmp_path, "position")) == [
        "shellcheck",
        "actionlint",
        "typos",
    ]


def test_the_inserted_block_keeps_its_opt_out_sentinels(tmp_path: Path) -> None:
    """Without them a later ``DEVKIT_FEATURES_DISABLED=actionlint`` cannot excise.

    ``render_actionlint_optout`` (#1660) deletes the sentinel range; a block
    inserted without sentinels would silently outlive the opt-out.
    """
    seed = _insert_seed(tmp_path, "DEVKIT_VERSION=1.15.1\n")
    _upgrade(tmp_path, seed, name="sentinels")
    text = _config(tmp_path, "sentinels")

    assert "# >>> devkit:actionlint" in text
    assert "# <<< devkit:actionlint" in text


def test_the_insert_touches_nothing_else(tmp_path: Path) -> None:
    """The consumer's excludes and comments survive the insert too."""
    seed = _insert_seed(tmp_path, "DEVKIT_VERSION=1.15.1\n")
    _upgrade(tmp_path, seed, name="insert-surgical")
    text = _config(tmp_path, "insert-surgical")

    assert "# SENTINEL-1654 consumer hook config" in text
    assert "exclude: ^docs/generated/" in text
    assert r"exclude: (^|/)\.envrc$|^vendor/" in text


def test_a_pin_at_the_release_is_left_alone(tmp_path: Path) -> None:
    """The repo has seen the hook, so its absence is a decision — durable."""
    seed = _insert_seed(tmp_path, f"DEVKIT_VERSION={ACTIONLINT_SINCE}\n")
    proc = _upgrade(tmp_path, seed, name="seen")

    assert "- id: actionlint" not in _config(tmp_path, "seen")
    assert "preserved-hook-insert:" not in proc.stdout


def test_no_pin_means_no_evidence_and_no_insert(tmp_path: Path) -> None:
    """Mirrors ``retired_prune_paths()``: no provenance, no write."""
    seed = tmp_path / "nopin"
    seed.mkdir()
    (seed / ".pre-commit-config.yaml").write_text(
        _CONSUMER_HEAD.replace(
            "  # Markdown Linting (excludes auto-generated docs)\n", ""
        )
        + _CONSUMER_TAIL.lstrip("\n"),
        encoding="utf-8",
    )
    proc = _upgrade(tmp_path, seed, name="nopin-ws")

    assert "- id: actionlint" not in _config(tmp_path, "nopin-ws")
    assert "preserved-hook-insert:" not in proc.stdout


def test_the_feature_opt_out_is_honoured(tmp_path: Path) -> None:
    """``DEVKIT_FEATURES_DISABLED`` is the durable "no" the insert must obey."""
    seed = _insert_seed(
        tmp_path, "DEVKIT_VERSION=1.15.1\nDEVKIT_FEATURES_DISABLED=actionlint\n"
    )
    proc = _upgrade(tmp_path, seed, name="optout")

    assert "- id: actionlint" not in _config(tmp_path, "optout")
    assert "preserved-hook-insert:" not in proc.stdout


def test_an_existing_hook_is_never_duplicated(tmp_path: Path) -> None:
    """Also what makes an rc -> final upgrade a no-op."""
    seed = _insert_seed(tmp_path, "DEVKIT_VERSION=1.15.1\n", name="dup-seed")
    config = seed / ".pre-commit-config.yaml"
    config.write_text(
        config.read_text(encoding="utf-8")
        + "\n  - repo: local\n    hooks:\n      - id: actionlint\n"
        + "        name: my own actionlint\n        entry: actionlint\n"
        + "        language: system\n        pass_filenames: false\n",
        encoding="utf-8",
    )
    proc = _upgrade(tmp_path, seed, name="dup")
    text = _config(tmp_path, "dup")

    assert text.count("- id: actionlint") == 1
    assert "name: my own actionlint" in text
    assert "preserved-hook-insert:" not in proc.stdout


def test_a_missing_anchor_skips_the_insert_rather_than_guessing(
    tmp_path: Path,
) -> None:
    """No template neighbour to anchor on means no defensible position."""
    seed = tmp_path / "anchorless"
    seed.mkdir()
    (seed / ".pre-commit-config.yaml").write_text(
        "# SENTINEL-1654 anchorless config\nrepos:\n" + _CONSUMER_TAIL.lstrip("\n"),
        encoding="utf-8",
    )
    (seed / ".vig-os").write_text("DEVKIT_VERSION=1.15.1\n", encoding="utf-8")
    proc = _upgrade(tmp_path, seed, name="anchorless-ws")

    assert "- id: actionlint" not in _config(tmp_path, "anchorless-ws")
    assert "preserved-hook-insert:" not in proc.stdout
    assert "anchor" in proc.stderr


def test_a_rewrite_keeps_the_file_mode(tmp_path: Path) -> None:
    """The consumer's file comes back as it went in, bits included.

    Writing through a temp file and renaming it over the target — what
    ``sed -i`` does — would hand the consumer ``mktemp``'s 0600 and silently
    de-group-read a tracked file.
    """
    seed = _seed(tmp_path)
    (seed / ".pre-commit-config.yaml").chmod(0o644)
    _upgrade(tmp_path, seed, name="mode")

    config = tmp_path / "mode" / ".pre-commit-config.yaml"
    assert "jackdewinter" not in config.read_text(encoding="utf-8")
    assert config.stat().st_mode & 0o777 == 0o644


# ── the preview may never be silent about a mutation ──────────────────────────


def test_preview_reports_the_planned_fold_and_writes_nothing(tmp_path: Path) -> None:
    """#886's report covers a rewrite of a consumer-owned file too."""
    seed = _seed(tmp_path)
    before = (seed / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    proc = _upgrade(tmp_path, seed, name="preview-fold", preview=True)

    assert "pymarkdown-pre-1170" in proc.stdout
    assert "REPLACED" in proc.stdout
    # A preview that told the consumer to hand-fold what the run repairs would
    # be lying in the other direction.
    assert "preserved-hook-drift:" not in proc.stdout
    assert "preserved-hook-fold:" not in proc.stdout
    assert _config(tmp_path, "preview-fold") == before


def test_preview_reports_the_planned_insert(tmp_path: Path) -> None:
    """Same contract for the hook the consumer never received."""
    seed = _insert_seed(tmp_path, "DEVKIT_VERSION=1.15.1\n")
    proc = _upgrade(tmp_path, seed, name="preview-insert", preview=True)

    assert "actionlint" in proc.stdout
    assert "INSERTED" in proc.stdout
    assert "- id: actionlint" not in _config(tmp_path, "preview-insert")


# ── the stock scaffold stays byte-identical ───────────────────────────────────


def test_a_stock_upgrade_reconciles_nothing(tmp_path: Path) -> None:
    """The template already ships both hooks, so a stock repo must stay silent."""
    first = scaffold(tmp_path, name="stock", check=False)
    assert first.returncode == 0, first.stderr
    again = scaffold(tmp_path, name="stock", check=False)
    assert again.returncode == 0, again.stderr

    assert "preserved-hook-fold:" not in again.stdout
    assert "preserved-hook-insert:" not in again.stdout
