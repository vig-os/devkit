"""Transactionally reconcile module-owned hook configuration (#1994)."""

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
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
    """Yield repository identity, hook ID, and source nodes; never positions."""
    for repo in repos_node(text).value:
        repo_fields = fields(repo)
        identity = repo_fields["repo"][1].value
        sequence = repo_fields["hooks"][1]
        if not isinstance(sequence, yaml.SequenceNode) or sequence.flow_style:
            raise ValueError("hooks must use a block-style sequence")
        for hook in sequence.value:
            values = fields(hook)
            yield identity, values["id"][1].value, hook, values


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
    for repo, identity, node, values in hooks(text):
        if identity not in FIXERS:
            continue
        old, pattern = None, GENERATED
        start = end = line_end(text, data_end(node))
        indent = " " * node.start_mark.column
        if "exclude" in values:
            value = values["exclude"][1]
            start, end = value.start_mark.index, value.end_mark.index
            old = text[start:end]
            separator = "\n|" if re.compile(value.value).flags & re.VERBOSE else "|"
            pattern = value.value + separator + GENERATED
        replacement = json.dumps(pattern)
        if old is None:
            replacement = f"{indent}exclude: {replacement}\n"
        elif old.endswith("\n"):
            replacement += "\n"
        edits.append((start, end, replacement))
        records.append([repo, identity, old, pattern])
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text, records


def restore_fixers(text, records):
    """Undo only parsed values we own, located by repository and hook ID."""
    for repo, identity, old, pattern in reversed(records):
        matches = [item for item in hooks(text) if item[:2] == (repo, identity)]
        if len(matches) != 1:
            raise ValueError(
                f"cannot uniquely locate {identity} in repository {repo}; restore the hook and repository URL, switch docs OFF, then reapply your edit"
            )
        values = matches[0][3]
        key, value = values["exclude"]
        if (old is None or old.endswith("\n")) and "#" in text[
            value.end_mark.index : line_end(text, value.end_mark.index)
        ]:
            raise ValueError(
                f"managed exclusion comment for {identity}: move the comment to its own line before retrying"
            )
        if value.value != pattern:
            raise ValueError(f"managed exclusion for {identity} was edited")
        start, end = value.start_mark.index, value.end_mark.index
        if old is None:
            start = text.rfind("\n", 0, key.start_mark.index) + 1
            end = line_end(text, end)
            if text[start : key.start_mark.index].strip():
                raise ValueError(
                    f"cannot safely remove relocated exclude for {identity}; move exclude after id and retry"
                )
        elif old.endswith("\n"):
            end = line_end(text, end)
        text = text[:start] + (old or "") + text[end:]
    return text


def block_digest(block):
    """Decline every hand edit to owned content, including prose comments."""
    lines = [
        line
        for line in block.splitlines()
        if not line.strip().startswith("# devkit-state: ")
        and line.strip() not in {f"# >>> {MARKER}", f"# <<< {MARKER}"}
    ]
    data = textwrap.dedent("\n".join(lines)).encode()
    return hashlib.sha256(data).hexdigest()


