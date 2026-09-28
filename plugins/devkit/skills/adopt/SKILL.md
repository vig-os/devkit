---
name: adopt
description: >-
  Propose vigOS devkit adoption for a repository that does not have it yet: inspect the languages, the existing CI,
  the existing release tooling, the existing Nix and pre-commit setup, map them onto devkit's scaffold, packs and
  workflow models, and hand back the exact installer invocation, the resulting .vig-os manifest, the concrete diff
  and the conflicts. Proposal only — it never writes a file. Use when asked whether or how a repo should adopt
  devkit.
---

# devkit adopt

A read-only proposal. This skill inspects a repository, works out what adopting devkit would mean for it, and hands
the operator a decision. It **never** applies anything: no file is written, no branch is created, no installer is
run. The deliverable is the exact command line plus the list of things that will collide.

## 1. State lookup

```bash
test -f .vig-os && echo "already scaffolded" || echo "not scaffolded"
```

If the repo **is** already scaffolded, this is the wrong skill: run `/devkit:status` and then `/devkit:upgrade`.

## 2. Inspect

Read the repo. Never guess a fact you can check.

```bash
git remote get-url origin
git branch -r --list 'origin/dev' 'origin/main'
ls .github/workflows/ 2>/dev/null
ls .claude/ 2>/dev/null
cat .pre-commit-config.yaml 2>/dev/null | head -40
ls flake.nix flake.lock Cargo.toml pyproject.toml package.json go.mod 2>/dev/null
```

Record, as facts with evidence:

- **Languages present** — by manifest file and by source glob, not by reputation.
- **Existing CI** — what each workflow under `.github/workflows/` actually does, and which lanes devkit would
  duplicate.
- **Existing release tooling** — release-plz, release-please, cargo-dist, semantic-release, goreleaser, changesets.
  This is the field that most often decides whether adoption is one step or a migration.
- **Existing Nix** — a `flake.nix` already present is preserved, not replaced.
- **Existing `.claude/`** — devkit ships a skill payload; say what would be added beside what is there.
- **Branch topology** — `dev` and `main`, or `main` only. This picks the workflow model.

## 3. Map onto devkit

Propose, with the reason for each choice:

| Decision | Options | How to choose |
|---|---|---|
| `--mode` | `devcontainer`, `direnv`, `both`, `bare` | How the team actually develops; `direnv` for a Nix-native repo, `both` when some contributors need a container |
| `--workflow` | `gitflow` (default), `trunk` | The branch topology you just read. `gitflow` needs `dev` **and** `main`; `trunk` is `main` only |
| `--version` | a release tag | Always an explicit tag, never an implicit latest, so the proposal is reproducible |
| `--org`, `--name`, `--repo` | strings | Read them from the remote rather than asking |
| Release feature group | on / off | A repo that will not run the train should disable it rather than carry dead workflows |

Then write out the `.vig-os` manifest the installer would produce, key by key, and the file-level diff:

```bash
./install.sh --preview --version 1.17.0 --mode direnv --workflow gitflow .
```

`--preview` is the non-mutating form: it prints the add/overwrite/preserve/delete report and exits.

## 4. Refuse — and flag the collisions

Never run the installer from this skill, never with `--force`, and never on a dirty tree. Adoption is a change the
operator makes deliberately, on a branch they created, after reading the diff.

Flag every one of these explicitly, because each one is a silent breakage rather than an error:

| Collision | What happens |
|---|---|
| **release-plz** present | It wants to own version, tag, changelog and PR — the same four things devkit's train owns. The two cannot both run; adoption means migrating off it, not adding beside it |
| **cargo-dist** present | Its default `announce` / `host` steps create the GitHub Release, and so does devkit's publish step. Set `create-release = false` and let cargo-dist host into the draft the train owns; otherwise the Release is published before the train can attach anything to it |
| **semantic-release / release-please / changesets** | Same ownership conflict as release-plz, on the changelog and version axes |
| An existing `flake.nix` | Preserved, not replaced — so devkit's dev shell is **not** what you get until it is merged by hand |
| An existing `.gitignore` | Devkit appends managed fragments; a conflicting hand-written rule stays and wins |
| An existing CodeQL workflow | Duplicate analysis matrices race on the same alerts |
| An existing `.pre-commit-config.yaml` | It is a preserved file: your version survives, and devkit's hooks are **not** added |
| No `dev` branch, gitflow chosen | Every workflow targets a branch that does not exist |

## 5. Hand back

End with exactly three things:

1. the single installer command line to run, with every flag resolved to a literal value;
2. the follow-up checklist — create the branch, run it, read the diff, provision `RELEASE_APP_*` and
   `COMMIT_APP_*` if the train is wanted, decide each collision above;
3. what adoption does **not** give them, so the scope is honest: an existing `flake.nix` and
   `.pre-commit-config.yaml` are preserved, and the release train is opt-in.

For a Rust repo, follow up with `/devkit:pack-rust`. After the installer has run, `/devkit:status` is the check
that it landed.
