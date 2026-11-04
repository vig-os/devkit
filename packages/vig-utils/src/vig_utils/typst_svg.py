"""SVG text sizes and painted viewport scales for the optional Typst guards."""

import re
from fractions import Fraction

from defusedxml.ElementTree import parse


def points(value):
    """Convert absolute lengths, with SVG's 96-dpi unitless/px convention."""
    value = re.sub(r"^0%\s*\+\s*", "", str(value))
    match = re.fullmatch(r"\s*([\d.]+)(pt|mm|cm|in|px)?\s*", value)
    factors = {
        None: 0.75,
        "px": 0.75,
        "pt": 1,
        "mm": 72 / 25.4,
        "cm": 720 / 25.4,
        "in": 72,
    }
    return float(match[1]) * factors[match[2]] if match else None


def svg_rules(root):
    """Collect simple CSS selectors, including Matplotlib's universal rule."""
    rules = []
    for node in root.iter():
        if node.tag.split("}")[-1] == "style":
            for selectors, declarations in re.findall(
                r"([^{}]+)\{([^{}]+)\}", node.text or ""
            ):
                selectors = [selector.strip() for selector in selectors.split(",")]
                if not all(
                    re.fullmatch(r"\*|[.#]?[\w-]+", selector) for selector in selectors
                ):
                    raise ValueError("unresolved SVG CSS selector")
                rules.append((selectors, declarations))
    return rules


def font_shorthand(value):
    """Extract the size; unsupported system/variable fonts remain unresolved."""
    if value in ("inherit", "unset", "initial"):
        return value if value != "initial" else "16px"
    match = re.fullmatch(
        r"(?:(?:normal|italic|oblique|small-caps|bold|bolder|lighter|[1-9]00)\s+)*"
        r"(0|[\d.]+(?:px|pt|mm|cm|in|em|%))"
        r"(?:\s*/\s*(?:normal|[\d.]+(?:px|pt|em|%)?))?\s+.+",
        value,
    )
    return match[1] if match else f"unresolved font shorthand: {value}"


def declarations(text):
    """Expand font at its declaration position before resolving the cascade."""
    for declaration in text.split(";"):
        if ":" not in declaration:
            continue
        name, value = (part.strip() for part in declaration.split(":", 1))
        important = bool(re.search(r"\s*!important\s*$", value, re.IGNORECASE))
        value = re.sub(r"\s*!important\s*$", "", value, flags=re.IGNORECASE)
        if name == "font":
            name, value = "font-size", font_shorthand(value)
        yield name, value, important


def svg_style(node, rules):
    """Cascade each property by importance, specificity and declaration order."""
    names = (
        "*",
        node.tag.split("}")[-1],
        "#" + node.get("id", ""),
        *("." + c for c in node.get("class", "").split()),
    )
    result, priorities = dict(node.attrib), {}
    matching = []
    for order, (selectors, text) in enumerate(rules):
        scores = [
            2
            if s.startswith("#")
            else 1
            if s.startswith(".")
            else -1
            if s == "*"
            else 0
            for s in selectors
            if s in names
        ]
        if scores:
            matching.append((max(scores), order, text))
    for specificity, order, text in [*matching, (3, len(rules), node.get("style", ""))]:
        for index, (name, value, important) in enumerate(declarations(text)):
            priority = (important, specificity, order, index)
            if name not in priorities or priority >= priorities[name]:
                result[name], priorities[name] = value, priority
    return result


def svg_font(style, inherited):
    """Return font-size in SVG user units, respecting inherited em and %."""
    value = style.get("font-size", str(inherited))
    if value in ("inherit", "unset"):
        return inherited
    if value.endswith("%"):
        return inherited * float(value[:-1]) / 100
    if value.endswith("em"):
        return inherited * float(value[:-2])
    size = points(value)
    if size is None:
        raise ValueError(f"unresolved SVG font-size {value}")
    return size / 0.75


def svg_scale(node):
    """Scale SVG user coordinates; rotations/translations preserve font size."""
    scale = 1
    for function, args in re.findall(r"(\w+)\(([^)]*)\)", node.get("transform", "")):
        if function == "scale":
            scale *= min(abs(float(n)) for n in re.split(r"[,\s]+", args.strip()))
        elif function not in ("translate", "rotate"):
            raise ValueError(f"unresolved SVG transform {function}")
    return scale


def svg_viewport(node, viewport, override=None):
    """Return nested SVG/symbol user coordinates and their physical scale."""
    dimensions = override or (node.get("width", "100%"), node.get("height", "100%"))

    def length(value, parent):
        if str(value).endswith("%"):
            return float(value[:-1]) / 100 * parent
        absolute = points(value)
        if absolute is None:
            raise ValueError(f"unresolved SVG viewport length {value}")
        return absolute / 0.75

    width, height = (
        length(value, parent)
        for value, parent in zip(dimensions, viewport, strict=True)
    )
    box = node.get("viewBox", "").replace(",", " ").split()
    if len(box) != 4:
        return (width, height), 1
    vw, vh = map(float, box[2:])
    if vw <= 0 or vh <= 0:
        raise ValueError("non-positive SVG viewBox")
    ratios = (width / vw, height / vh)
    aspect = node.get("preserveAspectRatio", "xMidYMid meet")
    scale = max(ratios) if "slice" in aspect else min(ratios)
    return (vw, vh), scale


