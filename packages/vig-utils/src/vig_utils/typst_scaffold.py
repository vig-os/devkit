"""Transactionally reconcile module-owned hook configuration (#1994)."""

import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

MARKER = "devkit:docs"
FIXERS = {"trailing-whitespace", "end-of-file-fixer", "mixed-line-ending"}
GENERATED = "(^|/)generated/"


class IndentedDumper(yaml.SafeDumper):
    """Use the scaffold's indented-sequence style at every nesting level."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def fields(node):
    """Get mapping fields with their source spans; reject unsafe flow layouts."""
    if not isinstance(node, yaml.MappingNode) or node.flow_style:
        raise ValueError("hook mappings must use block-style YAML")
    return {key.value: (key, value) for key, value in node.value}


def repos_node(text):
    """Locate the actual repos sequence, regardless of top-level key order."""
    item = fields(yaml.compose(text)).get("repos")
    if (
        item is None
        or not isinstance(item[1], yaml.SequenceNode)
        or item[1].flow_style
        or not item[1].value
    ):
        raise ValueError("repos must be a nonempty block-style sequence")
    return item[1]


def hooks(text):
    """Yield source nodes and stable repository/hook indices."""
    for r, repo in enumerate(repos_node(text).value):
        sequence = fields(repo)["hooks"][1]
        if sequence.flow_style:
            raise ValueError("hooks must use block-style YAML")
        for h, hook in enumerate(sequence.value):
            yield r, h, hook, fields(hook)


def data_end(node):
    """Find the end of data, excluding comments preceding a sibling key."""
    if isinstance(node, yaml.ScalarNode) or node.flow_style or not node.value:
        return node.end_mark.index
    children = (
        [part for pair in node.value for part in pair]
        if isinstance(node, yaml.MappingNode)
        else node.value
    )
    return max(data_end(child) for child in children)


def line_end(text, index):
    """Include the terminating newline of a value's last physical line."""
    return index if text[index - 1 : index] == "\n" else text.index("\n", index) + 1


def patch_fixers(text):
    """Edit scalar values only, preserving dashes, comments, and block scalars."""
    edits, records = [], []
    for r, h, node, values in hooks(text):
        identity = values["id"][1].value
        if identity not in FIXERS:
            continue
        old, pattern = None, GENERATED
        start = end = line_end(text, data_end(node))
        indent = " " * node.start_mark.column
        if "exclude" in values:
            value = values["exclude"][1]
            start, end = value.start_mark.index, value.end_mark.index
            old = text[start:end]
            pattern = value.value + "|" + GENERATED
        replacement = json.dumps(pattern)
        if old is None:
            replacement = f"{indent}exclude: {replacement}\n"
        elif old.endswith("\n"):
            replacement += "\n"
        edits.append((start, end, replacement))
        records.append([r, h, identity, old, pattern])
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text, records


def restore_fixers(text, records):
    """Undo owned scalar edits; fail rather than overwrite a consumer edit."""
    for r, h, identity, old, pattern in reversed(records):
        _, _, _, values = next(item for item in hooks(text) if item[:2] == (r, h))
        key, value = values["exclude"]
        if values["id"][1].value != identity or value.value != pattern:
            raise ValueError("a managed whitespace exclusion was edited")
        start, end = value.start_mark.index, value.end_mark.index
        if old is None:
            start = text.rfind("\n", 0, key.start_mark.index) + 1
            end = line_end(text, end)
            if (
                text[start:end]
                != " " * key.start_mark.column + f"exclude: {json.dumps(pattern)}\n"
            ):
                raise ValueError("a managed whitespace exclusion line was edited")
        elif old.endswith("\n"):
            end += 1
        text = text[:start] + (old or "") + text[end:]
    return text


