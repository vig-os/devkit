---
type: issue
state: closed
created: 2026-08-07T14:46:52Z
updated: 2026-08-07T15:59:52Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1370
comments: 2
labels: bug, priority:high, area:ci, effort:small, semver:patch, security
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:31:00.409Z
---

# [Issue 1370]: [[BUG] Release tags are unsigned annotated tag objects; publish a lightweight tag instead](https://github.com/vig-os/devkit/issues/1370)

## Summary

Every release tag devkit publishes is an **annotated tag object with an unsigned
tagger**, created by a bot identity that can never produce a verifiable
signature. The release *commit* is GitHub-verified; the tag that points at it is
not. That is a supply-chain gap in a repo whose `SECURITY.md` advertises
attested, signed release artifacts (cosign image signatures, SLSA provenance,
SBOM attestation).

## Live evidence (tag `1.6.0`)

```console
$ gh api repos/vig-os/devkit/git/refs/tags/1.6.0 --jq '.object.type'
tag                                   # -> annotated tag object, not a commit

$ gh api repos/vig-os/devkit/git/tags/bad7b6a18ae645ccc19b4cb838c57c4e80543963 \
    --jq '{tagger, verification}'
{
  "tagger": {
    "date": "2026-08-04T12:27:52Z",
    "email": "release@vig-os.local",
    "name": "vigOS Release Bot"
  },
  "verification": {
    "payload": null,
    "reason": "unsigned",
    "signature": null,
    "verified": false,
    "verified_at": null
  }
}
```

The commit the tag points at *is* verified:

```console
$ gh api repos/vig-os/devkit/commits/b590198a6956eb0bf75aec706d12b9d16728153e \
    --jq '.commit.verification.reason'
valid
```

## Root cause

`.github/workflows/release.yml` (publish job) creates the tag locally with

```yaml
- name: Create annotated tag
  run: git tag -a "$PUBLISH_VERSION" -m "Release $PUBLISH_VERSION"
```

after `git config user.name/user.email` are set from the workflow inputs
(`vigOS Release Bot <release@vig-os.local>`), then `git push origin
"$PUBLISH_VERSION"`. `git tag -a` writes a **tag object** carrying a tagger
identity, and nothing signs it.

## Why "just sign it" is not available

- **No key can be attached to the bot.** The tag is pushed under the Release
  **GitHub App** installation token. GitHub Apps have no GPG/SSH signing key that
  can be registered for verification, so no `git tag -s` variant can ever render
  as *Verified* for this identity.
- **The REST route is unsigned too.** Creating the tag object server-side with
  `POST /repos/{owner}/{repo}/git/tags` does **not** make GitHub sign it — unlike
  `POST /git/commits` reached through the higher-level Contents/merge APIs, the
  Git Data tag endpoint stores the payload verbatim and the result is again
  `reason: "unsigned"`.

So as long as an annotated tag object exists, there is an unsigned object in the
release chain.

## Proposed fix

**Stop creating an annotated tag object at all — publish a lightweight tag.**

A lightweight tag is just a ref (`refs/tags/<version>`) pointing directly at the
release commit. It has no tagger and no payload, so there is nothing to sign and
nothing that can report `unsigned`; the object the tag resolves to is the
GitHub-verified release commit.

Implementation sketch (publish job):

- replace `git tag -a` + `git push origin <tag>` with
  `POST /repos/{owner}/{repo}/git/refs` with `ref=refs/tags/<version>` and
  `sha=<finalize_sha>`, using the Release App token already generated in the job;
- keep the existing behaviours: skip when `finalize.outputs.tag_already_exists`
  is `true`, fail a **candidate** run when the RC tag already exists on origin
  (concurrent-publish detection), and treat a lost create race as success only
  when the existing ref already points at the finalize SHA;
- the downstream consumers already tolerate lightweight tags — `release.yml`'s
  `tag_already_exists` probe and the push-race recovery both fall back from
  `refs/tags/<v>^{}` to `refs/tags/<v>`.

## Scope

- `.github/workflows/release.yml` — the only place in devkit's own release chain
  that creates a tag. `prepare-release.yml` only checks existence
  (`git tag -l | grep`), `promote-release.yml` only deletes RC tags by ref, and
  `prepare-release-extension.yml` does not touch tags — all are
  annotation-agnostic.
- `docs/RELEASE_CYCLE.md` — the publish-job description says "creates annotated
  tag".

Out of scope (separate follow-ups):

- the **scaffold** shipped to consumers
  (`assets/workspace/.github/workflows/release-publish.yml`) still does
  `git tag -a`, and `docs/MIGRATION.md` documents peeling its annotated tags;
- **tag immutability** is a ruleset concern, tracked in `vig-os/org-config`, not
  something this workflow can provide.

## Acceptance criteria

- [ ] `release.yml` creates `refs/tags/<version>` as a lightweight ref at the
      release commit; no `git tag -a` remains in devkit's release chain
- [ ] candidate-collision and already-exists-at-finalize-SHA behaviours preserved
- [ ] `docs/RELEASE_CYCLE.md` no longer claims an annotated tag
- [ ] the next release tag reports `"type": "commit"` on
      `GET /git/refs/tags/<version>` (no tag object, nothing unsigned)

---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 03:21 PM_

Follow-up filed for the downstream half of this defect: #1378 — the consumer scaffold (`assets/workspace/.github/workflows/release-publish.yml`) still creates annotated tags via `git tag -a`, so every scaffolded repo's version tag is still `unsigned`. Kept out of #1374 because it changes every consumer's stamped workflow and must ride a devkit release + scaffold sync.

---

# [Comment #2]() by [c-vigo]()

_Posted on August 7, 2026 at 03:59 PM_

Fixed on dev by PR #1374 (d3d9f00e): release.yml now publishes the version tag as a lightweight ref via POST /git/refs, so no unsigned tag object remains in devkit's own release chain. First live proof will be the next release's tag. The consumer-scaffold half of this defect is tracked in #1378.