class SvgText:
    """Traverse visible text with bounded local use expansion."""

    def __init__(self, root, rules, viewport):
        self.root, self.rules, self.viewport = root, rules, viewport
        self.ids = {node.get("id"): node for node in root.iter() if node.get("id")}
        self.sizes, self.expansions = [], 0

    def use(self, node, size, scale, visibility, references, viewport):
        target = node.get("href", node.get("{http://www.w3.org/1999/xlink}href", ""))
        if (
            not target.startswith("#")
            or target[1:] not in self.ids
            or target in references
        ):
            raise ValueError("unresolved or cyclic SVG use reference")
        self.expansions += 1
        if len(references) >= 32 or self.expansions > 4096:
            raise ValueError("SVG use expansion limit exceeded")
        override = (node.get("width", "100%"), node.get("height", "100%"))
        self.visit(
            self.ids[target[1:]],
            size,
            scale,
            visibility,
            (*references, target),
            viewport,
            override,
        )

    def visit(
        self,
        node,
        inherited=16,
        scale=1,
        visibility="visible",
        references=(),
        viewport=None,
        override=None,
    ):
        tag = node.tag.split("}")[-1]
        if tag == "defs" or (tag == "symbol" and override is None):
            return
        style = svg_style(node, self.rules)
        if style.get("display") == "none":
            return
        viewport = viewport or self.viewport
        visibility = style.get("visibility", visibility)
        size = svg_font(style, inherited)
        scale *= svg_scale(node)
        if node is not self.root and tag in ("svg", "symbol"):
            viewport, factor = svg_viewport(node, viewport, override)
            scale *= factor
        visible = visibility not in ("hidden", "collapse") and size > 0 and scale > 0
        if (
            tag in ("text", "tspan", "textPath")
            and visible
            and (node.text or "").strip()
        ):
            self.sizes.append(size * scale)
        if tag == "use":
            self.use(node, size, scale, visibility, references, viewport)
        for child in node:
            self.visit(child, size, scale, visibility, references, viewport)
            if tag in ("text", "tspan") and visible and (child.tail or "").strip():
                self.sizes.append(size * scale)


def text_sizes(root, rules, viewport):
    """Ignore unused definitions/hidden text and scale nested viewports."""
    walker = SvgText(root, rules, viewport)
    walker.visit(root)
    return min(walker.sizes) if walker.sizes else None


def svg_metrics(path):
    """Accept harmless DOCTYPEs while blocking entities and external references."""
    root = parse(
        path, forbid_dtd=False, forbid_entities=True, forbid_external=True
    ).getroot()
    viewbox = root.get("viewBox", "").replace(",", " ").split()
    width, height = points(root.get("width", "")), points(root.get("height", ""))
    if len(viewbox) == 4:
        vw, vh = map(float, viewbox[2:])
    elif width and height:
        vw, vh = width / 0.75, height / 0.75
    elif width:
        vw, vh = width / 0.75, width / 0.75
    else:
        raise ValueError("unresolved SVG viewport dimensions")
    if vw <= 0 or vh <= 0:
        raise ValueError("non-positive SVG viewBox")
    if width is None:
        width = height * vw / vh if height is not None else vw * 0.75
    if height is None:
        height = width * vh / vw
    return {
        "smallest": text_sizes(root, svg_rules(root), (vw, vh)),
        "width": width,
        "height": height,
        "view_width": vw,
        "view_height": vh,
        "aspect": root.get("preserveAspectRatio", "xMidYMid meet"),
    }


def svg_text(path):
    """Compatibility surface: smallest user size, viewBox width, natural width."""
    metrics = svg_metrics(path)
    return metrics["smallest"], metrics["view_width"], metrics["width"]


def effective_text_size(metrics, width, height, fit):
    """Compose SVG preserveAspectRatio with Typst's contain/cover/stretch fit."""
    if metrics["smallest"] is None:
        return None

    # Rational arithmetic keeps the exactly-seven-point boundary exact rather
    # than compensating for floating point error with a loosened threshold.
    def number(value):
        return Fraction(str(value))

    iw, ih = number(metrics["width"]), number(metrics["height"])
    inner = (iw / number(metrics["view_width"]), ih / number(metrics["view_height"]))
    if "none" not in metrics["aspect"]:
        scale = max(inner) if "slice" in metrics["aspect"] else min(inner)
        inner = (scale, scale)
    outer = (number(width) / iw, number(height) / ih)
    if fit != "stretch":
        scale = min(outer) if fit == "contain" else max(outer)
        outer = (scale, scale)
    return float(
        number(metrics["smallest"])
        * min(a * b for a, b in zip(inner, outer, strict=True))
    )
