---
type: issue
state: closed
created: 2026-09-01T12:44:51Z
updated: 2026-09-01T14:11:47Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1595
comments: 1
labels: feature, area:workspace, effort:small, semver:minor
assignees: none
milestone: 1.13.0
projects: none
parent: none
children: none
synced: 2026-09-01T15:12:52.242Z
---

# [Issue 1595]: [[FEATURE] vigos.ghdash: let a section profile set its own issuesSections](https://github.com/vig-os/devkit/issues/1595)

## Description

`vigos.ghdash.profiles` names one section list per profile, and the wrapper
writes it to **both** `prSections` and `issuesSections` in the rendered
per-repo config ([`nix/home/ghdash.nix#L72-L79`](https://github.com/vig-os/devkit/blob/dev/nix/home/ghdash.nix#L72-L79)).
Let a profile carry a distinct issues list — and, where it does not, stop
silently overwriting a consumer's own `issuesSections`.

## Problem Statement

PR queues and issue queues are not filtered the same way. The qualifiers that
make a PR profile useful — `review-requested:@me`, `draft:false`,
`reviewed-by:@me` — either do not apply to issues or mean something else, so a
profile written for pull requests lands a permanently empty section in the
issues view.

That is exactly what the feature was built for. The motivating case in #1586 is
a team repo whose dashboard leads with `is:open review-requested:@me`; used as a
profile, the same filter becomes a dead "Needs my review" tab under Issues. The
only way out today is to write the profile down to the intersection of what both
views understand, which throws away the reason for having a profile at all.

There is a second, quieter half. `templateText` sets both keys
unconditionally:

```nix
config.programs.gh-dash.settings
// {
  prSections = sections';
  issuesSections = sections';
}
```

so a consumer who tunes `programs.gh-dash.settings.issuesSections` keeps it for
bare `gh-dash` and loses it in **every** `gh-dash-repo` launch, including
`default` — with no warning and no option to express the intent. Since the
`prs` window of a `vigos.sesh` layout runs `gh-dash-repo`, that is the launch
path that actually gets used.

## Proposed Solution

Widen the profile type to accept either shape, so existing configs keep
working unchanged:

```nix
profileType = lib.types.coercedTo (lib.types.listOf sectionModule)
  (l: { prSections = l; issuesSections = l; })
  (lib.types.submodule {
    options = {
      prSections = lib.mkOption { type = lib.types.listOf sectionModule; };
      issuesSections = lib.mkOption {
        type = lib.types.nullOr (lib.types.listOf sectionModule);
        default = null;   # null = mirror prSections, today's behaviour
      };
    };
  });
```

- A bare list stays a bare list: `profiles.shared = [ … ]` renders identically
  to today, so nothing in a released consumer config changes.
- The attribute form lets a profile say what the issues view should hold —
  including `issuesSections = [ ]` to leave it empty rather than wrong.
- `templateText` takes the two lists instead of one and stops folding them
  together.

For the `default` profile, prefer the consumer's own
`programs.gh-dash.settings.issuesSections` when it is set to something other
than the module's `mkDefault`, instead of overwriting it. Scope is the wrinkle:
generated sections compose the `__GH_DASH_SCOPE__` placeholder, while a
hand-written section carries a concrete scope already. Cleanest is to pass such
sections through verbatim (the consumer chose that scope) and document that a
section wanting to follow the launch repo writes the placeholder itself.

## Alternatives Considered

- **A parallel `issuesProfiles` option.** Two attrsets keyed by the same names,
  with nothing enforcing they stay in step, and `gh-dash-repo <name>` silently
  resolving in two places. A profile is one dashboard; it should be one entry.
- **Leaving it to the consumer.** Not reachable: the wrapper's substitution is
  the only thing that scopes a profile, and it is the code doing the
  overwriting. Opting out means dropping the profile mechanism entirely.
- **Documenting it as a limitation.** Cheap, but the failure is silent — the
  dead tab looks like a broken query, and the discarded `issuesSections` looks
  like a home-manager bug.

## Additional Context

- Introduced with the profiles feature in #1586 (PR #1591); no released
  consumer depends on the current fold, which is what keeps a coerced type
  purely additive.
- Composes with `vigos.sesh` layout profiles (#1583): a layout's `prs` window
  runs `gh-dash-repo <name>`, so the fix lands wherever the profile is already
  selected — no new declaration site.
- Found while migrating a downstream personal config onto `vigos.ghdash`: its
  org repos want a review-led PR dashboard, and every one of them would carry
  an always-empty "Needs my review" section under Issues.
- Tests: `tests/test_flake_checks.py` already schema-asserts the rendered
  profile templates, so the new shape has an obvious place to be covered —
  bare-list parity, a split profile, and the untouched-`issuesSections` case.

## Impact

Backward compatible. Every current profile is a list and coerces to today's
meaning, so rendered templates are byte-identical unless a consumer opts into
the attribute form. Benefits any consumer whose PR and issue workflows differ —
which is any repo that reviews pull requests.

## Changelog Category

Added

---

# [Comment #1]() by [c-vigo]()

_Posted on September 1, 2026 at 01:59 PM_

Merged to `dev` in #1596 (2b7ae1fc).

A profile is now either a bare list (both views, unchanged meaning) or `{ prSections; issuesSections; }`, with `issuesSections = [ ]` leaving the issues view empty rather than wrong; `default` keeps a consumer-set `programs.gh-dash.settings.issuesSections` verbatim instead of overwriting it. Backward compatibility verified byte-for-byte against `dev` (bare-list profile with a `limit`, plus the generated settings) — diff empty.

One deviation from the proposal: `coercedTo sectionList …` does not evaluate, since nixpkgs asserts the source type carries no submodules. The source type is shape-only (`listOf anything`) and the entries are type-checked by `prSections` after coercion, so a malformed section still fails at eval.

