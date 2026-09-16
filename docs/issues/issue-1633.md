---
type: issue
state: open
created: 2026-09-15T13:51:00Z
updated: 2026-09-15T13:51:00Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1633
comments: 0
labels: feature, area:workspace
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-16T07:33:11.411Z
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

