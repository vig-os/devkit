"""Shape and referential-integrity tests for the ``devkit`` Claude Code plugin.

The plugin (``plugins/devkit/``) is an *operator surface*: every skill wraps a
canonical devkit verb (a ``just`` recipe or a dispatched workflow) and never
re-implements one. That only holds if the wrapper and the thing it wraps cannot
drift apart, so this module asserts the two invariants that make drift
impossible by construction:

**Version lock.** ``plugin.json``'s ``version`` equals ``DEVKIT_VERSION`` in the
repo's ``.vig-os``, and ``release.yml``'s finalize step rewrites both in the same
place. A consumer pinned to devkit ``X.Y.Z`` therefore gets the ``devkit@X.Y.Z``
skills, and a skill can never describe a verb that release does not ship.

**Referential integrity.** Every ``just <recipe>`` and every ``<name>.yml``
token that appears inside a code span or fenced block of any ``SKILL.md`` must
resolve — against devkit's own justfiles/workflows *or* the consumer scaffold's,
since the skills run in both. Deleting or renaming a recipe breaks this test
before it breaks an operator mid-release.

Extraction is deliberately narrow, following ``test_scaffold_lint``'s doctrine
("few false positives beat exhaustive coverage"): only inline code spans and
fenced code blocks are scanned, so prose such as "just merge the PR" is never
mistaken for a recipe named ``merge``. The extractors are themselves unit-tested
against constructed fixtures, so a green suite proves the rules can still fail.

Refs: #1744
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

PLUGIN_ROOT = REPO_ROOT / "plugins" / "devkit"
PLUGIN_MANIFEST = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
PLUGIN_README = PLUGIN_ROOT / "README.md"
SKILLS_DIR = PLUGIN_ROOT / "skills"

MARKETPLACE_MANIFEST = REPO_ROOT / ".claude-plugin" / "marketplace.json"

VIG_OS = REPO_ROOT / ".vig-os"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
SYNC_MANIFEST = REPO_ROOT / "scripts" / "manifest.toml"

# Justfiles whose recipes a skill may legitimately name: devkit's own (the
# reference implementation the skills are dogfooded against) and the consumer
# scaffold's (where a downstream operator runs the same verbs).
JUSTFILES = (
    "justfile",
    "justfile.gh",
    "justfile.podman",
    "justfile.worktree",
    "assets/workspace/justfile",
    "assets/workspace/justfile.local",
    "assets/workspace/justfile.project",
    "assets/workspace/.devcontainer/justfile.gh",
    "assets/workspace/.devcontainer/justfile.devc",
    "assets/workspace/.devcontainer/justfile.worktree",
)

# Workflow directories a `<name>.yml` token may resolve against, same rationale.
WORKFLOW_DIRS = (
    ".github/workflows",
    "assets/workspace/.github/workflows",
)

# The catalogue #1744 asks for. Command names are namespaced by Claude Code as
# `/<plugin>:<skill>`, so these directory names yield `/devkit:status` etc.
EXPECTED_SKILLS = frozenset(
    {
        "adopt",
        "pack-rust",
        "release-abandon",
        "release-candidate",
        "release-finalize",
        "release-hotfix",
        "release-neutral",
        "release-prepare",
        "release-promote",
        "status",
        "upgrade",
    }
)

# Skills that dispatch a mutating verb. Each must run the read-only state lookup
# before it dispatches, and none may be auto-invoked by the model: an agent must
# never infer its way into cutting a release train.
MUTATING_SKILLS = frozenset(
    {
        "release-abandon",
        "release-candidate",
        "release-finalize",
        "release-hotfix",
        "release-neutral",
        "release-prepare",
        "release-promote",
        "upgrade",
    }
)

# Every state a release skill must refuse on, and the marker that proves the
# refusal is written down. Issue numbers are the stable marker: they survive
# rewording, and they are what an operator greps for when a refusal fires.
REFUSAL_MARKERS: dict[str, tuple[str, ...]] = {
    # Another release/* in flight is the #1627 single-train refusal; a dirty
    # tree is the local pre-flight every dispatching skill owns.
    "release-prepare": ("#1627", "dirty"),
    # An RC belongs to exactly one base version; publishing one against a
    # different base is the "another RC open" foot-gun.
    "release-candidate": ("base version", "dirty"),
    # Marking the PR ready is a human act; publishing the draft is the single
    # human approval (RELEASE_CYCLE.md phase 5).
    "release-finalize": ("draft", "dirty"),
    # :latest must never move backwards (#1626); a deleted published Release
    # tombstones the tag name permanently (#1301).
    "release-promote": ("#1626", "#1301"),
    # Abandoning a *published* Release is the tombstone trap.
    "release-abandon": ("#1301", "published"),
    # Mirror of #1627, plus the trunk-mode copy-exclude path (#1625).
    "release-hotfix": ("#1627", "#1625"),
    # The merge-to-main-without-a-release lane.
    "release-neutral": ("#1676", "release-neutral"),
    # An upgrade through a dirty tree loses work; install.sh refuses too.
    "upgrade": ("dirty", "--preview"),
}

# ---------------------------------------------------------------------------- #
# Extractors
# ---------------------------------------------------------------------------- #

_FENCE_RE = re.compile(r"^```[^\n]*\n(.*?)^```", re.DOTALL | re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")

# A recipe invocation inside a code span/fence: `just` at a command position
# (line start, after a shell separator, or after whitespace) followed by a
# recipe name. Flags (`--fmt`) never match, because a name must start [a-z].
# Flags between `just` and the recipe name are skipped, so `just --show foo`
# resolves `foo` rather than silently extracting nothing.
_JUST_RE = re.compile(
    r"(?:^|[;&|(]\s*|\s)just\s+(?:--?[a-zA-Z][a-zA-Z0-9-]*\s+)*([a-z][a-z0-9_-]*)",
    re.MULTILINE,
)

# A workflow/config filename token. Both YAML spellings count: `.yml` for the
# workflows, `.yaml` for files such as `.pre-commit-config.yaml` a skill reads.
_YML_RE = re.compile(r"\b([a-z0-9][a-z0-9._-]*\.ya?ml)\b")

# A recipe definition: `name [params]:` but not the `:=` assignment form. The
# parameter list may itself carry `=` (`ref=""`), so only the `:=` that directly
# follows the name is excluded.
_RECIPE_DEF_RE = re.compile(r"^([a-zA-Z0-9_-]+)(?:\s[^\n]*?)?:(?!=)", re.MULTILINE)
_ALIAS_DEF_RE = re.compile(r"^alias\s+([a-zA-Z0-9_-]+)\s*:=", re.MULTILINE)

# A cross-reference from one skill to another.
_SKILL_REF_RE = re.compile(r"/devkit:([a-z][a-z0-9-]*)")


def code_regions(markdown: str) -> list[str]:
    """Return every fenced block body and inline code span in ``markdown``.

    Only these regions are scanned for recipe/workflow tokens; prose is exempt
    by construction rather than by suppression.
    """
    regions = [m.group(1) for m in _FENCE_RE.finditer(markdown)]
    prose = _FENCE_RE.sub("", markdown)
    regions.extend(m.group(1) for m in _INLINE_CODE_RE.finditer(prose))
    return regions


def just_recipes_referenced(markdown: str) -> set[str]:
    """Recipe names invoked as ``just <name>`` inside code regions."""
    return {
        match.group(1)
        for region in code_regions(markdown)
        for match in _JUST_RE.finditer(region)
    }


def workflows_referenced(markdown: str) -> set[str]:
    """``<name>.yml`` tokens appearing inside code regions."""
    return {
        match.group(1)
        for region in code_regions(markdown)
        for match in _YML_RE.finditer(region)
    }


def known_recipes() -> set[str]:
    """Every recipe and alias defined by devkit's and the scaffold's justfiles."""
    names: set[str] = set()
    for rel in JUSTFILES:
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        names.update(_RECIPE_DEF_RE.findall(text))
        names.update(_ALIAS_DEF_RE.findall(text))
    return names


def known_yml_targets() -> set[str]:
    """Every ``.yml`` basename a skill may legitimately name."""
    names: set[str] = set()
    for rel in WORKFLOW_DIRS:
        directory = REPO_ROOT / rel
        if directory.is_dir():
            names.update(p.name for p in directory.glob("*.yml"))
    # Repo-root config files a skill may reference by name (zizmor.yml,
    # .pre-commit-config.yaml). A leading dot is not part of the extracted
    # token, so register both spellings.
    for pattern in ("*.yml", "*.yaml", ".*.yml", ".*.yaml"):
        for path in REPO_ROOT.glob(pattern):
            names.add(path.name)
            names.add(path.name.lstrip("."))
    return names


def skill_dirs() -> list[Path]:
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir())


def skill_ids() -> list[str]:
    return [p.name for p in skill_dirs()] or ["<no-skills-found>"]


def split_frontmatter(path: Path) -> tuple[dict, str]:
    """Return ``(frontmatter, body)`` for a ``SKILL.md``."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    _, _, rest = text.partition("---\n")
    raw, sep, body = rest.partition("\n---\n")
    if not sep:
        return {}, text
    return yaml.safe_load(raw) or {}, body


