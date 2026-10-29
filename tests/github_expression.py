"""Strict managed-workflow expression helper, shared by pytest and bats.

Lives beside workflow_scaffold.py: test infrastructure, not shipped vig-utils.
API: evaluate(expression, context) for bare expressions; render(value, context)
for workflow values (whole expressions preserve types; interpolation is text).
CLI from the repository root: python -m tests.github_expression --context
ctx.json --expr 'fromJSON(inputs.runners).small' (JSON stdout, errors exit 2).
Supports the managed subset plus literal string property indexes used by
release-test. Other functions, numeric/dynamic indexes and filters raise
ValueError with the source and a zero-based position. Parses every branch
before evaluating, so short circuiting cannot conceal unsupported syntax.
"""

import argparse
import json
import math
import re
from pathlib import Path

_TOKEN = re.compile(
    r"\s+|'(?:[^']|'')*'|-?0[xX][0-9a-fA-F]+|"
    r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?|"
    r"[A-Za-z_][A-Za-z_0-9-]*|&&|\|\||==|!=|[!().\[\]]"
)
_PRECEDENCE = {"||": 1, "&&": 2, "==": 3, "!=": 3}


def _fail(source, position, message):
    raise ValueError(f"{message} in {source!r} at position {position}")


def _truth(value):
    return value is not None and value is not False and value != 0 and value != ""


def _number(value):
    if value is None or value == "":
        return 0
    if isinstance(value, (bool, int, float)):
        return float(value)
    try:
        parsed = json.loads(value) if isinstance(value, str) else None
        return float(parsed) if type(parsed) in (int, float) else math.nan
    except ValueError:
        return math.nan


def _equal(left, right):
    if type(left) is not type(right):
        return _number(left) == _number(right)
    if isinstance(left, str):
        return left.casefold() == right.casefold()
    if isinstance(left, (list, dict)):
        return left is right
    return left == right


class _Parser:
    def __init__(self, source):
        self.source, self.tokens, self.cursor = source, [], 0
        position = 0
        while position < len(source):
            match = _TOKEN.match(source, position)
            if not match:
                _fail(source, position, "Unsupported token")
            if not match[0].isspace():
                self.tokens.append((match[0], position))
            position = match.end()
        self.tokens.append(("", len(source)))

    def take(self, expected=None):
        token, position = self.tokens[self.cursor]
        if expected is not None and token != expected:
            _fail(self.source, position, f"Expected {expected!r}")
        self.cursor += 1
        return token, position

    def expression(self, minimum=1):
        left = self.primary()
        while (
            precedence := _PRECEDENCE.get(self.tokens[self.cursor][0], 0)
        ) >= minimum:
            operator, position = self.take()
            left = (operator, position, left, self.expression(precedence + 1))
        return left

    def primary(self):
        token, position = self.take()
        if token == "!":
            return ("!", position, self.primary())
        if token == "(":
            node = self.expression()
            self.take(")")
        elif token == "fromJSON":
            self.take("(")
            node = ("json", position, self.expression())
            self.take(")")
        elif token in {"vars", "github", "needs", "inputs", "secrets"}:
            node = ("context", position, token)
        elif token in {"true", "false", "null"}:
            node = ("literal", position, json.loads(token))
        elif token.startswith("'"):
            node = ("literal", position, token[1:-1].replace("''", "'"))
        elif re.fullmatch(r"-?0[xX][0-9a-fA-F]+", token):
            node = ("literal", position, int(token, 16))
        elif re.match(r"-?\d", token):
            node = ("literal", position, json.loads(token))
        else:
            _fail(self.source, position, "Unsupported operand")
        while self.tokens[self.cursor][0] in {".", "["}:
            operator, position = self.take()
            key, key_position = self.take()
            if operator == "[":
                if not key.startswith("'"):
                    _fail(
                        self.source,
                        key_position,
                        "Only literal string indexes supported",
                    )
                key = key[1:-1].replace("''", "'")
                self.take("]")
            elif not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9-]*", key):
                _fail(self.source, key_position, "Expected property name")
            node = ("property", position, node, key)
        return node


def _resolve(node, context, source):
    operator, position, *args = node
    if operator == "literal":
        return args[0]
    if operator == "context":
        return context.get(args[0])
    left = _resolve(args[0], context, source)
    if operator == "property":
        return left.get(args[1]) if isinstance(left, dict) else None
    if operator == "!":
        return not _truth(left)
    if operator == "json":
        try:
            return json.loads(left)
        except ValueError, TypeError:
            _fail(source, position, "Invalid fromJSON argument")
    if operator == "&&" and not _truth(left) or operator == "||" and _truth(left):
        return left
    right = _resolve(args[1], context, source)
    if operator in {"&&", "||"}:
        return right
    equal = _equal(left, right)
    return equal if operator == "==" else not equal


def evaluate(expression, context):
    """Evaluate a bare expression; unsupported syntax always raises ValueError."""
    parser = _Parser(expression)
    tree = parser.expression()
    parser.take("")
    return _resolve(tree, context, expression)


def render(value, context):
    """Render workflow scalars/collections, preserving whole-expression types."""
    if isinstance(value, list):
        return [render(item, context) for item in value]
    if isinstance(value, dict):
        return {key: render(item, context) for key, item in value.items()}
    if not isinstance(value, str) or "${{" not in value:
        return value
    pieces, cursor = [], 0
    while (start := value.find("${{", cursor)) >= 0:
        pieces.append(value[cursor:start])
        # Quoted strings can contain closing braces; only an unquoted }} closes.
        end = re.search(r"'(?:[^']|'')*'|}}", value[start + 3 :])
        offset = start + 3
        while end and end[0] != "}}":
            offset += end.end()
            end = re.search(r"'(?:[^']|'')*'|}}", value[offset:])
        if not end:
            _fail(value, start, "Unclosed interpolation")
        stop = offset + end.start()
        result = evaluate(value[start + 3 : stop], context)
        cursor = stop + 2
        if start == 0 and cursor == len(value):
            return result
        if isinstance(result, (dict, list)):
            _fail(value, start, "Cannot interpolate a collection")
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        pieces.append(
            ""
            if result is None
            else str(result).lower()
            if isinstance(result, bool)
            else str(result)
        )
    return "".join(pieces) + value[cursor:]


def main():
    """Print JSON for bats; invalid expressions produce a diagnostic and exit 2."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True, type=Path)
    parser.add_argument("--expr", required=True)
    args = parser.parse_args()
    try:
        context = json.loads(args.context.read_text())
        result = (
            render(args.expr, context)
            if "${{" in args.expr
            else evaluate(args.expr, context)
        )
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
