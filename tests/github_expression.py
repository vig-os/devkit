"""Strict managed-workflow expression helper, shared by pytest and bats.

Lives beside workflow_scaffold.py: test infrastructure, not shipped vig-utils.
API: evaluate(expression, context) for bare expressions; render(value, context)
for runs-on values (whole expressions preserve types; interpolation is text).
S8 must use render_input(value, context) for step and reusable-job with values:
it returns strings, using null -> empty, lowercase booleans and G15 numbers.
Collections cannot be interpolated or passed as scalar inputs.
Properties and fromJSON/toJSON names ignore case; ambiguous object keys raise.
Keyword literals are lowercase only (runner Tokens/LexicalAnalyzer.cs).
Literals and coercion share runner Sdk/ExpressionUtility.cs, ParseNumber.
Numbers are doubles. Equality/property names use simple uppercase mappings.
Numeric input formatting follows runner ExpressionConstants.cs (G15).
Source: https://github.com/actions/runner/tree/main/src/Sdk/DTExpressions2/Expressions2
CLI from the repository root: python -m tests.github_expression --context
ctx.json --expr 'fromJSON(inputs.runners).small' (JSON stdout, errors exit 2).
Add --input for action/reusable inputs. Invalid/unreadable/non-object context
files produce clean errors with exit 2. Non-finite CLI results also exit 2
to keep stdout valid JSON. Render positions refer to the whole value.
toJSON uses two-space indentation, LF newlines and G15 scalar numbers.
Supports the managed subset plus literal string property indexes used by
release-test (present at origin/dev; absent at 1.18.0 in runs-on/with/env,
including devkit-upgrade step env). String array indexes use Index.cs number
conversion, nonnegative floor and Int32 bounds; invalid/out-of-range -> null.
Other functions, numeric/dynamic indexes and filters raise
ValueError with the source and a zero-based position. Parses every branch
before evaluating, so short circuiting cannot conceal unsupported syntax.
"""

import argparse
import json
import math
import re
from pathlib import Path

_TOKEN = re.compile(
    r"\s+|'(?:[^']|'')*'|[+-]?(?:[0-9]|\.[0-9])[^\s()\[\],!<>=&|]*|"
    r"[A-Za-z_][A-Za-z_0-9-]*|&&|\|\||==|!=|\S"
)
_PRECEDENCE = {"||": 1, "&&": 2, "==": 3, "!=": 3}


def _fail(source, position, message):
    raise ValueError(f"{message} in {source!r} at position {position}")


def _truth(value):
    if isinstance(value, float) and math.isnan(value):
        return False
    return value is not None and value is not False and value != 0 and value != ""


def _number(value):
    if value is None or value == "":
        return 0
    if isinstance(value, (bool, int, float)):
        return float(value)
    if not isinstance(value, str):
        return math.nan
    value = value.strip()
    if not value:
        return 0
    if re.fullmatch(r"0x[0-9a-fA-F]+|0o[0-7]+", value):
        number = int(value, 0)
        return float(
            number - 2**32
            if 2**31 <= number < 2**32
            else number
            if number < 2**31
            else math.nan
        )
    if not re.fullmatch(
        r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?|[+-]?Infinity",
        value,
    ):
        return math.nan
    return float(value)


def _ordinal(value):
    """Simple uppercase per character, without multi-character expansions."""
    return "".join(upper if len(upper := char.upper()) == 1 else char for char in value)


def _equal(left, right):
    if type(left) in (int, float) and type(right) in (int, float):
        return _number(left) == _number(right)
    if type(left) is not type(right):
        return _number(left) == _number(right)
    if isinstance(left, str):
        return _ordinal(left) == _ordinal(right)
    if isinstance(left, (list, dict)):
        return left is right
    return left == right


class _Parser:
    def __init__(self, expression, source, offset):
        self.source, self.tokens, self.cursor = source, [], 0
        position = 0
        while position < len(expression):
            match = _TOKEN.match(expression, position)
            if not match:
                _fail(source, position + offset, "Unsupported token")
            if not match[0].isspace():
                self.tokens.append((match[0], position + offset))
            position = match.end()
        self.tokens.append(("", len(expression) + offset))

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
        elif token.lower() in {"fromjson", "tojson"}:
            self.take("(")
            node = (token.lower(), position, self.expression())
            self.take(")")
        elif token.lower() in {"vars", "github", "needs", "inputs", "secrets"}:
            node = ("context", position, token)
        elif token in {"true", "false", "null"}:
            node = ("literal", position, json.loads(token))
        elif re.fullmatch(r"'(?:[^']|'')*'", token):
            node = ("literal", position, token[1:-1].replace("''", "'"))
        elif token and token[0] in "+-.0123456789":
            number = _number(token)
            if math.isnan(number):
                _fail(self.source, position, "Invalid number literal")
            node = ("literal", position, number)
        else:
            _fail(self.source, position, "Unsupported operand")
        while self.tokens[self.cursor][0] in {".", "["}:
            operator, position = self.take()
            key, key_position = self.take()
            if operator == "[":
                if not re.fullmatch(r"'(?:[^']|'')*'", key):
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