def vig_os_version() -> str:
    for line in VIG_OS.read_text(encoding="utf-8").splitlines():
        if line.startswith("DEVKIT_VERSION="):
            return line.split("=", 1)[1].strip()
    raise AssertionError("DEVKIT_VERSION not found in .vig-os")


def skill_path(name: str) -> Path:
    return SKILLS_DIR / name / "SKILL.md"


# ---------------------------------------------------------------------------- #
# Plugin manifest
# ---------------------------------------------------------------------------- #


def test_plugin_manifest_exists_and_is_valid_json():
    assert PLUGIN_MANIFEST.is_file(), f"missing plugin manifest: {PLUGIN_MANIFEST}"
    json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))


def test_plugin_manifest_shape():
    """`name` is the only required key, but the discovery fields all matter.

    Claude Code namespaces every component under `name`, so it is also the
    command prefix: `/devkit:status`.
    """
    manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))

    assert manifest["name"] == "devkit"
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", manifest["name"]), (
        "plugin name must be kebab-case (claude plugin validate warns otherwise)"
    )
    for key in ("version", "description", "author", "repository", "license"):
        assert manifest.get(key), f"plugin.json is missing `{key}`"
    assert manifest["author"].get("name"), "author.name is required"


def test_plugin_manifest_declares_no_unsupported_keys():
    """Unrecognized top-level keys are silently stripped — catch them here."""
    supported = {
        "$schema",
        "name",
        "displayName",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "metadata",
        "defaultEnabled",
        "dependencies",
        "settings",
        "userConfig",
        "channels",
        "skills",
        "commands",
        "agents",
        "hooks",
        "mcpServers",
        "lspServers",
        "outputStyles",
        "workflows",
        "experimental",
    }
    manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
    unknown = set(manifest) - supported
    assert not unknown, f"plugin.json carries unsupported top-level keys: {unknown}"


