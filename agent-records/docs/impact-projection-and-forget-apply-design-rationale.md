# Impact projection ownership and direct Forget Apply

## Motivation and ownership

Impact is an operation feature even when another command embeds its report.
Its concrete `ImpactEntry`, `ImpactView`, validation, and provider-free
`ImpactController` conversions therefore belong to
`adapters.console.commands.impact.projection`. Reuse by Update, Forget, Sever,
and other hosts does not make those types generic terminal components.

The session host still owns rendering, scrolling, focus, diff layout, and
artifact/revision matching. It consumes the structural read-only interface in
`terminal.components.resolution.effect_preview`; the interface declares no
concrete values, validation policy, or conversions. This avoids a reverse
import from reusable terminal code into command adapters without retaining a
second Impact implementation or an old-path facade.

Moving only the concrete file and importing it from shared terminal code was
rejected because it reverses the repository's dependency boundary. Keeping the
concrete classes under components because they have multiple callers was also
rejected: consumers do not decide feature ownership. The existing controller
name and constructor contract remain unchanged to keep this relocation focused.

## Ordinary Forget lifecycle

```text
Source and instruction -> one complete provider analysis -> frozen batch
  -> if changed: Impact report -> Apply or Escape
  -> exact authority/freshness/CAS validation -> atomic Apply -> compact receipt
```

Both local and granted changed batches open the report. It shows all Source
Memories as located KEEP/TRANSFORM/DROP transitions, including the original
content of a DROP. The report and one Apply control share a screen, like direct
TTY Update. Items remain available for evidence inspection, but this command
surface offers no per-Memory revision choices or response composer. The existing
application selection/revision functions remain available to their own callers.

The report uses the frozen public Source name, including a granted public path.
The historical Context-shaped command hook retains the original frozen Source
binding for that projection; display-name substitution never rebinds authority.

Apply returns the identical process-local snapshot. It does not reconnect the
provider, derive a second proposal, save a session, or write the Source. The
command's existing application boundary revalidates the frozen Source and exact
mutation permissions before publishing the accepted batch and checkpoint.
Escape discards the process-local proposal and creates no Context write,
checkpoint, or terminal receipt. Unlike Update, Forget has no durable staged
session to resume after cancellation.

Empty and all-KEEP batches finish with the existing no-change result, without a
screen or checkpoint. Explicit non-TTY invocation retains direct execution.
Standalone `mem impact forget` still only inspects a process-local batch and has
no Apply capability; this change does not promote it into an execution command.

The former local auto-accept branch and granted compact decision screen did not
render the supplied Impact controller. Mandatory preview for changed TTY batches
is an intentional interaction change. It keeps approval adjacent to the exact
Source effects rather than passing an unused preview into a different screen.
The shared ownership/Undo policy remains unchanged for other operations.

## Verification and limits

- Ownership tests locate the concrete classes under Impact and prove that
  importing the reusable session shell does not assemble command packages.
- Projection and shared-shell regressions retain the same text, diff, revision,
  read-only, and renderer contracts after relocation.
- Forget tests exercise both local and granted report routing, all-KEEP bypass,
  and the real report shell inside an isolated command invocation. They prove
  that Escape publishes nothing, Apply creates one checkpoint after approval,
  and Source drift during inspection rejects publication without losing the
  concurrent change. Non-TTY, authority, and Undo/Redo tests remain applicable.
- The [ordered PTY record](screenshots/forget-impact-apply-20260906/README.md)
  captures real command execution with deterministic provider responses. It
  covers preview, Apply, cancellation, no-op, and read-only verification in
  a 180-column by 52-row color terminal. No live provider or personal store is
  used in this evidence.

This task does not change Update's existing Apply screen, provider schemas,
whole-frame budgeting, semantic disposition rules, persistence formats, or
shared semantic colors. Historical screenshots document their captured
revisions; the new ordered record supersedes them for direct Forget approval.

### Implementation verification snapshot

At implementation time the selected primary-checkout suite passed 278 tests.
The focused-only checkout passed 393 tests in its broader run; its one remaining
failure was the pre-existing callable-catalog expectation that Meld is CLOSED,
while the unchanged authored registry classifies it MIXED. No route judgment
was changed to satisfy that test.

Two earlier broad-run failures (Resolve's fixture expecting a different
provider operation, and Update's Grant fixture omitting placement records) and
nine obsolete granted-Meld expectations were reproduced without this task's
changes on base `a0df9e6cb`. Those eleven tests and one unrelated endpoint-setup
interaction test were excluded from the focused broad run. This is a scoped
verification result, not a claim that the entire repository test suite passes.
The focused patch also incorporates the concurrent Context-availability naming
and Copy/Move ownership commits through base `430e2eb45`; unrelated working
changes remain excluded.
