"""Contract for release-time bot changelog synthesis (Refs: #1423).

Replaces the per-PR pipeline: entries for Renovate / devkit-adoption PRs are
derived at release cut and finalize from the merged-PR window since the last
stable tag, coalesced to the net delta per dependency, and rendered as a
regenerated ``#### Dependencies`` block that hand-written entries never share.
"""

from __future__ import annotations

import json
import os
import stat
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
from vig_utils.synthesize_bot_changelog import (
    BotPr,
    coalesce,
    last_stable_tag,
    main,
    parse_lockfile_title,
    pr_numbers_from_subjects,
    render_dependencies_block,
    splice_dependencies_block,
)

URL = "https://github.com/vig-os/devkit"


def _pr(
    number: int,
    *,
    author: str = "renovate[bot]",
    title: str = "",
    body: str = "",
    merged_at: str = "2026-01-01T00:00:00Z",
) -> BotPr:
    return BotPr(
        number=number, author=author, title=title, body=body, merged_at=merged_at
    )


# ── PR-number enumeration ─────────────────────────────────────────────────────


def test_pr_numbers_from_subjects_squash_and_merge_shapes() -> None:
    subjects = [
        "chore(deps): update github/codeql-action digest to 5595cca (#1367)",
        "Merge pull request #1368 from vig-os/renovate/github-actions",
        "docs: something unrelated",
        "fix: repeated reference (#1367)",
    ]
    assert pr_numbers_from_subjects(subjects) == [1367, 1368]


def test_pr_numbers_ignores_issue_refs_not_in_pr_position() -> None:
    # Plain "#N" mid-sentence is an issue reference, not a merge suffix.
    assert pr_numbers_from_subjects(["fix: guard against #1348 regressions"]) == []


# ── last stable tag ───────────────────────────────────────────────────────────


def test_last_stable_tag_excludes_prereleases_and_foreign_tags() -> None:
    tags = ["1.7.0", "1.7.1-rc2", "0.9.9", "smoke-1.0", "1.7.0-rc5"]
    assert last_stable_tag(tags) == "1.7.0"


def test_last_stable_tag_orders_numerically_not_lexically() -> None:
    assert last_stable_tag(["1.9.0", "1.10.0"]) == "1.10.0"


def test_last_stable_tag_honors_prefix_and_returns_full_tag() -> None:
    assert last_stable_tag(["v0.3.2", "0.9.0", "v0.3.10-rc1"], tag_prefix="v") == (
        "v0.3.2"
    )


def test_last_stable_tag_none_when_no_stable_tag() -> None:
    assert last_stable_tag(["1.0.0-rc1", "smoke"]) is None


# ── lockfile-maintenance recognition (#1423: the pip/npm gap) ─────────────────


@pytest.mark.parametrize(
    ("title", "scope"),
    [
        ("build(pip): lock file maintenance", "pip"),
        ("build(npm): lock file maintenance", "npm"),
        ("chore(deps): lock file maintenance", "deps"),
        ("Lock file maintenance", ""),
    ],
)
def test_parse_lockfile_title_recognized(title: str, scope: str) -> None:
    assert parse_lockfile_title(title) == scope


@pytest.mark.parametrize(
    "title",
    [
        "build(pip): update dependency ruff to v0.14.0",
        "chore: adopt devkit 1.7.0",
        "feat: lock file maintenance docs",
    ],
)
def test_parse_lockfile_title_rejects_non_lockfile(title: str) -> None:
    assert parse_lockfile_title(title) is None


# ── coalescing: only the net delta since the last release counts ──────────────


def test_coalesce_chains_same_dependency_to_net_delta() -> None:
    # 1.4.2 shipped two codeql entries (#1266 then #1312); the intermediate
    # digest never existed in a published release. The net delta is one line.
    prs = [
        _pr(
            1312,
            title="chore(deps): update github/codeql-action digest to f205ea1",
            body="| github/codeql-action | `e4fba86` -> `f205ea1` |",
            merged_at="2026-07-20T00:00:00Z",
        ),
        _pr(
            1266,
            title="chore(deps): update github/codeql-action digest to e4fba86",
            body="| github/codeql-action | `7188fc3` -> `e4fba86` |",
            merged_at="2026-07-10T00:00:00Z",
        ),
    ]
    result = coalesce(prs)
    assert len(result.deps) == 1
    dep = result.deps[0]
    assert (dep.name, dep.old, dep.new) == (
        "github/codeql-action",
        "7188fc3",
        "f205ea1",
    )
    # PRs cited in merge order regardless of input order.
    assert dep.prs == [1266, 1312]