def test_plugin_files_live_at_the_plugin_root_not_in_claude_plugin():
    """`.claude-plugin/` holds `plugin.json` and nothing else.

    Claude Code's manifest reference is explicit: "Put every other plugin file
    at the plugin root, not inside `.claude-plugin/`." #1744's issue body
    sketches `.claude-plugin/skills/`, which is off-spec; this pins the fix.
    """
    entries = {p.name for p in (PLUGIN_ROOT / ".claude-plugin").iterdir()}
    assert entries == {"plugin.json"}, (
        f".claude-plugin/ must hold only plugin.json, found: {sorted(entries)}"
    )
    assert SKILLS_DIR.is_dir(), "skills/ belongs at the plugin root"


def test_plugin_version_matches_pinned_devkit_version():
    """Plugin version == devkit version, so skills cannot outrun the workflows."""
    manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["version"] == vig_os_version(), (
        "plugin.json version must equal DEVKIT_VERSION in .vig-os; "
        "release.yml bumps both in its finalize step"
    )


def test_release_workflow_bumps_the_plugin_version():
    """The finalize step that rewrites `.vig-os` must rewrite `plugin.json` too.

    Without this, the version lock above holds only until the next release and
    then silently breaks on `main`.
    """
    workflow = yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    steps = [
        step
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if "Update root .vig-os to release version" in str(step.get("name", ""))
    ]
    assert steps, "release.yml no longer has the `.vig-os` version-bump step"
    script = "\n".join(str(step.get("run", "")) for step in steps)
    assert "plugins/devkit/.claude-plugin/plugin.json" in script, (
        "the finalize step must bump the plugin manifest alongside .vig-os"
    )


# ---------------------------------------------------------------------------- #
# Marketplace manifest
# ---------------------------------------------------------------------------- #


def test_marketplace_manifest_shape():
    """`name`, `owner` and `plugins` are required by the marketplace schema."""
    assert MARKETPLACE_MANIFEST.is_file(), f"missing {MARKETPLACE_MANIFEST}"
    market = json.loads(MARKETPLACE_MANIFEST.read_text(encoding="utf-8"))

    assert market["name"]
    assert not set(market["name"]) & set("/\\ "), (
        "marketplace name may not contain / \\ or spaces"
    )
    assert market["owner"]["name"]
    assert isinstance(market["plugins"], list) and market["plugins"]


def test_marketplace_entry_points_at_the_plugin():
    """The entry uses a relative-path source, which must resolve in-repo."""
    market = json.loads(MARKETPLACE_MANIFEST.read_text(encoding="utf-8"))
    entries = {entry["name"]: entry for entry in market["plugins"]}

    assert "devkit" in entries, "the marketplace must list the devkit plugin"
    source = entries["devkit"]["source"]
    assert isinstance(source, str) and source.startswith("./"), (
        "a relative-path plugin source must start with './'"
    )
    assert ".." not in source, "a relative source containing '..' fails validation"
    assert (REPO_ROOT / source).is_dir(), (
        f"marketplace source does not resolve: {source}"
    )
    assert (REPO_ROOT / source) == PLUGIN_ROOT


