---
type: issue
state: closed
created: 2026-09-15T13:51:00Z
updated: 2026-09-16T17:58:41Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1633
comments: 1
labels: feature, area:workspace
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-17T07:29:39.175Z
---

# [Issue 1633]: [[FEATURE] Refs policy: exempt a named set of commit types, not just the literal `chore`](https://github.com/vig-os/devkit/issues/1633)

### Description

`DEVKIT_REFS_POLICY` (#1282) decides which commit types may omit the `Refs:` line, but it is a three-value enum whose "some types exempt" case is hardcoded to the literal type name `chore`. A consumer that adds a custom commit type via `DEVKIT_COMMIT_TYPES` (#1431) cannot exempt that type without exempting every type.

Make the exempt set a list, mirroring the full-replacement-list pattern `DEVKIT_COMMIT_TYPES` and `DEVKIT_BRANCH_TYPES` already establish.

### Problem Statement

The underlying tool already supports this — `validate-commit-msg` takes `--refs-optional-types <comma-separated list>` and would happily accept `chore,record`. The Nix/scaffold layer is what clamps it, in `nix/hooks.nix`:

```nix
refsOptionalTypesFor = refsPolicy: commitTypes:
  if refsPolicy == "optional" then lib.concatStringsSep "," commitTypes
  else if refsPolicy == "required" then "none"
  else "chore";
```

plus the matching assertion in `mkProjectShell`:

```nix
assert pkgs.lib.assertMsg (builtins.elem refsPolicy [ null "chore-optional" "optional" "required" ]) ...
```

`DEVKIT_COMMIT_TYPES` exists precisely so a consumer can add a domain-specific type. A concrete case: a repo that keeps an append-only data record (a CSV registry or similar) adds a `record` type so those commits are greppable in history and distinct from `chore`. Routine record updates are made deliberately without an issue — the record *is* the change, and there is nothing for an issue to add. But `record` is not the literal string `chore`, so it inherits the Refs requirement.

The two knobs therefore compose badly: you can add the type, but you cannot give it the Refs treatment the type was added for.

Note this is not locally patchable. The value feeds three renderers in lockstep — the flake-generated hook, the scaffolded `.pre-commit-config.yaml`, and CI's `resolve-toolchain` `refs-optional-types` output. A consumer hand-editing its own flake would pass locally and still fail `commit-checks`, because CI re-derives the list from the same key.

### Proposed Solution

Add `DEVKIT_REFS_OPTIONAL_TYPES` — a comma-separated, whitespace-tolerant FULL REPLACEMENT list of types that may omit `Refs:`, defaulting to `chore`.

- Absent/empty resolves to `chore`, i.e. exactly today's `chore-optional` behaviour. No change for devkit or existing consumers.
- Entries must be a subset of the resolved `DEVKIT_COMMIT_TYPES`; guard loudly at scaffold time, the way the existing charset guards do.
- Flows through the same three renderers, so local and CI stay in lockstep.

This also subsumes the existing enum, which becomes expressible rather than special:

| `DEVKIT_REFS_POLICY` | equivalent list |
|---|---|
| `chore-optional` (default) | `chore` |
| `optional` | the resolved `DEVKIT_COMMIT_TYPES` |
| `required` | empty (`none`) |

Either keep `DEVKIT_REFS_POLICY` as sugar over the new key, or deprecate it once consumers migrate. Keeping both is fine as long as precedence is documented — the narrower key should win.

### Alternatives Considered

**`DEVKIT_REFS_POLICY=optional`.** Available today and a one-line change, but it drops Refs enforcement for `feat`, `fix`, `docs` and everything else to fix one type. For a consumer that wants a reviewable audit trail this trades away the thing the policy exists to protect.

**Use `chore` for record-type commits.** Works, and is the current workaround. But it erases the distinction `DEVKIT_COMMIT_TYPES` was added to create: the type is what makes those commits greppable and what a changelog or audit tool keys on. Adding a type and then not being able to use it is the smell.

**Open a placeholder issue per record change.** Satisfies the gate and defeats its purpose — issues that exist only to be referenced are noise, and they make the traceability signal worse, not better.

**Let `refsPolicy` accept a raw list in `mkProjectShell` only.** Half a fix: the flake surface would accept it while the scaffold and CI renderers still map from the enum, so local and CI would disagree. The key has to change at the manifest level for all three to follow.

### Additional Context

Builds directly on #1282 (`DEVKIT_REFS_POLICY`) and #1431 (`DEVKIT_COMMIT_TYPES`), and follows the same realize-at-scaffold-time pattern both use. Related: #1434, which made the flake-generated consumer hooks read these keys at eval time.

### Impact

Backward compatible: an absent key resolves to `chore`, byte-identical to today's default render. Benefits any consumer that has added a custom commit type whose commits are legitimately issue-less. Scope is small — one manifest key, the `refsOptionalTypesFor` mapping, the scaffold render, and the `resolve-toolchain` output.

---

# [Comment #1]() by [c-vigo]()

_Posted on September 16, 2026 at 05:58 PM_

Shipped to `dev` in #1639 (merge commit 7ce8030b), all 14 checks green.

`DEVKIT_REFS_OPTIONAL_TYPES` landed as proposed: a comma-separated,
whitespace-tolerant FULL REPLACEMENT list, defaulting to `chore` when
absent or blank, so devkit and every existing consumer render
byte-identically. It flows through all three renderers from the one key —
`render_refs_policy` in `assets/init-workspace.sh`, `mkProjectShell`'s new
`refsOptionalTypes` argument (`nix/hooks.nix` → `flake.nix` → the `.vig-os`
reader in the scaffold template), and `resolve-toolchain`'s
`refs-optional-types` output — so local and CI cannot disagree.

Entries must be lowercase alphanumerics **and** a subset of the resolved
`DEVKIT_COMMIT_TYPES`; the scaffold aborts loudly and `mkProjectShell` fails
eval, while CI warns rather than failing the job. `hooksModule.defaultCommitTypes`
is now exported so the flake's subset assert validates against the same list
the hook argv is built from, rather than a fourth copy of the stock 11.

**Precedence**, as the issue left open: `DEVKIT_REFS_POLICY` is kept as sugar
and the narrower key wins, with a notice printed when both are set. The enum
was not deprecated — it remains the only way to express "exempt nothing",
because an empty `--refs-optional-types` reads as falsy to
`validate-commit-msg` and reverts to its own `{chore}` default, which is why
`required` still travels as the `none` sentinel.

Two defects were caught in review and fixed before merge, each with a
regression test committed first:

- **The scaffold render has to gate on the keys, not the resolved value.**
  `.pre-commit-config.yaml` is preserved across upgrades, never
  template-overwritten, so its current arg is whatever the previous render
  left. Skipping the `sed` because the resolved value happened to equal the
  `chore` default stranded a consumer *narrowing* its exempt set with the
  previous, wider arg locally while CI resolved the narrow one — precisely
  the divergence this issue exists to prevent.
- **Fail-safe for an exemption list means the smallest set, not the stock
  mapping.** CI's fallback on an invalid value went to the
  `DEVKIT_REFS_POLICY` mapping, so under `DEVKIT_REFS_POLICY=optional` a typo
  in the new key switched the Refs gate off for every type behind a warning.
  It now clamps to `chore` unless the policy is already narrower (`none`).
  This is the one place the #1431 commit-types analogy inverts: there the
  stock list is a subset of any sane custom one, here it is not.

Also fixed: `docs/COMMIT_MESSAGE_STANDARD.md` is shipped to consumers and
still said only `chore` is exempt — it now carries the same consumer-knob
pointer the commit-types table has.

Deliberately out of scope, noted in the PR: the pre-existing staleness when a
consumer *clears* a render key. `render_commit_types` and
`render_branch_types` gate on "key absent", so clearing the key leaves the
previous render in the preserved `.pre-commit-config.yaml`. This change
matches that behaviour rather than diverging from it; fixing it properly
means an unconditional `sed` guarded against the flake-hooks store symlink
across all three renders, which wants its own issue.

Closing as done. It reaches consumers with the next release train.