def test_coalesce_drops_zero_net_delta() -> None:
    prs = [
        _pr(
            10,
            title="build(pip): update dependency foo to v2",
            body="| foo | `1.0` -> `2.0` |",
            merged_at="2026-01-01T00:00:00Z",
        ),
        _pr(
            11,
            title="build(pip): update dependency foo to v1",
            body="| foo | `2.0` -> `1.0` |",
            merged_at="2026-01-02T00:00:00Z",
        ),
    ]
    assert coalesce(prs).deps == []


def test_coalesce_flattens_grouped_pr_rows() -> None:
    grouped = _pr(
        20,
        title="ci(actions): update github-actions (minor and patch)",
        body=(
            "| [actions/checkout](https://github.com/actions/checkout) "
            "| `v4.1.0` -> `v4.2.0` |\n"
            "| [actions/cache](https://github.com/actions/cache) "
            "| `v4.0.0` -> `v4.0.1` |"
        ),
    )
    result = coalesce([grouped])
    assert [(d.name, d.old, d.new, d.prs) for d in result.deps] == [
        ("actions/checkout", "v4.1.0", "v4.2.0", [20]),
        ("actions/cache", "v4.0.0", "v4.0.1", [20]),
    ]


def test_coalesce_title_only_pr_has_no_old_version() -> None:
    result = coalesce([_pr(30, title="build(npm): update dependency eslint to v10")])
    assert [(d.name, d.old, d.new) for d in result.deps] == [("eslint", None, "v10")]


def test_coalesce_rolls_up_lockfile_prs_per_scope() -> None:
    prs = [
        _pr(
            40,
            title="build(pip): lock file maintenance",
            merged_at="2026-01-01T00:00:00Z",
        ),
        _pr(
            42,
            title="build(npm): lock file maintenance",
            merged_at="2026-01-03T00:00:00Z",
        ),
        _pr(
            41,
            title="build(pip): lock file maintenance",
            merged_at="2026-01-02T00:00:00Z",
        ),
    ]
    result = coalesce(prs)
    assert [(lf.scope, lf.prs) for lf in result.lockfiles] == [
        ("pip", [40, 41]),
        ("npm", [42]),
    ]


def test_coalesce_adoptions_keep_only_the_shipped_version() -> None:
    prs = [
        _pr(
            50,
            author="vigos-devkit-upgrade[bot]",
            title="chore: adopt devkit 1.6.0",
            merged_at="2026-01-01T00:00:00Z",
        ),
        _pr(
            51,
            author="vigos-devkit-upgrade[bot]",
            title="chore: adopt devkit 1.7.0",
            merged_at="2026-02-01T00:00:00Z",
        ),
    ]
    result = coalesce(prs)
    assert result.adoptions is not None
    assert result.adoptions.version == "1.7.0"
    assert result.adoptions.prs == [50, 51]


def test_coalesce_skips_non_bot_authors() -> None:
    result = coalesce(
        [
            _pr(
                60,
                author="c-vigo",
                title="build(pip): update dependency ruff to v0.14.0",
            )
        ]
    )
    assert result.deps == [] and result.lockfiles == [] and result.adoptions is None


# ── rendering ─────────────────────────────────────────────────────────────────