def test_marketplace_entry_does_not_duplicate_the_plugin_version():
    """`plugin.json` wins over an entry `version`; declaring both warns."""
    market = json.loads(MARKETPLACE_MANIFEST.read_text(encoding="utf-8"))
    entry = next(e for e in market["plugins"] if e["name"] == "devkit")
    assert "version" not in entry, (
        "leave `version` to plugin.json — an entry version is shadowed and warns"
    )


# ---------------------------------------------------------------------------- #
# Skill catalogue and frontmatter
# ---------------------------------------------------------------------------- #


def test_skill_catalogue_matches_the_issue():
    assert {p.name for p in skill_dirs()} == set(EXPECTED_SKILLS)


@pytest.mark.parametrize("skill", skill_ids())
def test_skill_has_a_skill_md(skill):
    assert skill_path(skill).is_file(), f"{skill} has no SKILL.md"


@pytest.mark.parametrize("skill", skill_ids())
def test_skill_frontmatter(skill):
    front, body = split_frontmatter(skill_path(skill))

    assert front, f"{skill}: SKILL.md must open with YAML frontmatter"
    assert front["name"] == skill, (
        f"{skill}: frontmatter name `{front.get('name')}` must match the directory"
    )
    description = front.get("description", "")
    assert description, f"{skill}: a description is required for discovery"
    assert len(description) + len(front.get("when_to_use", "")) <= 1536, (
        f"{skill}: description + when_to_use exceeds the 1536-character limit"
    )
    assert body.strip(), f"{skill}: SKILL.md has no body"


@pytest.mark.parametrize("skill", sorted(MUTATING_SKILLS))
def test_mutating_skills_are_not_model_invocable(skill):
    """An agent must not infer its way into dispatching a release verb."""
    front, _ = split_frontmatter(skill_path(skill))
    assert front.get("disable-model-invocation") is True, (
        f"{skill} dispatches a mutating verb and must set disable-model-invocation: true"
    )


def test_read_only_skills_stay_model_invocable():
    """`status` is the lookup every other skill delegates to — keep it reachable."""
    front, _ = split_frontmatter(skill_path("status"))
    assert not front.get("disable-model-invocation", False)


# ---------------------------------------------------------------------------- #
# Referential integrity — the drift gate
# ---------------------------------------------------------------------------- #


@pytest.mark.parametrize("skill", skill_ids())
def test_skill_just_recipes_exist(skill):
    """A skill may only name a `just` recipe devkit or the scaffold ships."""
    referenced = just_recipes_referenced(skill_path(skill).read_text(encoding="utf-8"))
    missing = sorted(referenced - known_recipes())
    assert not missing, (
        f"{skill}: references non-existent just recipe(s): {missing}. "
        "Skills wrap canonical verbs — add the recipe or fix the reference."
    )


@pytest.mark.parametrize("skill", skill_ids())
def test_skill_workflow_references_exist(skill):
    """A skill may only name a workflow devkit or the scaffold ships."""
    referenced = workflows_referenced(skill_path(skill).read_text(encoding="utf-8"))
    missing = sorted(referenced - known_yml_targets())
    assert not missing, f"{skill}: references non-existent workflow file(s): {missing}"


def test_readme_references_resolve_too():
    """The README lists every command, so its tokens are load-bearing as well."""
    text = PLUGIN_README.read_text(encoding="utf-8")
    assert not sorted(just_recipes_referenced(text) - known_recipes())
    assert not sorted(workflows_referenced(text) - known_yml_targets())


@pytest.mark.parametrize("skill", skill_ids())
def test_skill_cross_references_resolve(skill):
    """`/devkit:<name>` handoffs must name a skill that ships."""
    text = skill_path(skill).read_text(encoding="utf-8")
    referenced = set(_SKILL_REF_RE.findall(text))
    missing = sorted(referenced - EXPECTED_SKILLS)
    assert not missing, f"{skill}: handoff to unknown skill(s): {missing}"


def test_readme_lists_every_command():
    text = PLUGIN_README.read_text(encoding="utf-8")
    for skill in sorted(EXPECTED_SKILLS):
        assert f"/devkit:{skill}" in text, f"README does not list /devkit:{skill}"


# ---------------------------------------------------------------------------- #
# State-lookup-first and refusal coverage
# ---------------------------------------------------------------------------- #

_DISPATCH_RE = re.compile(
    r"just\s+(?:prepare|publish|finalize|promote|abandon)[a-z-]*|gh workflow run|install\.sh"
)


_SECTION_RE = re.compile(r"^## (\d+)\.\s*(.+)$", re.MULTILINE)


