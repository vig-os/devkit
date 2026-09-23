---
type: issue
state: closed
created: 2026-09-23T09:44:21Z
updated: 2026-09-23T12:59:18Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1666
comments: 1
labels: security, security-scan
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-23T14:38:47.425Z
---

# [Issue 1666]: [Security exception register (dev): exceptions expire 2026-09-30](https://github.com/vig-os/devkit/issues/1666)

The following security exceptions on `dev` expire on **2026-09-30** — within 7 days. They are still valid; `check-expirations` starts failing every branch, both nightly lanes and the release train the day *after* that date.

- `CVE-2026-27820` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-11822` — `.vulnixignore` (7 day(s) left)
- `CVE-2026-11824` — `.vulnixignore` (7 day(s) left)
- `CVE-2025-59777` — `.vulnixignore` (7 day(s) left)
- `CVE-2025-62689` — `.vulnixignore` (7 day(s) left)

- **Scanned ref:** `dev`
- **Expiry date:** 2026-09-30
- **Workflow run:** https://github.com/vig-os/devkit/actions/runs/35844608653

**A renewal is a re-verification, not a date bump.** Before touching any date:

1. Read the latest nightly findings delta for this ref (the `nix-image-cve-scan-dev` artifact on the most recent run) against the current closure.
2. **Delete** every entry the pin advance has cleared — the expiry grid exists so entries die rather than roll forward.
3. Renew only what is still genuinely accepted, re-stating the rationale, and snap the new date onto the Wednesday grid.

See `docs/CONTAINER_SECURITY.md` (*Exception registers* / *Expiry dates land on a Wednesday*). Close this issue once the register has been reconciled.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 23, 2026 at 12:59 PM_

Reconciled on `dev` in #1670 (merged as `b04a8ff5`).

The `2026-09-30` block does not survive as a block — all five entries were re-verified online against NVD CPE configurations, per-source CVSS and the nixpkgs branch contents, rather than date-bumped:

| CVE | Package | Outcome |
|---|---|---|
| `CVE-2026-27820` | zlib 1.3.2 | **CPE mismatch** — moved to the Class 1 block (`2027-06-23`) |
| `CVE-2025-59777` / `-62689` | libmicrohttpd 1.0.2 | renewed → `2026-10-21` |
| `CVE-2026-11822` / `-11824` | sqlite 3.51.2 | renewed → `2026-11-11` |

`CVE-2026-27820` is not this product: NVD's only CPE for it is `cpe:2.3:a:ruby-lang:zlib:*:*:*:*:*:ruby:*:*` (`target_sw=ruby`) — the Ruby zlib gem — affecting gem 3.0.0-and-below / 3.1.0-3.1.1 / 3.2.0-3.2.1. vulnix matched the C zlib 1.3.2 only because 1.3.2 sorts below 3.0.1. It was the 9.8 of the set and the entry with the weakest rationale, and it is a definitive false positive.

The same pass deleted 18 entries the pin advance had cleared (curl ×9 + openssl ×7 + libxml2 + pcre2), whose shared lever — [NixOS/nixpkgs#563094](https://github.com/NixOS/nixpkgs/pull/563094) — reached `release-26.05` on 2026-09-19 and the pin via #1662 on 09-21.

Register on `dev`: **32 → 15 entries**, on six distinct Wednesdays (`2026-10-07`, `10-14`, `10-21`, `11-04`, `11-11`, `2027-06-23`) with no two blocks sharing a date. `check-expirations` validates all 15.

`main`'s register is tracked separately in #1667 and is **not** reconciled yet.

