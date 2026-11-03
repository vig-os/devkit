#import "style.typ": plain-text, type-scale
#import "@preview/lilaq:0.5.0" as lq

// Math bypasses text show rules. Evaluate checks inside explicit style wrappers
// before typesetting the equation; arbitrary transformations remain caller-owned.
#let check-math-styles(value) = {
  if type(value) == content {
    let fields = value.fields()
    if "styles" in fields and "child" in fields {
      value.func()(
        {
          context assert(
            text.size >= type-scale.figure-min,
            message: "plot text must be at least 7 pt",
          )
          check-math-styles(value.child)
        },
        value.styles,
      )
    } else {
      for field in fields.values() { check-math-styles(field) }
    }
  } else if type(value) == array {
    for item in value { check-math-styles(item) }
  }
}

// Keep ordinary math and ticks at 9 pt; script bases allow the 50% math style.
#let readable-math(value) = {
  if type(value) != content { return value }
  let fields = value.fields()
  if value.func() == math.attach {
    let base = fields.remove("base")
    for (key, item) in fields {
      if item != none {
        fields.insert(key, text(
          size: type-scale.figure-math,
          readable-math(item),
        ))
      }
    }
    math.attach(readable-math(base), ..fields)
  } else if "children" in fields {
    value.children.map(readable-math).join()
  } else if "styles" in fields and "child" in fields {
    value.func()(readable-math(value.child), value.styles)
  } else { value }
}

// Dimensions resize the data area, never the lettering. No scale-to-fit step.
#let plot(x, y, xlabel: none, ylabel: none, width: 9cm, height: 5cm) = {
  assert(
    plain-text(xlabel).trim() != "" and plain-text(ylabel).trim() != "",
    message: "plot requires non-empty x and y axis labels",
  )
  set text(size: calc.max(type-scale.small, type-scale.figure-min))
  set super(size: type-scale.figure-min)
  set sub(size: type-scale.figure-min)
  show math.equation: it => {
    set text(size: type-scale.small)
    if it.has("label") and it.label == <devkit-plot-math> { return it }
    check-math-styles(it.body)
    [#math.equation(block: it.block, readable-math(it.body)) <devkit-plot-math>]
  }
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

// The caller loads files in its own filesystem scope, including editor previews.
#let glossary-register = state("devkit-glossary-register", none)
#let copying-outline = state("devkit-copying-outline", false)
#let used-terms = state("devkit-used-terms", ())

#let glossary-setup(entries, body) = {
  let register = (:)
  for entry in entries {
    assert(
      entry.id not in register,
      message: "duplicate glossary id: " + entry.id,
    )
    register.insert(entry.id, entry)
  }
  glossary-register.update(register)
  show outline.entry: it => {
    copying-outline.update(true)
    it
    copying-outline.update(false)
  }
  body
}

#let term(id) = context {
  let entries = glossary-register.get()
  assert(
    entries != none,
    message: "no glossary loaded; see glossary-setup in docs/NIX.md",
  )
  assert(id in entries, message: "unknown glossary id: " + id)
  let entry = entries.at(id)
  let copy = copying-outline.get()
  let first = not copy and id not in used-terms.get()
  if not copy {
    used-terms.update(ids => if id in ids { ids } else { ids + (id,) })
    metadata((kind: "devkit-term", id: id))
  }
  if first and entry.kind == "acronym" {
    [#entry.definition (#entry.term)]
  } else { entry.term }
}

#let glossary(title: [Glossary]) = context {
  let ids = used-terms.final()
  assert(ids == ids.dedup(), message: "duplicate ids in glossary usage state")
  if ids.len() > 0 {
    let entries = glossary-register
      .get()
      .values()
      .filter(entry => entry.id in ids)
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
