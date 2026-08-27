# Shared selection control design rationale

## Motivation

Mem accumulated several controls that all represented a cursor over stable
choices and a retained checked value, but each redrew that state differently.
Meld endpoint setup used individually bordered rectangles, Resolution Viewer
used a boxed group containing radio-like rows, Responses used unboxed
circle/diamond rows, and Context trees owned another checkmark/style decision.
The difference was implementation drift rather than a semantic requirement.

## Common contract

`memcommit.adapters.console.selection` now owns three operation-neutral layers:

1. `SelectionOption` carries a stable UID, one-line label, and optional
   explanatory description.
2. `FlatSelectionState` separates the keyboard cursor from one staged checked
   value and owns clamped movement, exact selection, toggling, clearing, and
   reopening the cursor on a saved value.
3. `selection.tui` owns checked markers, cursor/selection styles, the shared
   Meld-style rectangle geometry, stacked long-description cards, and the
   compact tree-row projection.

The common visual policy uses `✓` for a staged selection. The current keyboard
target receives the shared blue focus treatment and a heavy rectangle border;
an unfocused staged value retains the shared selected fill. Choice controls do
not use `○`, `●`, or `◇` to create a second radio-button grammar.
For a stacked card, the hidden viewport anchor follows its closing border so a
lower choice cannot appear as only a top edge. A surrounding semantic block
must not place an earlier cursor anchor ahead of the active card.

Layout remains adaptive. Short mode or range choices may be horizontal
segments or adjacent compact rectangles. A Response Decision stacks full-width
cards so its description can wrap. A Context/Memory selector retains its tree
indentation, expansion glyph, annotations, and multi-selection rules while
using the common checkmark and focus/selection styles.

## Consumers and compatibility

`commands.horizontal_choice` remains a compatibility facade for existing Meld,
Find, Help, and Context-targeting callers. Its state delegates movement and the
checked value to `FlatSelectionState`; its boxed layout delegates every card to
the common renderer. Meld therefore keeps the familiar setup appearance while
becoming the source of a service-wide policy rather than a special case.

The common `RESPONSES` frame and the older Resolution Viewer compatibility path
project their operation-owned choices into the same stacked-card renderer.
Responses projects the same flat state as unboxed stacked rows and places them
with its free-form Response stop in one linear Up/Down sequence. The focused
label is bold over the shared blue fill, while its description keeps the fill
without bold. This layout and topology remain Response-owned rather than part
of the operation-neutral flat state; other callers may retain bordered cards.
Older compact Meld and Atomize snapshot paths use the same checked-marker
policy, even though a stable text snapshot does not reproduce interactive focus
borders. Context endpoint, Find target, and Sever setup trees use the common
tree marker and style projection while retaining
`ContextTreeState` and `ContextSelectionState`.

## Semantic boundaries

A common selection control does not decide what selection means. Callers retain:

- immediate Left/Right selection versus Up/Down followed by Enter;
- single versus multiple cardinality and minimum checked counts;
- the Response box and its transition to free-form input;
- tree expansion, availability, annotations, authority, and destination rules;
- validation, persistence, provider turns, Apply actions, and CAS boundaries.

The Response layer still stores an opaque operation-owned option UID and text.
Context selection still stores canonical names. Horizontal modes still expose
their existing typed state. The common package is process-local interaction and
presentation, not a cross-operation persistence schema.

## Alternatives considered

- One universal widget containing horizontal, vertical, tree, single, multiple,
  editor, and persistence behavior was rejected because it would mix layout and
  operation semantics and make simple controls depend on Resolution behavior.
- Sharing only colors was rejected because cursor movement, checked state,
  marker choice, escaping, and border geometry would continue to drift.
- Forcing Response descriptions into horizontal Meld boxes was rejected because
  long semantic alternatives need wrapping. Stacked cards reuse the same visual
  primitive without sacrificing readable width.
