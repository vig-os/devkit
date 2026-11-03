---
type: issue
state: open
created: 2026-10-13T01:11:48Z
updated: 2026-10-13T01:11:48Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1878
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-13T09:14:39.846Z
---

# [Issue 1878]: [Rust pack: flake deny check runs --offline, so [advisories] is never enforced](https://github.com/vig-os/devkit/issues/1878)

## What happens
In the Rust pack, the flake's deny check runs `cargo --offline deny check bans licenses sources`. Advisories aren't checked: the Nix sandbox has no network to fetch the RustSec database. So a consumer's `deny.toml` `[advisories]` section (e.g. `yanked = "deny"`, vulnerability denial) is **never enforced** by `nix flake check`, and nothing else in the scaffolded CI runs it either.

## Seen in
gerchowl/nodd's pre-mortem on adopting devkit 1.19.0-rc1.

## Expected
One of these:
- a networked CI job (`cargo deny check advisories`, or `cargo audit`) in the Rust pack's CI;
- a pinned advisory-db flake input, so the check runs offline and reproducibly;
- docs that say advisories aren't covered, with the recommended job.

## Workaround
Consumers add their own networked job to `ci-extension.yml`.