def restore(text):
    """Remove the owned sequence item and reverse its recorded source edits."""
    match = re.search(
        r"(?ms)^[ \t]*# >>> devkit:docs ([A-Za-z0-9+/=]+)\n.*?^[ \t]*# <<< devkit:docs\n",
        text,
    )
    if match is None:
        if "# >>> devkit:docs" in text:
            raise ValueError("unrecognized or incomplete docs marker")
        return text, None
    metadata = json.loads(base64.b64decode(match[1]))
    text = text[: match.start()] + text[match.end() :]
    text = restore_fixers(text, metadata["fixers"])
    return text, metadata["format"]


def enable(text, asset, formatting):
    """Insert the module block inside repos, skipping existing hook IDs."""
    text, records = patch_fixers(text)
    existing = {values["id"][1].value for _, _, _, values in hooks(text)}
    owned = []
    for hook in json.loads(asset.read_text())["repos"][0]["hooks"]:
        aliases = {hook["id"]} | (
            {"typstyle"} if hook["id"] == "typstyle-check" else set()
        )
        if aliases & existing:
            print(
                f"notice: existing {hook['id']} hook retained; not adding a duplicate",
                file=sys.stderr,
            )
        else:
            owned.append(hook)
    metadata = {"fixers": records, "format": formatting}
    encoded = base64.b64encode(json.dumps(metadata).encode()).decode()
    sequence = repos_node(text)
    indent = " " * sequence.start_mark.column
    block = (
        yaml.dump(
            [{"repo": "local", "hooks": owned}], Dumper=IndentedDumper, sort_keys=False
        )
        if owned
        else ""
    )
    block = f"# >>> {MARKER} {encoded}\n" + block + f"# <<< {MARKER}\n"
    block = "".join(indent + line for line in block.splitlines(keepends=True))
    index = text.rfind("\n", 0, sequence.start_mark.index) + 1
    return text[:index] + block + text[index:]


def validate(path):
    """Use the same schema/parser as the consumer's hook runner."""
    result = subprocess.run(
        ["prek", "validate-config", str(path)], capture_output=True, text=True
    )
    if result.returncode:
        raise ValueError(result.stdout + result.stderr)


def publish(path, candidate):
    """Validate a staged file, atomically install, then validate and roll back."""
    with tempfile.TemporaryDirectory(
        prefix=".typst-scaffold-", dir=path.parent
    ) as directory:
        backup, staged = (
            Path(directory) / "original",
            Path(directory) / "candidate.yaml",
        )
        shutil.copy2(path, backup)
        staged.write_bytes(candidate)
        staged.chmod(path.stat().st_mode)
        validate(staged)
        staged.replace(path)
        try:
            validate(path)
        except OSError, ValueError:
            backup.replace(path)
            raise


def main():
    """Reconcile safely; on any failure retain the original config verbatim."""
    workspace, asset, enabled = sys.argv[1:]
    path = Path(workspace) / ".pre-commit-config.yaml"
    if path.is_symlink() or not path.exists():
        return 0
    try:
        raw = path.read_bytes()
        text = raw.decode()
        formatting = {
            "eol": "\r\n" if "\r\n" in text else "\n",
            "final": text.endswith("\n"),
        }
        text = text.replace("\r\n", "\n")
        if "\r" in text or any(
            isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken))
            for token in yaml.scan(text)
        ):
            raise ValueError("mixed/legacy newlines and YAML aliases are not supported")
        validate(path)
        text, restored = restore(text if text.endswith("\n") else text + "\n")
        formatting = restored or formatting
        if enabled == "true":
            text = enable(text, Path(asset), formatting)
        if not formatting["final"]:
            text = text.removesuffix("\n")
        publish(path, text.replace("\n", formatting["eol"]).encode())
        return 0
    except (OSError, ValueError, KeyError, StopIteration, yaml.YAMLError) as error:
        print(
            f"typst-scaffold: {error}\nOriginal config retained. Add the hooks by hand from {asset}; see docs/NIX.md (Docs module).",
            file=sys.stderr,
        )
        return 1
