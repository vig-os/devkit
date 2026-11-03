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

#let plain-text(value) = {
  if type(value) == str { return value }
  if type(value) != content { return "" }
  if value.has("text") { return value.text }
  if value.has("children") {
    return value.children.fold("", (text, child) => text + plain-text(child))
  }
  if value.has("body") { return plain-text(value.body) }
  ""
}

#let fig(body, caption: none, ..options) = {
  assert(
    plain-text(caption).trim() != "",
    message: "fig requires a non-empty caption",
  )
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

// The explicit opt-out preserves native table settings and user rules.
#let plain-table(..args) = [#table(..args)<devkit-plain-table>]

#let header-cell(cell) = {
  if cell.func() != table.cell { return strong(cell) }
  let fields = cell.fields()
  let body = fields.remove("body")
  table.cell(..fields, strong(body))
}

// Only explicit headers are styled. Never infer grid positions from children.
// User hline/vline decorations are replaced by booktabs rules; plain-table
// retains them. A private label prevents recursive reconstruction.
#let booktabs(it) = {
  if (
    it.at("label", default: none) in (<devkit-booktabs>, <devkit-plain-table>)
  ) { return it }
  let fields = it.fields()
  let children = fields.remove("children")
  let _ = fields.remove("label", default: none)
  fields.stroke = none
  fields.inset = (x: 6pt, y: 5pt)
  let decoration(cell) = cell.func() in (table.hline, table.vline)
  let result = table(
    ..fields,
    table.hline(stroke: 0.8pt),
    ..children
      .filter(child => not decoration(child))
      .map(child => {
        if child.func() != table.header { return child }
        let fields = child.fields()
        let cells = fields.remove("children")
        table.header(
          ..fields,
          ..cells.filter(cell => not decoration(cell)).map(header-cell),
          table.hline(stroke: 0.4pt),
        )
      }),
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

#let typography(body, accent: black) = {
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
  body
}

#let page-layout(body, title: none, accent: black) = {
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
  body
}

#let figure-style(body) = {
  show table: booktabs
  show figure.caption: it => {
    set text(size: scale.caption)
    align(center, block(width: 85%, it))
  }
  set figure.caption(position: bottom)
  show figure.where(kind: table): set block(breakable: true)
  show figure.where(kind: table): set figure.caption(position: top)
  body
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
  show: typography.with(accent: accent)
  show: page-layout.with(title: title, accent: accent)
  show: figure-style
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
