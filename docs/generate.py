#!/usr/bin/env python3
"""Generate documentation from narrative sources, requirements.yaml, skills, and just help output.

This script implements "docs as code" by generating documentation from:
- Narrative markdown files (docs/narrative/)
- Requirements definitions (scripts/requirements.yaml)
- Agent skill definitions (.cursor/skills/*/SKILL.md frontmatter)
- Just recipe help output (just --list)

Single source of truth principle: All dependency information comes from requirements.yaml,
all skill metadata comes from SKILL.md frontmatter.
"""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import jinja2
import yaml


def get_just_help() -> str:
    """Extract just --list output."""
    try:
        result = subprocess.run(
            ["just", "--list"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error: Could not get just help: {e}", file=sys.stderr)
        sys.exit(1)


def get_version_from_changelog() -> str:
    """Extract version from CHANGELOG.md."""
    changelog = Path(__file__).parent.parent / "CHANGELOG.md"
    if changelog.exists():
        with changelog.open() as f:
            for line in f:
                # Skip unreleased headings (e.g., "TBD") and use latest dated release.
                if line.startswith("## [") and re.search(r"\d{4}-\d{2}-\d{2}", line):
                    version = line.split("[")[1].split("]")[0]
                    return version
    return "dev"


def get_release_date_from_changelog() -> str:
    """Extract release date from CHANGELOG.md."""
    changelog = Path(__file__).parent.parent / "CHANGELOG.md"
    if changelog.exists():
        with changelog.open() as f:
            for line in f:
                if line.startswith("## ["):
                    match = re.search(r"\d{4}-\d{2}-\d{2}", line)
                    if match:
                        return match.group()
    return datetime.now().isoformat(timespec="seconds")


def load_requirements() -> dict:
    """Load requirements from requirements.yaml.

    Returns a dictionary with:
    - dependencies: List of required dependencies
    - optional: List of optional dependencies
    """
    requirements_file = Path(__file__).parent.parent / "scripts" / "requirements.yaml"

    if not requirements_file.exists():
        print(
            f"Warning: Requirements file not found: {requirements_file}",
            file=sys.stderr,
        )
        return {"dependencies": [], "optional": [], "auto_install": []}

    with requirements_file.open() as f:
        data = yaml.safe_load(f)

    return {
        "dependencies": data.get("dependencies", []),
        "optional": data.get("optional", []),
    }


SKILL_GROUP_ORDER = [
    ("inception", "Inception (Project Bootstrap)"),
    ("issue", "Issue Management"),
    ("design", "Design (Interactive)"),
    ("code", "Code (Interactive)"),
    ("git", "Git & PR (Interactive)"),
    ("pr", "Git & PR (Interactive)"),
    ("ci", "CI"),
    ("solve-and-pr", "Autonomous Launcher"),
    ("worktree", "Autonomous Worktree Pipeline"),
]

SKILL_GROUP_INTROS = {
    "inception": (
        "Run when starting a new repo or major initiative. "
        "Explores the problem space, scopes boundaries, validates architecture, "
        "and decomposes the result into actionable issues."
    ),
    "solve-and-pr": (
        "Interactive entry point to kick off autonomous work. "
        "Launches a worktree where the agent runs design → plan → execute → verify → PR → CI "
        "with no further human interaction. All progress is posted as issue comments."
    ),
    "worktree": (
        "These are non-blocking counterparts of the interactive skills. "
        "They run in a git worktree with no user prompts — designed for "
        "`just worktree-start <issue>`. "
        "**Do not invoke these directly in your editor session.** "
        "They only work inside a worktree environment launched via `just`."
    ),
}


def load_skills() -> list[dict]:
    """Scan .cursor/skills/*/SKILL.md and return parsed skill metadata.

    Each entry has: name, trigger, description, group (prefix before underscore).
    """
    skills_dir = Path(__file__).parent.parent / ".cursor" / "skills"
    skills = []

    if not skills_dir.is_dir():
        print(f"Warning: Skills directory not found: {skills_dir}", file=sys.stderr)
        return skills

    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        text = skill_file.read_text()
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        meta = yaml.safe_load(parts[1])
        if not meta or "name" not in meta:
            continue

        name = meta["name"]
        skills.append(
            {
                "name": name,
                "trigger": "/" + name.replace("_", "-"),
                "description": meta.get("description", ""),
                "group": name.split("_")[0],
            }
        )

    return skills


def group_skills(skills: list[dict]) -> list[dict]:
    """Organize skills into ordered groups for the template."""
    seen_headings: dict[str, dict] = {}
    groups: list[dict] = []

    for prefix, heading in SKILL_GROUP_ORDER:
        if heading in seen_headings:
            seen_headings[heading]["prefixes"].add(prefix)
            continue
        group = {
            "heading": heading,
            "intro": SKILL_GROUP_INTROS.get(prefix, ""),
            "prefixes": {prefix},
            "skills": [],
        }
        seen_headings[heading] = group
        groups.append(group)

    for skill in skills:
        for group in groups:
            if skill["group"] in group["prefixes"]:
                group["skills"].append(skill)
                break

    # Drop the internal prefixes set before returning
    for group in groups:
        del group["prefixes"]

    return [g for g in groups if g["skills"]]


def format_requirements_table(requirements: dict) -> str:
    """Generate markdown table from requirements data."""
    lines = [
        "| Component            | Version | Purpose |",
        "|----------------------|---------|---------|",
    ]

    # Required dependencies (manual install)
    for dep in requirements["dependencies"]:
        name = dep.get("name", "unknown")
        version = dep.get("version", "latest")
        purpose = dep.get("purpose", "")
        lines.append(f"| **{name}** | {version} | {purpose} |")

    return "\n".join(lines)


def format_install_commands(requirements: dict, os_type: str) -> str:
    """Generate installation command for a specific OS."""
    deps = requirements["dependencies"]
    install_field = {
        "macos": "macos",
        "debian": "debian",
        "fedora": "fedora",
    }.get(os_type, "debian")

    # Collect package names for package manager installs
    brew_packages = []
    apt_packages = []
    other_commands = []

    for dep in deps:
        install_info = dep.get("install", {})
        cmd = install_info.get(install_field, "")

        if not cmd:
            continue

        # Parse common package manager patterns
        if os_type == "macos" and cmd.startswith("brew install "):
            brew_packages.append(cmd.replace("brew install ", "").strip())
        elif os_type == "debian" and cmd.startswith("sudo apt install -y "):
            apt_packages.append(cmd.replace("sudo apt install -y ", "").strip())
        elif "|" in cmd or "\n" in cmd:
            # Multi-line or piped commands - keep separate
            other_commands.append(f"# {dep.get('name', 'unknown')}\n{cmd}")
        else:
            other_commands.append(cmd)

    result = []

    if os_type == "macos" and brew_packages:
        result.append(f"brew install {' '.join(brew_packages)}")
    elif os_type == "debian" and apt_packages:
        result.append("sudo apt update")
        result.append(f"sudo apt install -y {' '.join(apt_packages)}")

    result.extend(other_commands)

    return "\n".join(result)


def generate_docs() -> bool:
    """Generate documentation from templates."""
    docs_dir = Path(__file__).parent
    root_dir = docs_dir.parent

    # Load requirements
    requirements = load_requirements()

    # Set up Jinja2 environment
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(docs_dir / "templates"),
        keep_trailing_newline=True,
    )

    # Register helper for including narrative files
    def include_narrative(filename: str) -> str:
        """Include a narrative markdown file, stripping front-matter if present."""
        narrative_file = docs_dir / "narrative" / filename
        if narrative_file.exists():
            content = narrative_file.read_text()
            # Strip YAML front-matter if present
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2]
            return content.strip()
        return f"<!-- Missing: {filename} -->"

    env.globals["include_narrative"] = include_narrative

    # Load skills
    skills = load_skills()

    # Context for templates
    context = {
        "project_name": "vigOS Development Environment",
        "just_help_output": get_just_help(),
        "version": get_version_from_changelog(),
        "release_date": get_release_date_from_changelog(),
        "release_url": f"https://github.com/vig-os/devcontainer/releases/tag/{get_version_from_changelog()}",
        # Requirements data
        "requirements": requirements,
        "requirements_table": format_requirements_table(requirements),
        "install_macos": format_install_commands(requirements, "macos"),
        "install_debian": format_install_commands(requirements, "debian"),
        # Skill data
        "skill_groups": group_skills(skills),
    }

    # Generate each template
    templates_to_generate = [
        ("README.md.j2", "README.md"),
        ("CONTRIBUTE.md.j2", "CONTRIBUTE.md"),
        ("TESTING.md.j2", "TESTING.md"),
        ("SKILL_PIPELINE.md.j2", "docs/SKILL_PIPELINE.md"),
    ]

    generated_count = 0
    for template_name, output_name in templates_to_generate:
        template_path = docs_dir / "templates" / template_name
        if not template_path.exists():
            print(f"Skipping {template_name} (template not found)", file=sys.stderr)
            continue

        try:
            template = env.get_template(template_name)
            output = template.render(**context)

            output_path = root_dir / output_name
            output_path.write_text(output)
            print(f"Generated: {output_name}")
            generated_count += 1
        except Exception as e:
            print(f"Error generating {output_name}: {e}", file=sys.stderr)
            return False

    print(f"\n✓ Generated {generated_count} documentation files")
    return True


if __name__ == "__main__":
    success = generate_docs()
    sys.exit(0 if success else 1)