@pytest.mark.parametrize("skill", sorted(MUTATING_SKILLS))
def test_mutating_skill_step_one_is_the_state_lookup(skill):
    """Principle 1, structurally: section 1 *is* the lookup, not merely near it.

    Comparing text offsets only proved the words appeared in some order. This
    asserts the shape an operator actually reads: the first numbered section is
    the state lookup, and that section delegates to `/devkit:status`.
    """
    text = skill_path(skill).read_text(encoding="utf-8")
    sections = _SECTION_RE.findall(text)

    assert sections, f"{skill}: has no numbered `## N. Title` sections"
    number, title = sections[0]
    assert number == "1", f"{skill}: first numbered section is {number}, expected 1"
    assert "state lookup" in title.lower(), (
        f"{skill}: section 1 is {title!r}, expected the state lookup"
    )

    body_start = text.index(f"## {number}. {title}")
    body_end = (
        text.index(f"## {sections[1][0]}. {sections[1][1]}")
        if len(sections) > 1
        else len(text)
    )
    assert "/devkit:status" in text[body_start:body_end], (
        f"{skill}: section 1 does not delegate to /devkit:status"
    )


@pytest.mark.parametrize("skill", sorted(MUTATING_SKILLS))
def test_mutating_skill_does_not_dispatch_before_the_lookup(skill):
    """Principle 1: no mutation without a fresh state read in the same run."""
    text = skill_path(skill).read_text(encoding="utf-8")

    lookup = text.find("/devkit:status")
    assert lookup != -1, f"{skill}: must delegate its step 1 to /devkit:status"

    dispatch = _DISPATCH_RE.search(text)
    assert dispatch is not None, (
        f"{skill}: dispatches nothing — expected a canonical verb"
    )
    assert lookup < dispatch.start(), (
        f"{skill}: dispatches at offset {dispatch.start()} before the "
        f"/devkit:status lookup at {lookup}"
    )


@pytest.mark.parametrize(("skill", "markers"), sorted(REFUSAL_MARKERS.items()))
def test_skill_documents_its_refusals(skill, markers):
    """Every foot-gun named in #1744's acceptance criteria is written down."""
    text = skill_path(skill).read_text(encoding="utf-8").lower()
    missing = [marker for marker in markers if marker.lower() not in text]
    assert not missing, f"{skill}: refusal(s) not documented: {missing}"


@pytest.mark.parametrize("skill", sorted(MUTATING_SKILLS | {"adopt"}))
def test_skill_has_a_refusal_section(skill):
    text = skill_path(skill).read_text(encoding="utf-8")
    assert re.search(r"^#{2,3} (?:\d+\.\s*)?Refuse\b", text, re.MULTILINE), (
        f"{skill}: needs an explicit refusal section listing the states it declines"
    )


def test_status_reports_every_axis_the_issue_requires():
    """The acceptance criteria enumerate what `/devkit:status` must report."""
    text = skill_path("status").read_text(encoding="utf-8").lower()
    for axis in (
        "devkit_version",
        "drift",
        "release pr",
        "pre-release",
        "promote",
        "hotfix",
        "devkit_workflow",
        "legacy",
        "release_app_client_id",
        "commit_app_client_id",
    ):
        assert axis in text, f"/devkit:status does not report `{axis}`"


def test_status_does_not_hardcode_the_rc_pre_release_label():
    """#1746 makes the pre-release format configurable — do not bake in `-rc`."""
    text = skill_path("status").read_text(encoding="utf-8")
    assert "DEVKIT_PRERELEASE_FORMAT" in text or "pre-release format" in text.lower(), (
        "status must treat a pre-release as `-<label>`, not assume `-rc*` (#1746)"
    )


def test_adopt_is_proposal_only():
    text = skill_path("adopt").read_text(encoding="utf-8").lower()
    assert "never" in text and "install.sh" in text
    for collision in ("release-plz", "cargo-dist"):
        assert collision in text, f"adopt must flag the {collision} collision"


def test_pack_rust_is_scoped_to_what_devkit_ships_today():
    """The pending seams are named by issue, in prose — never as live tokens."""
    text = skill_path("pack-rust").read_text(encoding="utf-8")
    assert "#1496" in text, "pack-rust must cite the Rust pack issue"
    assert "#1746" in text, "pack-rust must cite the release-extension issue"


# ---------------------------------------------------------------------------- #
# Distribution
# ---------------------------------------------------------------------------- #


def test_plugin_is_not_vendored_into_the_consumer_scaffold():
    """Consumers install from the marketplace; vendoring is the drift #927 retires."""
    manifest = SYNC_MANIFEST.read_text(encoding="utf-8")
    assert "plugins/devkit" not in manifest, (
        "the plugin must not be synced into assets/workspace/ — it is distributed "
        "through the marketplace, not copied per repo (#927)"
    )
    assert not (REPO_ROOT / "assets" / "workspace" / "plugins").exists()


