#import "style.typ": (
  figure-style, title-block, type-scale, typography, typst-document,
)

// Scale inline objects uniformly to at most the footer font size.
#let footer-inline(value) = {
  let atom = box(value)
  let extent = measure(atom)
  if extent.height > text.size {
    atom = scale(
      (text.size / extent.height) * 100%,
      origin: top + left,
      reflow: true,
      atom,
    )
  }
  box(baseline: (at: bottom, shift: 0.2 * text.size), atom)
}

// Split inside style wrappers and reconstruct each token with the same fields.
#let footer-pieces(value, words: true) = {
  if value == none { return () }
  if type(value) == str {
    return if words {
      value.matches(regex("\\S+|\\s+")).map(m => m.text)
    } else { value.clusters() }
  }
  let fields = value.fields()
  if value.func() in (linebreak, parbreak) { return ([ ],) }
  if "children" in fields {
    return value.children.map(v => footer-pieces(v, words: words)).flatten()
  }
  if "styles" in fields and "child" in fields {
    return footer-pieces(value.child, words: words).map(p => value.func()(
      p,
      value.styles,
    ))
  }
  if value.func() in (strong, emph, smallcaps, link) {
    let pieces = footer-pieces(fields.remove("body"), words: words)
    if value.func() == link {
      let dest = fields.remove("dest")
      return pieces.map(p => link(dest, p, ..fields))
    }
    return pieces.map(p => value.func()(p, ..fields))
  }
  if value.func() == text {
    return footer-pieces(fields.remove("text"), words: words).map(p => text(
      p,
      ..fields,
    ))
  }
  if value.func() in (image, box) { return (footer-inline(value),) }
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
  let pieces = footer-pieces(body)
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
    value = pieces.slice(0, count).join() + […]
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
