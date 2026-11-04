"""Keep new consumer changelogs free of devkit release history (#2025)."""

from pathlib import Path


def test_workspace_changelog_is_empty_skeleton():
    """The first-deploy seed contains headings only, never release entries."""
    seed = Path(__file__).resolve().parents[1] / "assets/workspace/CHANGELOG.md"

    assert (
        seed.read_text()
        == """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security
"""
    )
