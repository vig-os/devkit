// Public API: import this package, then use #show: document.with(...).
#import "@preview/fletcher:0.5.8"
#import "@preview/cetz:0.3.4"

#let typst-document = document

#let scale = (
  body: 11pt,
  small: 9pt,
  caption: 9pt,
  heading: (20pt, 16pt, 13pt, 11pt),
  figure-min: 7pt,
)

// Align entire numeric columns with numeric-columns(); use number() for
// individual cells. Tabular lining figures keep equal-width digits.
#let number(value) = align(right, text(features: ("tnum", "lnum"), str(value)))
#let numeric-columns(..columns) = (x, y) => if x in columns.pos() {
  right
} else { left }

#let fig(body, caption: none, ..options) = {
  assert(caption != none and caption != [], message: "fig requires a caption")
  figure(body, caption: caption, ..options)
}

#let callout(body, label: [], accent: rgb("404040")) = block(
  width: 100%,
  inset: 10pt,
  stroke: (left: 2pt + accent),
  fill: accent.lighten(95%),
)[#text(weight: "bold", fill: accent, label) #body]
#let note(body, label: [Note], accent: rgb("404040")) = callout(
  body,
  label: label,
  accent: accent,
)
#let warning(body, label: [Warning], accent: rgb("404040")) = callout(
  body,
  label: label,
  accent: accent,
)

#let doc-ref(id, title: none, target: none) = {
  let body = if title == none { [#id] } else { [#id — #title] }
  if target == none { body } else { link(target, body) }
}

#let revision-history(
  ..entries,
  labels: (version: [Version], date: [Date], description: [Description]),
) = table(
  columns: (auto, auto, 1fr),
  table.header(labels.version, labels.date, labels.description),
  ..entries
    .pos()
    .map(entry => (entry.version, entry.date, entry.description))
    .flatten(),
)

// A table show rule sees resolved cells. Rebuild once with explicit booktabs
// rules. A private label prevents reprocessing the reconstructed table.
#let booktabs(it) = {
  if it.at("label", default: none) == <devkit-booktabs> { return it }
  let children = it.children
  let has-header = children.any(child => child.func() == table.header)
  let cols = if type(it.columns) == int { it.columns } else { it.columns.len() }
  if not has-header {
    children = (
      table.header(..children.slice(0, calc.min(cols, children.len()))),
      ..children.slice(calc.min(cols, children.len())),
    )
  }
  let fields = it.fields()
  let _ = fields.remove("children")
  let _ = fields.remove("label", default: none)
  fields.stroke = none
  fields.inset = (x: 6pt, y: 5pt)
  let result = table(
    ..fields,
    table.hline(stroke: 0.8pt),
    ..children.map(child => if child.func() == table.header {
      table.header(
        repeat: true,
        ..child.children.map(cell => if cell.func() == table.cell {
          let fields = cell.fields()
          let body = fields.remove("body")
          table.cell(..fields, strong(body))
        } else { strong(cell) }),
        table.hline(stroke: 0.4pt),
      )
    } else { child }),
    table.hline(stroke: 0.8pt),
  )
  [#result<devkit-booktabs>]
}

#let title-block(
  title: none,
  subtitle: none,
  authors: (),
  date: none,
  version: none,
  status: none,
  doc-id: none,
  logo: none,
  accent: black,
  labels: (:),
) = {
  let values = (doc-id, version, status, date).filter(value => value != none)
  if logo != none {
    image(logo, height: 18mm)
    v(8pt)
  }
  if title != none {
    text(size: 26pt, weight: "bold", fill: accent, title)
    v(6pt)
  }
  if subtitle != none {
    text(size: 16pt, subtitle)
    v(6pt)
  }
  if authors.len() > 0 {
    authors.join(", ")
    v(6pt)
  }
  if values.len() > 0 {
    let names = ("doc-id", "version", "status", "date")
    let all = (doc-id, version, status, date)
    let fields = range(4)
      .filter(i => all.at(i) != none)
      .map(i => {
        let label = labels.at(names.at(i), default: none)
        if label == none { all.at(i) } else { [#label: #all.at(i)] }
      })
    text(size: scale.small, fields.join([ · ]))
    v(12pt)
  }
}

#let document(
  body,
  title: none,
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
  set typst-document(title: title, author: authors)
  set text(font: "Libertinus Serif", size: scale.body, lang: "en")
  show raw: set text(font: "DejaVu Sans Mono", size: scale.small)
  set math.equation(numbering: "(1)")
  set par(justify: true, leading: 0.65em)
  set heading(numbering: "1.1")
  show heading: it => text(
    size: scale.heading.at(calc.min(it.level, scale.heading.len()) - 1),
    fill: accent,
    weight: "bold",
    it,
  )
  set page(
    paper: "a4",
    margin: 2.5cm,
    header: context text(size: scale.small, fill: accent, if title == none {
      []
    } else { title }),
    footer: context {
      let stamp = sys.inputs.at("rev", default: "")
      text(size: scale.small)[
        #grid(
          columns: (1fr, auto, 1fr),
          if title == none { [] } else { title },
          [#counter(page).get().first() / #counter(page).final().first()],
          align(right, text(font: "DejaVu Sans Mono", stamp)),
        )
      ]
    },
  )
  show table: booktabs
  show figure.caption: it => {
    set text(size: scale.caption)
    align(center, block(width: 85%, it))
  }
  show figure.where(kind: table): set figure.caption(position: top)
  show figure.where(kind: image): set figure.caption(position: bottom)
  title-block(
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
  )
  body
}
