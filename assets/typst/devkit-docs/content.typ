#import "style.typ": plain-text, type-scale
#import "@preview/lilaq:0.5.0" as lq

// Dimensions resize the data area, never the lettering. No scale-to-fit step.
#let plot(x, y, xlabel: none, ylabel: none, width: 9cm, height: 5cm) = {
  assert(
    plain-text(xlabel).trim() != "" and plain-text(ylabel).trim() != "",
    message: "plot requires non-empty x and y axis labels",
  )
  set text(size: calc.max(type-scale.small, type-scale.figure-min))
  show text: it => context {
    assert(
      text.size >= type-scale.figure-min,
      message: "plot text must be at least 7 pt",
    )
    it
  }
  lq.diagram(
    width: width,
    height: height,
    xlabel: xlabel,
    ylabel: ylabel,
    lq.plot(x, y),
  )
}

#let register() = yaml(bytes(sys.inputs.at("devkit-glossary", default: "[]")))
#let used-terms = state("devkit-used-terms", ())

#let term(id) = {
  let entries = register().filter(entry => entry.id == id)
  assert(entries.len() == 1, message: "unknown glossary id: " + id)
  let entry = entries.first()
  context {
    let first = id not in used-terms.get()
    used-terms.update(ids => if id in ids { ids } else { ids + (id,) })
    metadata((kind: "devkit-term", id: id))
    if first and entry.kind == "acronym" {
      [#entry.definition (#entry.term)]
    } else { entry.term }
  }
}

#let glossary(title: [Glossary]) = context {
  let ids = used-terms.final()
  let entries = register().filter(entry => entry.id in ids)
  if entries.len() > 0 {
    heading(numbering: none, outlined: true, title)
    for entry in entries.sorted(key: entry => entry.term) {
      block[#strong(entry.term) — #entry.definition]
    }
  }
}

#let slide(body, title: none) = {
  pagebreak(weak: true)
  if title != none { heading(numbering: none, title) }
  body
  pagebreak(weak: true)
}

#let section-slide(body) = slide(align(horizon + center, text(
  size: type-scale.heading.first(),
  weight: "bold",
  body,
)))
