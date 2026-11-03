# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- **Advisory glossary candidate discovery** ([#1994](https://github.com/vig-os/devkit/issues/1994))
  - Add JSON-line candidate reports and a just recipe for terminology review, with measured precision fixtures.
  - Reject dead rules, protect registered words across simple inline markup and partial overlaps, deduplicate overlapping hits, and clarify source diagnostics.
  - Preserve forbidden rules containing registered names; filter candidate markup/code noise, join wrapped names, retain source context, and allow extra stopwords.
  - Cache nearest-term comparisons across files and report representative precision, recall and benchmark results.

- **Opt-in terminology register checks** ([#1994](https://github.com/vig-os/devkit/issues/1994))
  - Validate glossary YAML and reject forbidden names and unknown part numbers in document sources.
  - Preserve registered names and casing corrections, scan tracked prose across whitespace, and reject ambiguous registers.
  - Include jsonschema and its runtime dependencies in all images/toolchains via vig-utils, sharing the editor and hook schema validator; docs hooks remain opt-in.

### Changed

### Deprecated

### Removed

### Fixed

- **Promote releases on plan-limited private repositories** ([#1851](https://github.com/vig-os/devkit/issues/1851))
  - Stop retrying only rulesets plan-limit HTTP 403 responses and require one approval by default in both promote gates.
  - Count distinct current-head approvals from each reviewer's latest APPROVED, CHANGES_REQUESTED, or DISMISSED review, ignoring COMMENTED and PENDING and excluding the PR author; keep host retry diagnostics out of API responses.
  - Add `DEVKIT_RELEASE_REQUIRED_APPROVALS` for the 403 fallback; solo consumers can set 0, while real ruleset requirements retain precedence.

### Security
