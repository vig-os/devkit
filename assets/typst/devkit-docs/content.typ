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
  set super(size: type-scale.figure-min, typographic: false)
  set sub(size: type-scale.figure-min, typographic: false)
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

#let index-glossary(entries) = {
  assert(
    entries != none and entries.len() > 0,
    message: "empty glossary register; add at least one entry",
  )
  let register = (:)
  for entry in entries {
    assert(
      entry.id not in register,
      message: "duplicate glossary id: " + entry.id,
    )
    register.insert(entry.id, entry)
  }
  register
}

#let setup-register(register, body) = {
  glossary-register.update(register)
  show outline.entry: it => {
    copying-outline.update(true)
    it
    copying-outline.update(false)
  }
  body
}

#let glossary-setup(entries, body) = setup-register(
  index-glossary(entries),
  body,
)

// The canonical spelling stays outside context, so PDF bookmarks can read it.
#let render-term(entry) = {
  context {
    if (
      not copying-outline.get()
        and entry.id not in used-terms.get()
        and entry.kind == "acronym"
    ) {
      [#entry.definition (]
    }
  }
  entry.term
  context {
    let copy = copying-outline.get()
    let first = not copy and entry.id not in used-terms.get()
    if first and entry.kind == "acronym" { [)] }
    if not copy {
      used-terms.update(ids => if entry.id in ids { ids } else {
        ids + (entry.id,)
      })
      metadata((kind: "devkit-term", id: entry.id))
    }
  }
}

#let lookup-term(register, id) = {
  assert(id in register, message: "unknown glossary id: " + id)
  render-term(register.at(id))
}

#let term(id) = context {
  let entries = glossary-register.get()
  assert(
    entries != none,
    message: "no glossary loaded; see https://github.com/vig-os/devkit/blob/dev/docs/NIX.md#house-style-package",
  )
  lookup-term(entries, id)
}

#let glossary(title: [Glossary]) = context {
  assert(
    glossary-register.get() != none,
    message: "no glossary loaded; see https://github.com/vig-os/devkit/blob/dev/docs/NIX.md#house-style-package",
  )
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

// Bind the register before layout when canonical text is needed in bookmarks.
#let glossary-tools(entries) = {
  let register = index-glossary(entries)
  (
    term: id => lookup-term(register, id),
    setup: body => setup-register(register, body),
  )
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
