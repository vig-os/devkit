// A namespace, not a callable template: direct calls are a type error.
#let with(..options) = {
  import "style.typ": render-document
  assert(
    options.pos().len() == 0,
    message: "Use #show: devkit-document.with(...), not a plain function call",
  )
  body => render-document(body, ..options.named())
}
