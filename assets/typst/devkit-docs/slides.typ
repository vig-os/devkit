#import "style.typ": (
  figure-style, title-block, type-scale, typography, typst-document,
)

// Preserve rich content, treating non-text elements as indivisible tokens.
#let footer-pieces(value) = {
  if value == none { return () }
  if type(value) == str { return value.clusters() }
  if value.has("children") {
    return value.children.map(footer-pieces).flatten()
  }
  if value.func() == text { return value.text.clusters() }
  if value.func() == image { return (box(value),) }
  (value,)
}

#let footer-title(body) = layout(size => {
  let pieces = footer-pieces(body)
  let value = pieces.join()
  if measure(box(value)).width <= size.width { box(value) } else {
    let low = 0
    let high = pieces.len()
    while low < high {
      let middle = calc.ceil((low + high) / 2)
      if (
        measure(box(pieces.slice(0, middle).join() + […])).width <= size.width
      ) {
        low = middle
      } else { high = middle - 1 }
    }
    box(pieces.slice(0, low).join() + […])
  }
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
    footer: context text(size: type-scale.small)[
      #grid(
        columns: (1fr, auto, 1fr),
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
