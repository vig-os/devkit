"""Reconcile module-owned hook blocks without rewriting consumer YAML (#1994)."""

import base64
import json
import re
import sys
from pathlib import Path

import yaml

MARKER = "devkit:docs"
FIXERS = {"trailing-whitespace", "end-of-file-fixer", "mixed-line-ending"}


def restore(text):
    """Remove owned additions, restoring each original exclusion byte for byte."""
    text = re.sub(
        r"(?m)^# >>> devkit:docs\n.*?^# <<< devkit:docs\n", "", text, flags=re.S
    )
    return re.sub(
        r"(?m)^.*# devkit:docs-exclude=([A-Za-z0-9+/=]*)\n",
        lambda match: base64.b64decode(match[1]).decode(),
        text,
    )


def exclude_generated(text):
    """Patch only fixer exclusions, retaining their original source in a marker."""
    root = dict(yaml.compose(text).value)
    repos = next(value for key, value in root.items() if key.value == "repos")
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    edits = []
    for repo in repos.value:
        fields = {key.value: value for key, value in repo.value}
        for hook in fields["hooks"].value:
            fields = {key.value: (key, value) for key, value in hook.value}
            if fields["id"][1].value not in FIXERS:
                continue
            if hook.flow_style:
                raise ValueError(
                    "docs module requires block-style YAML for whitespace hooks"
                )
            original, pattern = "", "(^|/)generated/"
            start = end = offsets[fields["id"][1].end_mark.line + 1]
            if "exclude" in fields:
                key, value = fields["exclude"]
                start, end = (
                    offsets[key.start_mark.line],
                    offsets[value.end_mark.line + 1],
                )
                original = text[start:end]
                pattern = value.value + "|" + pattern
            encoded = base64.b64encode(original.encode()).decode()
            indent = " " * fields["id"][0].start_mark.column
            replacement = (
                f"{indent}exclude: {json.dumps(pattern)} # {MARKER}-exclude={encoded}\n"
            )
            edits.append((start, end, replacement))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def main():
    """Install or remove docs-owned hooks; never follow a generated symlink."""
    workspace, asset, enabled = sys.argv[1:]
    path = Path(workspace) / ".pre-commit-config.yaml"
    if path.is_symlink() or not path.exists():
        return 0
    try:
        text = restore(path.read_text())
        if enabled == "true":
            text = exclude_generated(text)
            repos = json.loads(Path(asset).read_text())["repos"]
            block = yaml.safe_dump(repos, sort_keys=False)
            text += f"# >>> {MARKER}\n" + "".join(
                "  " + line for line in block.splitlines(keepends=True)
            )
            text += f"# <<< {MARKER}\n"
        path.write_text(text)
        return 0
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"typst-scaffold: {error}", file=sys.stderr)
        return 1
