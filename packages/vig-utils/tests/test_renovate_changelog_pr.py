"""Tests for bot-PR metadata parsing (Refs: #506, #1423).

Since #1423 this module is a parsing library only: entry formatting, insertion
and the CLI moved to release-time synthesis (``synthesize_bot_changelog``).
"""

from __future__ import annotations

import textwrap

import pytest
from vig_utils.renovate_changelog_pr import (
    parse_adoption_title,
    parse_renovate_pr_updates,
)


def test_parse_title_single_dependency_digest() -> None:
    title = (
        "ci(actions): update actions/checkout digest to "
        "de0fac2e4500dabe0009e67214ff5f5447ce83dd"
    )
    updates = parse_renovate_pr_updates(title, "")
    assert len(updates) == 1
    pkg, old_v, new_v = updates[0]
    assert pkg == "actions/checkout"
    assert old_v is None
    assert new_v == "de0fac2e4500dabe0009e67214ff5f5447ce83dd"


def test_parse_title_single_dependency_version() -> None:
    title = "build(pip): update dependency urllib3 to v2.6.3"
    updates = parse_renovate_pr_updates(title, "")
    assert updates == [("urllib3", None, "v2.6.3")]


def test_parse_body_markdown_table() -> None:
    body = textwrap.dedent(
        """
        This PR contains the following updates:

        | Package | Type | Update | Change |
        |---------|------|--------|--------|
        | [actions/checkout](https://github.com/actions/checkout) | action | minor | `v4.1.0` -> `v4.2.0` |
        | [actions/cache](https://github.com/actions/cache) | action | patch | `v4.0.0` -> `v4.0.1` |
        """
    ).strip()
    updates = parse_renovate_pr_updates("chore(deps): update all", body)
    assert len(updates) == 2
    assert updates[0][0] == "actions/checkout"
    assert updates[0][1] == "v4.1.0"
    assert updates[0][2] == "v4.2.0"
    assert updates[1][0] == "actions/cache"


def test_parse_body_markdown_table_unicode_arrow() -> None:
    # Renovate renders the change cell with a Unicode arrow (U+2192), not ASCII "->".
    body = textwrap.dedent(
        """
        This PR contains the following updates:

        | Package | Type | Update | Change |
        |---------|------|--------|--------|
        | [docker/login-action](https://github.com/docker/login-action) | action | minor | `v4.2.0` → `v4.4.0` |
        | [aquasecurity/trivy](https://github.com/aquasecurity/trivy) | uses-with | minor | `v0.71.2` → `v0.72.0` |
        """
    ).strip()
    updates = parse_renovate_pr_updates("ci(actions): update github-actions", body)
    assert len(updates) == 2
    assert updates[0] == ("docker/login-action", "v4.2.0", "v4.4.0")
    assert updates[1] == ("aquasecurity/trivy", "v0.71.2", "v0.72.0")


def test_parse_change_cell_unicode_arrow_digest() -> None:
    # Unquoted digest cell with a Unicode arrow must also parse.
    body = textwrap.dedent(
        """
        | Package | Type | Update | Change |
        |---------|------|--------|--------|
        | [actions/checkout](https://github.com/actions/checkout) | action | digest | abc1234 → def5678 |
        """
    ).strip()
    updates = parse_renovate_pr_updates("chore(deps): update all", body)
    assert updates == [("actions/checkout", "abc1234", "def5678")]


def test_parse_adoption_title_final() -> None:
    assert parse_adoption_title("chore: adopt devkit 1.7.0") == "1.7.0"


def test_parse_adoption_title_rc() -> None:
    assert parse_adoption_title("chore: adopt devkit 1.7.0-rc3") == "1.7.0-rc3"


@pytest.mark.parametrize(
    "title",
    [
        "chore: adopt devkit",
        "chore: adopt devkit next",
        "feat: adopt devkit 1.7.0",
        "chore: adopt devkit 1.7.0 and more",
        "chore(scope): adopt devkit 1.7.0",
    ],
)
def test_parse_adoption_title_rejects_non_adoption(title: str) -> None:
    assert parse_adoption_title(title) is None
