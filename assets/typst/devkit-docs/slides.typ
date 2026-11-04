#import "style.typ": (
  figure-style, title-block, type-scale, typography, typst-document,
)

// Normalize tall pieces before measuring their available horizontal space.
#let footer-inline(value) = {
  let extent = measure(box(value))
  let height = measure(box([Ag])).height
  // Keep collapsible spaces outside boxes; wrap block-capable elements inline.
  if extent.width == 0pt and extent.height == 0pt { return value }
  if extent.height <= height { return box(value) }
  box(baseline: (at: bottom, shift: 0.2 * text.size), scale(
    (text.size / extent.height) * 100%,
    origin: top + left,
    reflow: true,
    box(value),
  ))
}

// Required positional fields follow their original field order. All remaining
// fields are passed by name; no wrapper element types need to be enumerated.
#let footer-rebuild(value, field, piece) = {
  let fields = value.fields()
  let positional = ()
  for (key, original) in fields {
    if key == field {
      positional.push(if key == "children" { (piece,) } else { piece })
      let _ = fields.remove(key)
    } else if key in ("dest", "styles", "alignment", "angle") {
      positional.push(original)
      let _ = fields.remove(key)
    }
  }
  value.func()(..positional, ..fields)
}

// Split any content-bearing element and reconstruct every piece identically.
#let footer-pieces(value, words: true) = {
  if value == none { return () }
  if type(value) == str {
    return if words {
      value.matches(regex("\\S+|\\s+")).map(m => m.text)
    } else { value.clusters() }
  }
  let fields = value.fields()
  if value.func() in (linebreak, parbreak) { return ([ ],) }
  for field in ("body", "children", "child", "text") {
    if field not in fields { continue }
    let inner = fields.at(field)
    if inner == none { return (value,) }
    let pieces = if type(inner) == array {
      inner.map(v => footer-pieces(v, words: words)).flatten()
    } else { footer-pieces(inner, words: words) }
    if pieces.len() == 0 { return (value,) }
    return pieces.map(p => footer-rebuild(value, field, p))
  }
  (value,)
}

#let footer-prefix(pieces, width) = {
  let low = 0
  let high = pieces.len()
  while low < high {
    let middle = calc.ceil((low + high) / 2)
    if measure(box(pieces.slice(0, middle).join() + […])).width <= width {
      low = middle
    } else { high = middle - 1 }
  }
  low
}

#let footer-line(value, height) = {
  let line = box(value)
  let extent = measure(line)
  if extent.height > height {
    line = scale(
      (height / extent.height) * 100%,
      origin: top + left,
      reflow: true,
      line,
    )
  }
  let result = block(height: height, place(top + left, line))
  assert.eq(
    measure(result).height,
    height,
    message: "footer must occupy exactly one line",
  )
  result
}

#let footer-title(body) = layout(size => {
  set text(top-edge: "ascender", bottom-edge: "descender")
  let height = measure(box([Ag])).height
  let pieces = footer-pieces(body).map(footer-inline)
  let value = pieces.join()
  if measure(box(value)).width > size.width {
    let count = footer-prefix(pieces, size.width)
    // An oversized word still gets a visible prefix in its original style.
    if (
      count < pieces.len()
        and measure(box(pieces.at(count) + […])).width > size.width
    ) {
      let chars = footer-pieces(pieces.at(count), words: false)
      pieces = pieces.slice(0, count) + chars
      count = footer-prefix(pieces, size.width)
    }
    // An indivisible oversized atom must remain visible, even without text.
    let suffix = […]
    if (
      count < pieces.len()
        and measure(box(pieces.at(count) + suffix)).width > size.width
    ) {
      suffix = [□…]
      count = footer-prefix(
        pieces.slice(0, count),
        size.width - measure(box([□])).width,
      )
    }
    value = text(dir: text.dir, pieces.slice(0, count).join() + suffix)
  }
  footer-line(value, height)
})

#let render(
  body,
  title: none,
  short-title: none,
  subtitle: none,
  authors: (),
  date: none,
  version: none,
  status: none,
  doc-id: none,
  accent: rgb("303030"),
  logo: none,
  labels: (:),
) = {
  if type(authors) == str { authors = (authors,) }
  set typst-document(title: title, author: authors)
  show: typography.with(accent: accent)
  show: figure-style
  set page(
    width: 256mm,
    height: 144mm,
    margin: 12mm,
    footer: context text(
      size: type-scale.small,
      top-edge: "ascender",
      bottom-edge: "descender",
    )[
      #grid(
        columns: (1fr, auto, 1fr),
        column-gutter: 2mm,
        footer-title(if short-title == none { title } else { short-title }),
        [#counter(page).get().first() / #counter(page).final().first()],
        align(right, text(font: "DejaVu Sans Mono", sys.inputs.at(
          "rev",
          default: "",
        ))),
      )
    ],
  )
  if (
    (title, subtitle, date, version, status, doc-id, logo).any(v => v != none)
      or authors.len() > 0
  ) {
    align(horizon, title-block(
      title: title,
      subtitle: subtitle,
      authors: authors,
      date: date,
      version: version,
      status: status,
      doc-id: doc-id,
      logo: logo,
      accent: accent,
      labels: labels,
    ))
    pagebreak(weak: true)
  }
  body
}

// Same show-rule namespace contract as devkit-document.
#let with(..options) = {
  assert(options.pos().len() == 0, message: "Use #show: slides.with(...)")
  body => render(body, ..options.named())
}
