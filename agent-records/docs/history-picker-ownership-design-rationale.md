# History picker and Revert review ownership

## Motivation

The 1,078-line History picker combined presentation values, row rendering,
Items/Viewer navigation, and Revert's editable command grammar, retention policy,
review effects, and approval receipt. `choose_history()` alone occupied 623
lines. Even its read-only mode constructed a Revert command editor, while
checkpoint projection modules imported the application shell just to obtain
their shared value types.

The change separates these reasons to edit the code while preserving the
existing terminal interaction. It does not introduce a new user flow.

## Ownership and dependency direction

Under `adapters.console.terminal.components.history`:

- `model.py` owns the item protocol, entry, anchored detail view, and back
  navigation receipt. Projection modules import this owner directly.
- `rendering.py` owns plain and styled rows, responsive columns, escaped detail
  text, and logical change-position projection.
- `controls.py` owns the reusable Items/Viewer pair and its reading state. It
  composes `SessionWorkbenchNavigation`, `FocusSurface`, the shared scrollable
  pane, focused frames, and shared text layout. A checked-UID projection and an
  item-activation handler are supplied by the composing screen.
- `picker.py` only assembles and runs the read-only screen. Its entry point has
  no operation mode, retention policy, staged checkpoint, or Revert callback.

Under `adapters.console.commands.revert`:

- `review.py` owns `REVERT_COMMAND_FORM`, frozen-frame argv validation, exact
  effect text, `RevertSelectionReceipt`, and the selected revision's review
  appendix.
- `workbench.py` composes History controls with the retention choice and common
  command editor. It owns staging, bidirectional command synchronization, and
  approval. `choose_revert_history()` is the dedicated UI entry point.
- `selection.py` freezes the canonical local Context, checkpoint catalog, and
  reviewed checkpoint units before opening the workbench. `command.py` passes
  the already resolved command-start Context name and retains the existing
  semantic selection, application execution, and receipt paths.

The dependency direction is Revert screen → shared History → common terminal
components. Shared History modules never import Revert. The old
`history.browser` mutation branch and its private exact-version tree projection
are removed; its read-only location/subtree helpers remain. Operand-free Revert
already opened the command-start Context directly, so this does not replace an
active namespace-selection flow or broaden its scope. An explicitly prestaged
UID remains supported by the Revert workbench itself.

## Preserved contracts

1. Rows preview history independently from the exact checked approval target.
   Browsing another row does not retarget a staged Revert command.
2. Every retained checkpoint remains selectable, including repeated operation
   identities and separately persisted Init/Atomize versions.
3. Items Enter stages a full UID and focuses the proposed command. Only Enter
   on a valid command returns the local receipt. Unique prefixes resolve only
   inside the frozen visible frame; another Context or ambiguous UID is invalid.
4. KEEP ALL remains the default. Policy controls and valid command edits update
   one another. The custom checkpoint-unit review and logical detail anchors
   survive both plain and styled detail composition.
5. Empty history has only reading surfaces. Read-only history and empty Revert
   construct no writable command editor.
6. Surface order, initial focus, navigation keys, footer text, semantic colors,
   escaping, dimensions, and plain output remain unchanged. Existing ordered
   terminal evidence remains applicable; this structural split does not add or
   alter an interactive step.
7. Provider calls, storage writes, authorization, locked freshness checks,
   checkpoint-unit restoration, and persisted schemas stay at their existing
   boundaries. The UI receipt alone is not mutation authority.

## Alternatives and verification

A mechanical file split retaining `mode="revert"` in the shared picker would
leave operation semantics in the common component. A callback registry for
arbitrary future mutation workflows would add an abstraction without a current
caller. The selected design exposes the existing reading controls and lets
Revert compose its own approval surfaces; it does not add a navigation engine.

These are internal Python ownership changes: consumers migrate to the narrow
modules, with no facade retaining Revert exports on the shared picker. CLI
arguments and persisted data remain compatible.

Existing interaction tests now target the read-only and Revert entry points
separately. Added regression coverage blocks consuming-screen imports in fresh
processes, prohibits command-editor construction in reading-only screens,
checks preview versus staged identity and invalid command approval, and verifies
complete checkpoint selection and anchored custom-unit review. CLI restoration
and concurrent-frame tests continue to exercise the existing execution boundary.