# ---------------------------------------------------------------------------- #
# Extractor unit tests — proof the rules above can still fail
# ---------------------------------------------------------------------------- #


def test_just_extractor_finds_recipes_only_in_code_regions():
    markdown = (
        "Prose saying just merge the PR must not match.\n\n"
        "Run `just prepare-release 1.2.3` first.\n\n"
        "```bash\njust promote-release 1.2.3\ncd x && just finalize-release 1.2.3\n```\n"
    )
    assert just_recipes_referenced(markdown) == {
        "prepare-release",
        "promote-release",
        "finalize-release",
    }


def test_just_extractor_flags_an_unknown_recipe():
    """The gate this module exists for: a renamed recipe fails the suite."""
    markdown = "```bash\njust prepare-release 1.2.3\njust totally-made-up-verb\n```\n"
    referenced = just_recipes_referenced(markdown)
    assert "prepare-release" in referenced
    assert sorted(referenced - known_recipes()) == ["totally-made-up-verb"]


def test_yml_extractor_flags_an_unknown_workflow():
    markdown = (
        "Dispatch `gh workflow run promote-release.yml` then `does-not-exist.yml`.\n"
    )
    referenced = workflows_referenced(markdown)
    assert "promote-release.yml" in referenced
    assert sorted(referenced - known_yml_targets()) == ["does-not-exist.yml"]


def test_recipe_definitions_are_parsed_not_assignments():
    recipes = known_recipes()
    # Real recipes across both trees.
    assert {
        "prepare-release",
        "promote-release",
        "abandon-release",
        "doctor",
    } <= recipes
    # `repo := env(...)` in justfile is an assignment, not a recipe.
    assert "repo" not in recipes
    # Aliases are callable and therefore known.
    assert "gh-i" in recipes


# ---------------------------------------------------------------------------- #
# Safety and correctness of what a skill tells the operator to run
# ---------------------------------------------------------------------------- #

# Skills that take an X.Y.Z argument and feed it to a shell command. Each must
# validate it before use: the recipes interpolate the value straight into bash.
VERSION_ARG_SKILLS = frozenset(
    {
        # `adopt` and `status` belong here even though no operator types their
        # version: both read it out of the INSPECTED repo's `.vig-os` and
        # interpolate it into an installer URL, which is a worse source than a
        # typed argument, not a better one.
        "adopt",
        "release-abandon",
        "release-candidate",
        "release-finalize",
        "release-hotfix",
        "release-prepare",
        "release-promote",
        "status",
        "upgrade",
    }
)

_SEMVER_GUARD_RE = re.compile(r"\^\[0-9\]\+\\?\.\[0-9\]\+\\?\.\[0-9\]\+\$")


@pytest.mark.parametrize("skill", skill_ids())
def test_no_skill_runs_a_repo_local_installer(skill):
    """`./install.sh` is the *target* repo's script, or absent.

    `/devkit:adopt` and `/devkit:status` run against arbitrary repositories, and
    a consumer never ships devkit's installer. Executing `./install.sh` there is
    either a no-op or running someone else's script; both are wrong, and the
    second is arbitrary code execution from a model-invocable skill. Fetch
    devkit's installer at a pinned tag instead.
    """
    text = skill_path(skill).read_text(encoding="utf-8")
    assert "./install.sh" not in text, (
        f"{skill}: runs a repo-local ./install.sh — fetch devkit's installer at a "
        "pinned tag instead"
    )


_INSTALLER_FETCH_RE = re.compile(
    r"raw\.githubusercontent\.com/vig-os/devkit/(\S*?)/install\.sh"
)


@pytest.mark.parametrize("skill", skill_ids())
def test_every_installer_fetch_is_guarded_in_its_own_block(skill):
    """A semver guard must precede every installer fetch, in the same block.

    A blacklist of `main`/`dev`/`HEAD` is not enough, and neither is a guard
    somewhere earlier in the file. The ref is interpolated into a URL path and
    piped to `bash`, and curl collapses `..` before it sends the request, so
    `DEVKIT_VERSION=../../attacker/repo/refs/heads/main` in the *inspected*
    repo's manifest fetches and executes that repository's script instead --
    verified against raw.githubusercontent.com, which serves the collapsed path
    with HTTP 200 for an arbitrary owner. The guard has to be local to the
    snippet an operator copies, and it has to come first.
    """
    text = skill_path(skill).read_text(encoding="utf-8")

    for block in _FENCE_RE.findall(text):
        fetch = _INSTALLER_FETCH_RE.search(block)
        if fetch is None:
            continue
        guard = _SEMVER_GUARD_RE.search(block)
        assert guard is not None, (
            f"{skill}: a code block fetches install.sh with no "
            "^[0-9]+\\.[0-9]+\\.[0-9]+$ guard in the same block"
        )
        assert guard.start() < fetch.start(), (
            f"{skill}: the version guard comes after the installer fetch in the "
            "same block; it has to run first or it guards nothing"
        )