def test_render_block_full_shape() -> None:
    prs = [
        _pr(
            1266,
            title="chore(deps): update github/codeql-action digest to e4fba86",
            body="| github/codeql-action | `7188fc3` -> `e4fba86` |",
            merged_at="2026-07-10T00:00:00Z",
        ),
        _pr(
            1312,
            title="chore(deps): update github/codeql-action digest to f205ea1",
            body="| github/codeql-action | `e4fba86` -> `f205ea1` |",
            merged_at="2026-07-20T00:00:00Z",
        ),
        _pr(
            1369,
            title="build(pip): lock file maintenance",
            merged_at="2026-07-21T00:00:00Z",
        ),
        _pr(
            70,
            author="vigos-devkit-upgrade[bot]",
            title="chore: adopt devkit 1.7.1",
            merged_at="2026-07-22T00:00:00Z",
        ),
    ]
    block = render_dependencies_block(coalesce(prs), URL)
    assert block is not None
    assert block.startswith("#### Dependencies\n\n")
    assert (
        "- Update `github/codeql-action` from `7188fc3` to `f205ea1`"
        f" ([#1266]({URL}/pull/1266), [#1312]({URL}/pull/1312))" in block
    )
    assert f"- Lock file maintenance (pip) ([#1369]({URL}/pull/1369))" in block
    assert (
        f"- Adopt vigOS devkit 1.7.1 ([#70]({URL}/pull/70)) —"
        " [release notes](https://github.com/vig-os/devkit/releases/tag/1.7.1)" in block
    )


def test_render_block_without_old_version() -> None:
    block = render_dependencies_block(
        coalesce([_pr(30, title="build(npm): update dependency eslint to v10")]), URL
    )
    assert block is not None
    assert f"- Update `eslint` to `v10` ([#30]({URL}/pull/30))" in block


def test_render_block_empty_is_none() -> None:
    assert render_dependencies_block(coalesce([]), URL) is None


# ── splicing the regenerated block ────────────────────────────────────────────

CHANGELOG = """# Changelog

## Unreleased

### Added

- **Hand-written feature** ([#1](https://x/1))

### Changed

- **Hand-written change** ([#2](https://x/2))

### Fixed

## [1.7.0] - 2026-08-08

### Changed

- **Released entry** ([#3](https://x/3))
"""

BLOCK = "#### Dependencies\n\n- Update `foo` from `1` to `2` ([#9](https://x/9))\n"


def test_splice_appends_block_at_end_of_unreleased_changed() -> None:
    result = splice_dependencies_block(CHANGELOG, BLOCK, version=None)
    unreleased = result[result.index("## Unreleased") : result.index("## [1.7.0]")]
    changed = unreleased[unreleased.index("### Changed") :]
    # Hand-written bullets stay first; the block lands below them.
    assert changed.index("Hand-written change") < changed.index("#### Dependencies")
    assert "- Update `foo` from `1` to `2`" in changed
    # Released sections are never touched.
    released = result[result.index("## [1.7.0]") :]
    assert "#### Dependencies" not in released


def test_splice_is_regeneration_not_accretion() -> None:
    once = splice_dependencies_block(CHANGELOG, BLOCK, version=None)
    new_block = BLOCK.replace("`2`", "`3`").replace(
        "(https://x/9))", "(https://x/9), [#12](https://x/12))"
    )
    twice = splice_dependencies_block(once, new_block, version=None)
    assert twice.count("#### Dependencies") == 1
    assert "to `3`" in twice
    assert "to `2`" not in twice
    # The hand-written entry survives regeneration.
    assert "Hand-written change" in twice


def test_splice_targets_version_section_when_given() -> None:
    frozen = CHANGELOG.replace(
        "## [1.7.0] - 2026-08-08", "## [1.7.1] - TBD", 1
    ).replace("## Unreleased", "## Unreleased\n\nplaceholder-marker\n", 1)
    result = splice_dependencies_block(frozen, BLOCK, version="1.7.1")
    version_section = result[result.index("## [1.7.1] - TBD") :]
    assert "#### Dependencies" in version_section
    unreleased = result[
        result.index("## Unreleased") : result.index("## [1.7.1] - TBD")
    ]
    assert "#### Dependencies" not in unreleased


def test_splice_creates_changed_section_when_missing() -> None:
    changelog = "# Changelog\n\n## [1.7.1] - TBD\n\n### Fixed\n\n- **A fix** ([#4](https://x/4))\n"
    result = splice_dependencies_block(changelog, BLOCK, version="1.7.1")
    # Keep-a-Changelog order: Changed comes before Fixed.
    assert "### Changed" in result
    assert result.index("### Changed") < result.index("### Fixed")
    assert "#### Dependencies" in result