def _object(pairs):
    if len({_ordinal(key) for key, _ in pairs}) != len(pairs):
        raise ValueError("Ambiguous object properties")
    return dict(pairs)


def _constant(value):
    raise ValueError(f"Non-standard JSON constant: {value}")


def _lookup(value, key, source, position):
    if isinstance(value, list):
        index = _number(key)
        if math.isfinite(index) and index >= 0:
            integer = math.floor(index)
            if integer <= 2**31 - 1 and integer < len(value):
                return value[integer]
        return None
    if not isinstance(value, dict):
        return None
    try:
        _object(list(value.items()))
    except ValueError as error:
        _fail(source, position, str(error))
    return next(
        (item for name, item in value.items() if _ordinal(name) == _ordinal(key)), None
    )


def _resolve(node, context, source):
    operator, position, *args = node
    if operator == "literal":
        return args[0]
    if operator == "context":
        return _lookup(context, args[0], source, position)
    left = _resolve(args[0], context, source)
    if operator == "property":
        return _lookup(left, args[1], source, position)
    if operator == "!":
        return not _truth(left)
    if operator in {"fromjson", "tojson"}:
        try:
            return (
                _to_json(left)
                if operator == "tojson"
                else json.loads(
                    left,
                    parse_int=float,
                    parse_float=float,
                    parse_constant=_constant,
                    object_pairs_hook=_object,
                )
            )
        except (ValueError, TypeError) as error:
            _fail(source, position, f"Invalid {operator} argument: {error}")
    if operator == "&&" and not _truth(left) or operator == "||" and _truth(left):
        return left
    right = _resolve(args[1], context, source)
    if operator in {"&&", "||"}:
        return right
    equal = _equal(left, right)
    return equal if operator == "==" else not equal


def evaluate(expression, context, *, source=None, offset=0):
    """Evaluate a bare expression; unsupported syntax always raises ValueError."""
    source = expression if source is None else source
    parser = _Parser(expression, source, offset)
    tree = parser.expression()
    parser.take("")
    return _resolve(tree, context, source)


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
        result = evaluate(
            value[start + 3 : stop], context, source=value, offset=start + 3
        )
        cursor = stop + 2
        if start == 0 and cursor == len(value):
            return result
        pieces.append(_string(result, value, start))
    return "".join(pieces) + value[cursor:]


def _string(value, source, position=0):
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float) and not math.isfinite(value):
        return {"nan": "NaN", "inf": "Infinity", "-inf": "-Infinity"}[str(value)]
    if isinstance(value, (int, float)):
        return format(value, ".15G")
    if isinstance(value, str):
        return value
    _fail(source, position, f"Cannot stringify value of type {type(value).__name__}")


def _to_json(value, level=0):
    """Match runner ToJson.cs layout and scalar formatting, including G15."""
    if isinstance(value, (dict, list)):
        mapping = isinstance(value, dict)
        if mapping:
            _object(list(value.items()))
        opening, closing = ("{", "}") if mapping else ("[", "]")
        if not value:
            return opening + closing
        items = (
            [
                f"{_to_json(key)}: {_to_json(item, level + 1)}"
                for key, item in value.items()
            ]
            if mapping
            else [_to_json(item, level + 1) for item in value]
        )
        separator = ",\n" + "  " * (level + 1)
        return (
            opening
            + "\n"
            + "  " * (level + 1)
            + separator.join(items)
            + "\n"
            + "  " * level
            + closing
        )
    if isinstance(value, str):
        result = json.dumps(value, ensure_ascii=False)
        for char in "\u0085\u2028\u2029":
            result = result.replace(char, f"\\u{ord(char):04x}")
        return result
    return "null" if value is None else _string(value, "toJSON")


def render_input(value, context):
    """Render a scalar with value as a GitHub input string, using G15 numbers."""
    return _string(render(value, context), value)


def main():
    """Print JSON for bats; invalid expressions produce a diagnostic and exit 2."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True, type=Path)
    parser.add_argument("--expr", required=True)
    parser.add_argument(
        "--input", action="store_true", help="Render a with input as a string"
    )
    args = parser.parse_args()
    try:
        context = json.loads(
            args.context.read_text(),
            parse_constant=_constant,
            object_pairs_hook=_object,
        )
        if not isinstance(context, dict):
            raise ValueError("Context must be a JSON object")
        result = (
            render(args.expr, context)
            if "${{" in args.expr
            else evaluate(args.expr, context)
        )
        if args.input:
            result = _string(result, args.expr)
        output = json.dumps(result, allow_nan=False)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(output)


if __name__ == "__main__":
    main()