@pytest.mark.parametrize("skill", skill_ids())
def test_installer_fetches_resolve_a_tag_explicitly(skill):
    """`refs/tags/<v>` so a same-named branch cannot shadow the tag."""
    text = skill_path(skill).read_text(encoding="utf-8")
    for match in _INSTALLER_FETCH_RE.finditer(text):
        ref = match.group(1)
        assert ref.startswith("refs/tags/"), (
            f"{skill}: fetches install.sh from `{ref}`; use refs/tags/<version> so a "
            "branch of the same name cannot shadow the tag"
        )


@pytest.mark.parametrize("skill", skill_ids())
def test_no_skill_hardcodes_the_devkit_release_series(skill):
    """A consumer's release series is its own, not devkit's.

    The floating-tag monotonicity check compares against the *current* repo's
    published releases. Hard-coding devkit's would compare a consumer against
    the wrong series and either block a valid promote or wave a regression
    through.
    """
    text = skill_path(skill).read_text(encoding="utf-8")
    assert "repos/vig-os/devkit/releases" not in text, (
        f"{skill}: hard-codes devkit's release series — use repos/{{owner}}/{{repo}}"
    )


@pytest.mark.parametrize("skill", sorted(VERSION_ARG_SKILLS))
def test_version_arguments_are_validated_before_use(skill):
    """The recipes interpolate the version straight into bash — validate it."""
    text = skill_path(skill).read_text(encoding="utf-8")
    assert _SEMVER_GUARD_RE.search(text), (
        f"{skill}: takes a version argument but never validates it against "
        "^[0-9]+\\.[0-9]+\\.[0-9]+$ before passing it to a shell command"
    )


def test_status_compares_the_plugin_version_against_the_pin():
    """The version lock is a property of a tag, not of an install.

    An unpinned marketplace tracks the default branch, so a consumer can be
    running newer skills than their pinned scaffold. `/devkit:status` has to
    detect that rather than let the plugin assume it cannot happen.
    """
    text = skill_path("status").read_text(encoding="utf-8")
    assert "CLAUDE_PLUGIN_ROOT" in text, (
        "status must read the running plugin's own manifest to know its version"
    )
    lowered = text.lower()
    assert "plugin version" in lowered
    assert "mismatch" in lowered or "differs" in lowered


def test_readme_documents_ref_pinned_installation():
    """`owner/repo@ref` is what actually pins a marketplace to a version."""
    text = PLUGIN_README.read_text(encoding="utf-8")
    assert "vig-os/devkit@" in text, (
        "README must document the tag-pinned marketplace form, which is the only "
        "thing that makes a consumer's skills match their DEVKIT_VERSION"
    )


def test_readme_does_not_overclaim_the_version_lock():
    """State the guarantee the mechanism actually provides, and its condition."""
    text = PLUGIN_README.read_text(encoding="utf-8")
    assert "impossible by construction" not in text, (
        "the lock guarantees a tag carries matching skills; it does not make an "
        "unpinned install match the consumer's pin"
    )
    assert "default branch" in text, (
        "README must say what an unpinned marketplace tracks"
    )


def test_release_workflow_verifies_the_plugin_version_bump():
    """A `sed` that matches nothing is silent — the tag would ship a stale version."""
    workflow = yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    script = "\n".join(
        str(step.get("run", ""))
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if "Update root .vig-os to release version" in str(step.get("name", ""))
    )
    assert "jq -e" in script, (
        "the finalize step must verify the plugin version actually changed; a "
        "non-matching sed otherwise ships a stale plugin.json under the final tag"
    )


def test_readme_sparse_add_passes_paths():
    """`--sparse <paths...>` takes directories; a bare flag checks out nothing useful."""
    text = PLUGIN_README.read_text(encoding="utf-8")
    invocations = [
        match.group("rest").strip()
        # Actual `marketplace add` command lines only; prose and inline code
        # spans may name the bare flag when describing what it does.
        for region in code_regions(text)
        if "marketplace add" in region
        for match in re.finditer(r"--sparse(?P<rest>[^\n]*)", region)
    ]
    assert invocations, "README must show the sparse form"
    for rest in invocations:
        assert ".claude-plugin" in rest and "plugins" in rest, (
            f"--sparse must name the marketplace and plugin directories, got {rest!r}"
        )


