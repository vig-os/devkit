# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

### Changed

### Deprecated

### Removed

### Fixed

- **Promote releases on plan-limited private repositories** ([#1851](https://github.com/vig-os/devkit/issues/1851))
  - Stop retrying only rulesets plan-limit HTTP 403 responses and require one approval by default in both promote gates.
  - Count distinct current-head approvals from each reviewer's latest review, excluding the PR author; keep host retry diagnostics out of API responses.
  - Add `DEVKIT_RELEASE_REQUIRED_APPROVALS` for the 403 fallback; solo consumers can set 0, while real ruleset requirements retain precedence.

### Security
