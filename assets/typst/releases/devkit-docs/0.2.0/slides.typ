#import "style.typ": (
  figure-style, title-block, type-scale, typography, typst-document,
)

// Separators are work items too; whitespace is collapsed after traversal.
#let footer-separated(values) = {
  if type(values) != array { return () }
  let result = ()
  for value in values {
    if result.len() > 0 { result.push(" ") }
    result.push(value)
  }
  result
}

// Read only the next level of fields; never rebuild or lay out title elements.
#let footer-children(value, math-mode) = {
  let kind = value.func()
  if kind in (hide, footnote, metadata, state, counter, place) { return () }
  if kind in (image, rect, square, circle, ellipse) { return () }
  if kind in ([ ].func(), linebreak, parbreak) { return (" ",) }
  let fields = value.fields()
  if kind in (h, v) {
    return if fields.at("amount", default: 0pt) == 0pt { () } else { (" ",) }
  }
  if kind == terms.item {
    return (
      fields.at("term", default: none),
      ": ",
      fields.at("description", default: none),
    )
  }
  if kind in (grid.cell, table.cell) {
    return (" ", fields.at("body", default: none), " ")
  }
  if kind in (grid, table, stack, math.vec, math.cases) {
    return footer-separated(fields.at("children", default: ()))
  }
  if math-mode and kind == math.mat {
    let rows = fields.at("rows", default: ())
    if type(rows) != array { return () }
    return footer-separated(rows.map(footer-separated))
  }
  for field in ("body", "children", "child", "text") {
    if field in fields { return (fields.at(field),) }
  }
  // Attachments expose base/top/bottom content, in field order.
  if math-mode {
    return footer-separated(fields
      .values()
      .filter(v => type(v) in (content, array)))
  }
  ()
}

// Bound both extraction and later width measurement, including the ellipsis.
#let footer-append(output, piece) = {
  let clusters = (output + piece).replace(regex("\\s+"), " ").clusters()
  if clusters.len() > 400 {
    return (clusters.slice(0, 399).join("", default: "") + "…", true)
  }
  (clusters.join("", default: ""), false)
}

#let footer-quote(double, output, quotes) = {
  let index = if double { 0 } else { 1 }
  if not double and output.match(regex("[\\p{L}\\p{N}]\\p{M}*$")) != none {
    return ("’", quotes)
  }
  let opened = quotes.at(index)
  if not double and (output == "" or output.match(regex("\\s$")) != none) {
    opened = false
  }
  let marks = if double { ("“", "”") } else { ("‘", "’") }
  quotes.at(index) = not opened
  (marks.at(if opened { 1 } else { 0 }), quotes)
}

// An equation's closing marker detects math with no text leaves.
#let footer-fallback(entry, output) = {
  if "fallback" not in entry { return (output, entry.value) }
  if output.slice(entry.fallback).trim() != "" { return (output, none) }
  (output.slice(0, entry.fallback), "□")
}

#let footer-text(value, math-mode: false) = {
  let work = ((value: value, math-mode: math-mode),)
  let output = ""
  let quotes = (false, false)
  for _ in range(1000000) {
    if work.len() == 0 { break }
    let entry = work.pop()
    let (prefix, current) = footer-fallback(entry, output)
    output = prefix
    if type(current) == str {
      let (next, capped) = footer-append(output, current)
      output = next
      if capped { return output.trim() }
      continue
    }
    let children = ()
    if type(current) == array {
      children = current
    } else if type(current) == content {
      let kind = current.func()
      if kind == smartquote {
        let (mark, next-quotes) = footer-quote(
          current.fields().at("double", default: true),
          output,
          quotes,
        )
        quotes = next-quotes
        work.push((value: mark, math-mode: entry.math-mode))
        continue
      }
      if kind == math.equation {
        entry.math-mode = true
        work.push((value: none, math-mode: true, fallback: output.len()))
      }
      children = footer-children(current, entry.math-mode)
    }
    // LIFO work preserves document order by pushing children in reverse.
    for child in children.rev() {
      work.push((value: child, math-mode: entry.math-mode))
    }
  }
  if work.len() > 0 { output = footer-append(output, "…").first() }
  output.trim()
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
  let value = footer-text(body)
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