def test_splice_removes_stale_block_when_no_entries_remain() -> None:
    once = splice_dependencies_block(CHANGELOG, BLOCK, version=None)
    result = splice_dependencies_block(once, None, version=None)
    assert "#### Dependencies" not in result
    assert "Hand-written change" in result


def test_splice_missing_version_heading_raises() -> None:
    with pytest.raises(ValueError, match="1.9.9"):
        splice_dependencies_block(CHANGELOG, BLOCK, version="1.9.9")


# ── CLI end-to-end with stubbed git/gh ────────────────────────────────────────

PR_DB = {
    1367: {
        "number": 1367,
        "user": {"login": "renovate[bot]"},
        "title": "chore(deps): update github/codeql-action digest to 5595cca",
        "body": "| github/codeql-action | `d1ba80a` -> `5595cca` |",
        "merged_at": "2026-08-05T00:00:00Z",
    },
    1369: {
        "number": 1369,
        "user": {"login": "renovate[bot]"},
        "title": "build(pip): lock file maintenance",
        "body": "This PR refreshes the lock file.",
        "merged_at": "2026-08-06T00:00:00Z",
    },
    1385: {
        "number": 1385,
        "user": {"login": "c-vigo"},
        "title": "chore: release 1.7.0",
        "body": "",
        "merged_at": "2026-08-04T00:00:00Z",
    },
}


def _write_stub(path: Path, body: str) -> None:
    path.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def stub_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.log"
    calls.touch()
    _write_stub(
        bin_dir / "git",
        f'echo "git $*" >> "{calls}"\n'
        'if [[ "$1" == "tag" ]]; then printf "1.7.0\\n1.7.1-rc1\\n"; exit 0; fi\n'
        'if [[ "$1" == "log" ]]; then\n'
        '  printf "%s\\n" \\\n'
        '    "chore(deps): update github/codeql-action digest to 5595cca (#1367)" \\\n'
        '    "build(pip): lock file maintenance (#1369)" \\\n'
        '    "chore: release 1.7.0 (#1385)" \\\n'
        '    "docs: reference an issue mid-line about #1348 hygiene"\n'
        "  exit 0\nfi\nexit 1",
    )
    gh_cases = "".join(
        f'if [[ "$2" == *"/pulls/{n}" ]]; then cat <<\'EOF\'\n'
        f"{json.dumps(meta)}\nEOF\nexit 0; fi\n"
        for n, meta in PR_DB.items()
    )
    _write_stub(
        bin_dir / "gh",
        f'echo "gh $*" >> "{calls}"\n{gh_cases}exit 1',
    )
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("GITHUB_REPOSITORY", "vig-os/devkit")
    monkeypatch.setenv("GITHUB_REPOSITORY_URL", URL)
    return calls


def _seed_changelog(tmp_path: Path) -> Path:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(CHANGELOG)
    return path


def test_main_synthesizes_window_since_last_stable_tag(
    tmp_path: Path, stub_bin: Path
) -> None:
    changelog = _seed_changelog(tmp_path)
    assert main(["--changelog", str(changelog)]) == 0
    text = changelog.read_text()
    assert "#### Dependencies" in text
    assert "- Update `github/codeql-action` from `d1ba80a` to `5595cca`" in text
    assert "- Lock file maintenance (pip)" in text
    # The human release PR (#1385) is not a bot PR: no entry.
    assert "1385" not in text
    # The log window starts at the last stable tag, not an rc.
    assert "1.7.0..HEAD" in stub_bin.read_text()
    # Mid-line issue references are never treated as PR numbers.
    assert "/pulls/1348" not in stub_bin.read_text()


def test_main_missing_changelog_is_noop(tmp_path: Path, stub_bin: Path) -> None:
    assert main(["--changelog", str(tmp_path / "absent.md")]) == 0


def test_main_dry_run_prints_block_and_leaves_file_untouched(
    tmp_path: Path, stub_bin: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = _seed_changelog(tmp_path)
    before = changelog.read_text()
    assert main(["--changelog", str(changelog), "--dry-run"]) == 0
    assert changelog.read_text() == before
    assert "#### Dependencies" in capsys.readouterr().out
