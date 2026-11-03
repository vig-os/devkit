// Import this package, then apply #show: devkit-document.with(...).
// Helpers stay in style.typ; only the documented API is exported here.
#import "style.typ": (
  booktabs-table, doc-ref, fig, note, number, numeric-columns, plain-table,
  revision-history, type-scale, warning,
)
#import "@preview/fletcher:0.5.8"
#import "@preview/cetz:0.3.4"

#import "devkit-document.typ" as devkit-document

#import "content.typ": (
  glossary, glossary-setup, plot, section-slide, slide, term,
)
#import "slides.typ" as slides
