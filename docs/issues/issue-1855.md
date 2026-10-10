---
type: issue
state: open
created: 2026-10-09T23:09:32Z
updated: 2026-10-09T23:09:32Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1855
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-10T08:21:25.556Z
---

# [Issue 1855]: [rust: scaffolded renovate.json omits the cargo manager, so Rust dependencies are never monitored](https://github.com/vig-os/devkit/issues/1855)

## Summary

A Rust consumer repo scaffolded by devkit gets a `renovate.json` whose `enabledManagers` omits
`cargo`, so **no Rust dependency is ever monitored** — not `Cargo.toml`, not `Cargo.lock`. The
scaffolded list targets ecosystems a Rust-only repo does not have.

Observed in a Rust consumer (`gerchowl/pidgy`, Rust workspace + Nix flake, using
`devkit.lib.mkRustProject`):

```json
{
  "extends": ["github>gerchowl/pidgy//.github/renovate-default"],
  "enabledManagers": ["github-actions", "pep621", "npm"]
}
```

| manager | status in a Rust consumer |
|---|---|
| `pep621` | no-op — no `pyproject.toml` exists |
| `npm` | no-op — no `package.json` exists |
| `github-actions` | nearly a no-op — `renovate-default`'s final rule disables the devkit-managed workflow files (correctly, since devkit advances those pins upstream) |
| `cargo` | **absent** — 5 `Cargo.toml` files and `Cargo.lock` unmonitored |
| `nix` | absent — `flake.lock` unmonitored |

Net effect: Renovate has nothing to do in a Rust consumer, while the repo's entire real
dependency surface goes unwatched.

## Why it mattered in practice

The gap was invisible until `cargo deny` was run by hand, which surfaced three advisories that
had accumulated silently:

| advisory | crate | note |
|---|---|---|
| [RUSTSEC-2026-0285](https://rustsec.org/advisories/RUSTSEC-2026-0285) | `rustls` | TLS 1.3 handshake messages accepted across encryption level boundaries — in the consumer's live IMAP TLS path |
| [RUSTSEC-2026-0194](https://rustsec.org/advisories/RUSTSEC-2026-0194) | `quick-xml` | quadratic run time on duplicate attribute names |
| [RUSTSEC-2026-0195](https://rustsec.org/advisories/RUSTSEC-2026-0195) | `quick-xml` | unbounded namespace-declaration allocation (memory-exhaustion DoS) |

Both `quick-xml` advisories are reached transitively via `calamine` and sit in code that parses
untrusted attachment bytes. A direct dependency was also six major versions stale (`zip 2.x`
while 8.x is current), which no PR had ever proposed.

`cargo deny` does catch advisories, but it is a *gate*, not a *bump*: it tells you something is
wrong at commit time and leaves the upgrade to a human. That is the job Renovate was supposed to
be doing, and `SECURITY.md` says it is:

> - Renovate monitors dependencies for updates and known vulnerabilities

For a Rust consumer that line is currently inaccurate — which is arguably the worse half of this
bug, since it reads as assurance.

## Suggested fix

1. **Add `cargo` to `enabledManagers`** in the Rust scaffold's `renovate.json` (or make the list
   language-conditional, so Rust repos get `cargo` and Python repos get `pep621` rather than every
   repo getting the union).
2. **Add cargo `packageRules` to `renovate-default`** in the same house style the preset already
   uses for github-actions and npm — group minor/patch, keep majors separate, set
   `semanticCommitType`/`semanticCommitScope` so commits satisfy the devkit commit-message gate.
   Worth noting: the existing `lockFileMaintenance` rule already benefits cargo once the manager is
   on, since it picks up in-range transitive fixes like the `quick-xml` one.
3. **Consider `nix`** for flake-based consumers, so `flake.lock` inputs are proposed rather than
   bumped by hand.
4. **Reword the `SECURITY.md` line** to say what is actually monitored, since the file is
   devkit-managed and regenerated on upgrade (a consumer cannot fix it locally — local edits are
   lost).

Happy to send a PR if you'd like it in a particular shape — especially re: whether
`enabledManagers` should become language-conditional or just gain `cargo` unconditionally.

