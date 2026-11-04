#import "style.typ": (
  figure-style, title-block, type-scale, typography, typst-document,
)

// Read content fields only; never invoke or rebuild title elements.
#let footer-text(value, math-mode: false) = {
  if type(value) == str { return value }
  if type(value) == array {
    return value
      .map(v => footer-text(v, math-mode: math-mode))
      .join("", default: "")
  }
  if type(value) != content { return "" }
  let kind = value.func()
  if kind in (footnote, metadata, state, counter, place) { return "" }
  if kind in ([ ].func(), linebreak, parbreak) { return " " }
  let fields = value.fields()
  if kind == smartquote {
    return if fields.at("double", default: true) { "”" } else { "’" }
  }
  if kind == math.equation {
    let result = footer-text(fields.at("body", default: none), math-mode: true)
    return if result == "" { "□" } else { result }
  }
  for field in ("body", "children", "child", "text") {
    if field in fields {
      return footer-text(fields.at(field), math-mode: math-mode)
    }
  }
  // Math attachments and operators expose content in fields such as base/t/b.
  if math-mode {
    return fields
      .values()
      .filter(v => type(v) in (content, array))
      .map(v => footer-text(v, math-mode: true))
      .join("", default: "")
  }
  ""
}

#let footer-prefix(clusters, width) = {
  let low = 0
  let high = clusters.len()
  while low < high {
    let middle = calc.ceil((low + high) / 2)
    if (
      measure(box(clusters.slice(0, middle).join("", default: "") + "…")).width
        <= width
    ) {
      low = middle
    } else { high = middle - 1 }
  }
  clusters.slice(0, low).join("", default: "") + "…"
}

#let footer-title(body) = layout(size => {
  set text(top-edge: "ascender", bottom-edge: "descender")
  let height = measure(box([Ag])).height
  let value = footer-text(body).replace(regex("\\s+"), " ").trim()
  if value == "" and body != none and body != [] { value = "□" }
  if measure(box(value)).width > size.width {
    value = footer-prefix(value.clusters(), size.width)
  }
  block(height: height, place(top + start, box(value)))
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
