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


def svg_style(node, rules):
    """Resolve presentation attributes, CSS specificity and inline declarations."""
    names = (
        "*",
        node.tag.split("}")[-1],
        "#" + node.get("id", ""),
        *("." + c for c in node.get("class", "").split()),
    )
    matching = []
    for order, (selectors, declarations) in enumerate(rules):
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
            matching.append((max(scores), order, declarations))
    result = dict(node.attrib)
    for _, _, declarations in [*sorted(matching), (3, 0, node.get("style", ""))]:
        for declaration in declarations.split(";"):
            if ":" in declaration:
                name, value = declaration.split(":", 1)
                result[name.strip()] = value.strip()
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


def text_sizes(root, rules):
    """Ignore unused definitions and hidden text; follow local use references."""
    sizes = []
    ids = {node.get("id"): node for node in root.iter() if node.get("id")}

    def visit(node, inherited=16, scale=1, visibility="visible", references=()):
        tag = node.tag.split("}")[-1]
        if tag == "defs":
            return
        style = svg_style(node, rules)
        if style.get("display") == "none":
            return
        visibility = style.get("visibility", visibility)
        size = svg_font(style, inherited)
        scale *= svg_scale(node)
        visible = visibility not in ("hidden", "collapse")
        if (
            tag in ("text", "tspan", "textPath")
            and visible
            and (node.text or "").strip()
        ):
            sizes.append(size * scale)
        if tag == "use":
            target = node.get(
                "href", node.get("{http://www.w3.org/1999/xlink}href", "")
            )
            if (
                not target.startswith("#")
                or target[1:] not in ids
                or target in references
            ):
                raise ValueError("unresolved or cyclic SVG use reference")
            visit(ids[target[1:]], size, scale, visibility, (*references, target))
        for child in node:
            visit(child, size, scale, visibility, references)
            if tag in ("text", "tspan") and visible and (child.tail or "").strip():
                sizes.append(size * scale)

    visit(root)
    return min(sizes) if sizes else None


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
        "smallest": text_sizes(root, svg_rules(root)),
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