def block_operation(text, library, operation, *arguments):
    """Use the installer's shared #1654 range/splice helpers on staged LF text."""
    with tempfile.TemporaryDirectory(prefix="preserved-hooks-") as directory:
        path = Path(directory) / "config.yaml"
        path.write_text(text)
        result = subprocess.run(
            [
                "bash",
                "-c",
                'set -euo pipefail; source "$1"; "$2" "${@:3}"',
                "preserved-hooks",
                str(library),
                operation,
                str(path),
                *map(str, arguments),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode and not (
            operation == "hook_block_range" and result.returncode == 1
        ):
            raise ValueError(
                result.stderr.strip() or f"{operation} failed ({result.returncode})"
            )
        return (
            result.stdout.strip()
            if operation == "hook_block_range"
            else path.read_text()
        )


def restore(text, library):
    """Apply the shared range engine and decline edits, as historical folds do."""
    span = block_operation(text, library, "hook_block_range", "docs", "true")
    if not span:
        if any(
            line.strip().split()[:3]
            in (["#", ">>>", "devkit:docs"], ["#", "<<<", "devkit:docs"])
            for line in text.splitlines()
        ):
            raise ValueError("incomplete docs marker")
        return text
    start, end = map(int, span.split())
    block = "".join(text.splitlines(keepends=True)[start - 1 : end])
    chunks = [
        json.loads(line.strip().removeprefix("# devkit-state: "))
        for line in block.splitlines()
        if line.strip().startswith("# devkit-state: ")
    ]
    if not chunks:
        raise ValueError(
            "unrecognized docs state; remove the old block and exclusions by hand"
        )
    metadata = json.loads("".join(chunks))
    if block_digest(block) != metadata["digest"]:
        raise ValueError(
            "managed docs block was edited; preserve or move your custom hooks by hand"
        )
    text = block_operation(text, library, "delete_lines", start, end)
    return restore_fixers(text, metadata["fixers"])


def rendered_hooks(text, owned):
    """Match the consumer's dash spacing and nested sequence indentation."""
    sequence = repos_node(text)
    repo = sequence.value[0]
    key, nested = fields(repo)["hooks"]
    repo_indent = sequence.start_mark.column
    mapping_step = repo.start_mark.column - repo_indent
    # Match indentless sequences, otherwise use the consumer's outer step.
    # Copying an already inconsistent inner step would add a lint finding.
    hook_indent = key.start_mark.column - repo_indent
    if nested.start_mark.column != key.start_mark.column:
        hook_indent += repo_indent or mapping_step
    hook_step = (
        nested.value[0].start_mark.column - nested.start_mark.column
        if nested.value
        else mapping_step
    )
    body = yaml.dump(owned, Dumper=IndentedDumper, sort_keys=False, indent=hook_step)
    return (
        "-"
        + " " * (mapping_step - 1)
        + "repo: local\n"
        + " " * (key.start_mark.column - repo_indent)
        + "hooks:\n"
        + textwrap.indent(body, " " * hook_indent)
    )


def managed_block(body, records):
    """Keep exact feature sentinels and bounded, reversible state comments."""
    metadata = json.dumps(
        {"fixers": records, "digest": block_digest(body)}, separators=(",", ":")
    )
    state = "".join(
        f"# devkit-state: {json.dumps(metadata[i : i + 24])}\n"
        for i in range(0, len(metadata), 24)
    )
    return f"# >>> {MARKER}\n" + state + body + f"# <<< {MARKER}"


def enable(text, asset, library):
    """Extend preserved-block insertion with reversible exclusion field edits."""
    text, records = patch_fixers(text)
    identities = [(repo, hook) for repo, hook, _, _ in hooks(text)]
    if any(identities.count((repo, hook)) != 1 for repo, hook, *_ in records):
        raise ValueError("ambiguous repository/hook ID for a managed exclusion")
    existing = {hook for _, hook in identities}
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
    body = rendered_hooks(text, owned) if owned else ""
    block = managed_block(body, records)
    sequence = repos_node(text)
    indent = " " * sequence.start_mark.column
    block = "\n".join(indent + line for line in block.splitlines())
    line = sequence.start_mark.line + 1
    return block_operation(text, library, "splice_lines", line, line - 1, block)


def validate(path):
    """Use the same schema/parser as the consumer's hook runner."""
    result = subprocess.run(
        ["prek", "validate-config", str(path)], capture_output=True, text=True
    )
    if result.returncode:
        raise ValueError(result.stdout + result.stderr)


def publish(path, candidate):
    """Validate staged bytes, write in place, then validate and roll back."""
    with tempfile.TemporaryDirectory(
        prefix=".preserved-hooks-", dir=path.parent
    ) as directory:
        backup, staged = (
            Path(directory) / "original",
            Path(directory) / "candidate.yaml",
        )
        shutil.copy2(path, backup)
        staged.write_bytes(candidate)
        staged.chmod(path.stat().st_mode)
        validate(staged)
        try:
            path.write_bytes(candidate)
            validate(path)
        except Exception:
            path.write_bytes(backup.read_bytes())
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
        if (
            "\r" in text
            or (formatting["eol"] == "\r\n" and raw.count(b"\n") != raw.count(b"\r\n"))
            or any(
                isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken))
                for token in yaml.scan(text)
            )
        ):
            raise ValueError("mixed/legacy newlines and YAML aliases are not supported")
        validate(path)
        library = Path(asset).parent / "preserved-hooks.sh"
        text = restore(text if text.endswith("\n") else text + "\n", library)
        if enabled == "true":
            text = enable(text, Path(asset), library)
        if not formatting["final"]:
            text = text.removesuffix("\n")
        candidate = text.replace("\n", formatting["eol"]).encode()
        publish(path, candidate)
        if candidate != raw:
            channel = "fold" if b"# >>> devkit:docs" in raw else "insert"
            print(f"preserved-hook-{channel}: docs in .pre-commit-config.yaml")
        return 0
    except (
        Exception
    ) as error:  # Retain bytes and give advice even for unexpected failures.
        print("preserved-hook-drift: docs in .pre-commit-config.yaml")
        advice = (
            f" Add hooks by hand from {asset} if enabling docs manually."
            if enabled == "true"
            else ""
        )
        print(
            f"reconcile-preserved-hooks: {type(error).__name__}: {str(error) or repr(error)}\nOriginal config retained. Resolve the reported edit before retrying; use {asset} as a reference; see docs/NIX.md (Docs module).{advice}",
            file=sys.stderr,
        )
        return 1
