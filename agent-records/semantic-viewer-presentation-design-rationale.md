# Semantic Viewer presentation policy

## Motivation

Mem's section-oriented terminal surfaces had already converged on the same
light-blue palette and stable section navigation, but they still expressed the
current reading position differently. Resolution rewrote focused headings as
`── HEADING ──`, Compare parsed finished report text and applied the same
decoration, Result used an operation-local selected row, and Share moved a
cursor across physical lines, including blank lines. Cards often colored their
complete explanatory body merely because the card was focused.

That made focus presentation an operation-owned rendering decision even though
focus and viewport position are application-wide interaction mechanics. It
also made report text differ according to navigation state and allowed a title
change to alter Compare's section parser.

## Shared boundary

`memcommit.commands.semantic_viewer` owns the presentation of one semantic
Viewer stop. A `SemanticViewerBlock` receives neutral semantic fragments and
adds the common focus styles and prompt-toolkit viewport anchor. A
`SemanticViewerSection` pairs that block with one stable UID, kind, and optional
Items row. `SemanticViewerDocument` derives the navigation order and rendered
order from the same immutable section sequence.

The shared layer owns only:

- active versus resting semantic styles;
- start, end, or two-sided viewport anchors;
- removal of positional emphasis when Viewer does not own keyboard focus; and
- the correspondence between a stable section identity and its rendered
  block.

Operation adapters continue to own report meaning, evidence grouping, Memory
identity, choices, response validation, provider turns, persistence, authority,
and mutation boundaries. Result cases, Compare relations, and Resolution
issues therefore remain different semantic models even when their focus is
presented by the same component.

## Visual invariants

- Focus is a presentation overlay. It must not insert decorative punctuation
  into persisted or snapshot report text.
- The focused semantic identity uses the shared light blue. Neutral explanatory
  prose inside that block remains white.
- An individual Memory rests in lavender and may use the shared blue treatment
  while it is the active Viewer stop.
- A focused card colors only its identifying top line or heading. Its entire
  body must not become blue merely because the card owns the cursor.
- Nested choice navigation remains distinct: the current option is blue and
  underlined, while `✓` records the staged or durable selection independently
  of cursor position.
- Leaving Viewer removes positional focus color and nested cursor treatment.
  Selection badges and checked choices remain visible because they are state,
  not keyboard position.
- A complete wrapped block may anchor at its end when exposing only its first
  line would hide the body or closing border. The operation does not place
  raw cursor anchors around such blocks itself.

## Rollout

Resolution-based Atomize, Meld, Sever, Update, Forget, Impact, and adaptive
Review now use the shared block policy. Standalone Compare projects its report
into a `SemanticViewerDocument`, so the same section objects supply navigation
and rendering. Result case rows and Share's Context, Memory, and Action blocks
use the same focus renderer. Share's Context pane now navigates stable Context
and Destination sections rather than each physical line.

Help, Context trees, Session/History pickers, and Ground are not semantic
Viewer documents. They should reuse lower-level frame, row, choice, table,
width, and anchor primitives, but their hierarchy or exact-command state must
not be forced into the semantic report model. Ground in particular retains its
Goal–Contexts–Rules–Memories–Chat and exact approval contract.

## Alternatives and limitations

A palette-only change was rejected because callers would still decide which
parts of a block receive focus and where the viewport anchor belongs. One
universal terminal document for every picker and composer was also rejected:
selection, hierarchy, text editing, and exact approval are different
interaction contracts.

Resolution still has operation-adaptive builders for native reports, seeded
Compare/Meld cards, Impact rows, item details, and final review. Those builders
now delegate focus presentation to the shared block policy, but their semantic
projection remains intentionally operation-aware. Future refactors may project
more of those builders directly into `SemanticViewerDocument`; they must not
collapse their distinct action or evidence models to do so.