@pytest.mark.parametrize("skill", ["status", "upgrade"])
def test_reref_instructions_remove_before_adding(skill):
    """A repeat `marketplace add` is a no-op: `already on disk`, exit 0.

    Telling an operator to re-add at the new tag therefore changes nothing, and
    `marketplace update` refreshes the *same* ref rather than moving it. Only
    remove-then-add repoints a marketplace at a new version.
    """
    text = skill_path(skill).read_text(encoding="utf-8")
    assert "marketplace remove" in text, (
        f"{skill}: tells the operator to re-add a marketplace without removing it "
        "first, which is a silent no-op"
    )


# ---------------------------------------------------------------------------- #
# The guards have to actually guard
# ---------------------------------------------------------------------------- #

# Variables a snippet defines for itself. Shell state does not survive between
# commands, so a block that reads one of these must also assign it.
SELF_CONTAINED_VARS = ("VERSION", "PINNED", "BRANCH", "RUN_ID", "TITLE", "ISSUE")

# How far past the guard to look for the abort. The guard is either a one-line
# `|| { echo …; exit 1; }` or the same spread over a short brace block.
_GUARD_WINDOW = 240


def guard_aborts(block: str) -> bool:
    """Does every semver guard in ``block`` actually abort when it fails?

    Matching the regex text alone proves nothing: a guard whose failure branch
    runs `true` reads exactly the same to a text search and lets an unvalidated
    value straight through to the command underneath.
    """
    matches = list(_SEMVER_GUARD_RE.finditer(block))
    if not matches:
        return False
    return all(
        re.search(r"\b(exit|return)\b", block[m.end() : m.end() + _GUARD_WINDOW])
        for m in matches
    )


@pytest.mark.parametrize("skill", skill_ids())
def test_every_installer_fetch_guard_aborts(skill):
    """A guard that does not abort is decoration."""
    text = skill_path(skill).read_text(encoding="utf-8")
    for block in _FENCE_RE.findall(text):
        if _INSTALLER_FETCH_RE.search(block) is None:
            continue
        assert guard_aborts(block), (
            f"{skill}: a block fetching install.sh has a semver guard whose failure "
            "branch does not exit/return, so an invalid version reaches the fetch"
        )


def test_guard_abort_check_rejects_a_non_aborting_guard():
    """Mutation test: the check above must fail when the abort is removed."""
    aborting = (
        "VERSION=1.2.3\n"
        '[[ "$VERSION" =~ ^[0-9]+\\.[0-9]+\\.[0-9]+$ ]] || { echo "refusing"; exit 1; }\n'
        'curl -fsSL "https://raw.githubusercontent.com/vig-os/devkit/'
        'refs/tags/${VERSION}/install.sh" | bash\n'
    )
    assert guard_aborts(aborting)

    # The only change: `exit 1` becomes `true`. The regex text is identical.
    neutered = aborting.replace("exit 1", "true")
    assert _SEMVER_GUARD_RE.search(neutered), "the mutation must keep the regex text"
    assert not guard_aborts(neutered), (
        "a guard whose failure branch does not abort must be rejected"
    )


@pytest.mark.parametrize("skill", skill_ids())
def test_bash_blocks_are_self_contained(skill):
    """Shell state does not persist between commands an operator runs.

    A block that reads `$VERSION` without assigning it expands to the empty
    string and produces a confident, wrong answer — or, next to a guard, skips
    the value the guard was meant to check.
    """
    text = skill_path(skill).read_text(encoding="utf-8")
    for block in re.findall(
        r"^```bash[^\n]*\n(.*?)^```", text, re.DOTALL | re.MULTILINE
    ):
        for var in SELF_CONTAINED_VARS:
            if not re.search(rf"\$\{{?{var}\b", block):
                continue
            assert re.search(rf"^\s*{var}=", block, re.MULTILINE), (
                f"{skill}: a bash block reads ${var} without assigning it; shell "
                "state does not survive between commands"
            )


def test_release_neutral_title_cannot_execute():
    """The PR title is issue-sourced free text, so it must never be expanded.

    `TITLE="…"` runs `$(…)` and backticks at assignment time. A quoted heredoc
    (`<<'EOF'`) is the form that keeps the text literal.
    """
    text = skill_path("release-neutral").read_text(encoding="utf-8")
    blocks = re.findall(r"^```bash[^\n]*\n(.*?)^```", text, re.DOTALL | re.MULTILINE)
    runnable = "\n".join(blocks)

    # Command lines only: the prose names the unsafe form on purpose, to say
    # why it is unsafe. What matters is what an operator copies and runs.
    assert 'TITLE="' not in runnable, (
        "a double-quoted TITLE executes command substitution in issue-sourced text"
    )
    assert "<<'" in runnable, "use a quoted heredoc so the title stays literal"
