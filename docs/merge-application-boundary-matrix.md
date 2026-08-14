# Merge application-boundary matrix

## Status

The historical direct Merge contract, its terminal-independent typed
Application/Runtime boundary, and the path-aligned recursive runtime are
verified. The public CLI exposes explicit `--direct` and `--recursive` reach,
while bare `mem merge` opens a readable Source picker and the same reach
control in a TTY. Both adapters invoke the same typed application boundary.

## Motivating distinction

`mem merge SOURCE` has always been a deterministic direct-item union, not a
Git-style three-way merge and not a semantic reconciliation. The command adds
Source items whose durable identities are absent from the current Target. It
does not interpret equal content, changed content, or deletion as a change to
propagate.

The descendant form is a path-aligned recursive union. Because that behavior
requires multi-Context authority, planning, and persistence, the existing
single-Context contract remains independently reproducible through the same
application boundary.

## Characterized direct contract

| Concern | Current owner | Frozen behavior |
| --- | --- | --- |
| CLI input | `commands.merge` | One existing Source locator; the command-start current Context is the Target. |
| Locator meaning | `MemoryStoreMergePort` and authority access | Source and Target are resolved from one captured current-name snapshot. |
| Authority | Grant-aware access and derived-transfer policy | Source requires `READ`; Target requires `CREATE`; cross-domain transfer also enforces its derived permissions. |
| Source projection | Store runtime | A cross-Profile Source exposes direct Memory values only; pointers are not copied across Profiles. |
| Domain operation | `ops.merge` | Iterate direct Source items, add UID-new items, and preserve Target order. No descendant traversal occurs. |
| Existing UID | `ops.merge` | Target wins without comparing content; a Source revision under the same UID is skipped. |
| Source absence | `ops.merge` | Never removes a Target item. Deletions are not propagated. |
| Pointer collisions | `ops.merge` | Duplicate reference targets are skipped and ambiguous Context-like names fail before mutation. |
| Freshness | Store runtime and Store transaction | Source name, UID, and direct-record digest are revalidated; Target save uses UID/digest compare-and-set. |
| Persistence | `save_context_with_sources` | One Target Context and one automatic checkpoint are published under the Source/Target lock set. |
| Result | typed application receipt and CLI presentation | Reports only newly added direct item counts, or `nothing new`. |

## Extracted ownership

| Callable | Layer | Responsibility |
| --- | --- | --- |
| `MergeRequest`, `FrozenMergePlan`, `MergeResult` | Application contract | Typed locator/reach input, reviewed identity binding, and durable result without Store or terminal objects. |
| `prepare_merge`, `run_merge` | Application | Validate before Store access and require the final receipt to match the frozen plan. |
| `MemoryStoreMergePort` | Infrastructure/runtime | Capture current once; resolve authority; project cross-Profile input; freeze Source/Target digests; revalidate and checkpoint atomically. |
| `execute_merge` | Internal Python runtime | Invoke the same use case with no stdout, stderr, prompt-toolkit, or provider dependency. |
| `render_merge_plain` | Plain CLI adapter | Preserve the historical direct success sentence and explicitly report recursive Context/checkpoint totals. |
| Merge TUI setup and screen | Interactive adapter | Freeze a readable Source catalog and current Target, select exact/descendant reach, and expose one exact-command review without owning persistence. |
| `commands.merge.cmd` | Typer composition boundary | Parse argv or route a bare TTY invocation, compose Store runtime, translate expected failures to CLI exits, and invoke the presenter. |

`MergeReach.DESCENDANTS` uses the same typed request and result. Its result
contains one ordered `MergeContextResult` and one checkpoint UID for every
Source-relative Target path, while direct contains exactly one of each.

## Direct compatibility gate

Extraction must preserve all of the following before descendant behavior may
be enabled:

- local Memory, MemoryRef, QueryContextRef, and embedded-Context union;
- target-wins handling for equal UIDs, including different content;
- non-propagation of Source deletion and lexical descendants;
- idempotent repeated execution with one checkpoint per successful command;
- fail-closed Context-like name collision without partial mutation;
- same-Context rejection, relative-locator behavior, Source freshness, and
  Target compare-and-set;
- Grant permissions and cross-Profile Memory-only projection; and
- existing exit status and plain terminal wording.

Focused characterization lives in `tests/test_merge_characterization.py` and
is supplemented by the existing operation, CLI, integration, Grant, reference,
order, query-only, and concurrency suites.

## Descendant contract

The descendant form aligns lexical descendants by their complete relative path
from the two selected roots. Matching paths receive the same
direct UID-union rule, Source-only paths become fresh Target-owned Contexts,
and Target-only paths remain unchanged. A leaf name alone is never sufficient
to match Contexts under different parents.

The complete Source and Target lexical membership, every Source record, every
existing Target identity/digest, every require-new Target path, and every
write-protection decision are checked before publication. All Target writes
share the Store command lock, exclusive graph lock, and deterministic Context
lock set. An exception restores prior Context bytes, removes new checkpoints,
and deletes only the fresh Context identities created by the transaction.

Source-only Contexts receive fresh Context identities. Same-Store internal
Context and MemoryRef pointers are remapped to corresponding Target identities;
cross-Profile recursive Merge copies direct Memory values only, matching the
existing direct transfer boundary. A granted Target may update existing
CREATE-authorized descendants but cannot create a missing authority Context.

The internal `execute_merge()` callable verifies local matching,
Source-only creation, Target-only preservation, complete-relative-path
alignment, granted recursive Source projection, membership freshness, and
exception rollback. `mem merge SOURCE --recursive` exposes that behavior
non-interactively. Bare `mem merge` starts with Source focused, keeps Source
and reach as independent shared controls, shows the exact command and effects,
and mutates only after Enter on that review. Outside a TTY, omitting Source
fails with a stable instruction instead of attempting a full-screen UI.

## Interface verification

The focused automated gate covers the unchanged direct sentence and result,
recursive CLI path creation, conflicting reach flags, non-TTY routing,
readable Source selection, reach traversal, exact-command projection,
cancellation, authority, freshness, rollback, checkpoints, and the deliberate
Undo exclusion. The ordered real-terminal evidence is recorded under
`docs/screenshots/mem-merge-recursive-tui-20260814/` at 180×52 with color ANSI
verified. It demonstrates typed Help, direct root-only mutation, recursive
Source-only path creation, Target-only descendant preservation, durable
receipts, a zero-mutation cancellation path, and a pre-persistence failure
that remains reviewable without publishing a receipt or partial state.

The TUI's `ALL READABLE CONTEXTS` label is a Profile-wide contract, not a
command-local union of Store names and Grant rows. Its setup therefore freezes
the shared Profile readable catalog, retains ordinary local and exact
READ-granted public names, and excludes QUERY-only routes that Merge cannot
materialize. Source selection only establishes readability; operation-owned
DERIVE, EXPORT, and write authority remains enforced when the typed request is
frozen and applied.

## Restoration boundary

Every affected Context retains a normal Merge checkpoint for Diff, History,
and provenance. Recursive Merge checkpoints are intentionally omitted from the
global Undo stack for now. The existing lifecycle restoration archive can
recover one exact Sever-created Context, but cannot yet atomically restore a
mixed command that updates existing Contexts and creates several descendants.
Offering only the existing subset as Undo would leave a partially merged tree,
so the command fails closed at discovery instead. Generic multi-Context
creation restoration is a separately required extension.

## Intentional non-goals

- No common-ancestor or three-way change analysis.
- No propagation of edits or deletions under an existing Memory UID.
- No semantic duplicate or conflict reconciliation; Meld owns that behavior.
- No traversal of embedded Context graphs as if they were lexical descendants.
- No partial publication when one descendant fails validation.
- No recursive Merge between overlapping local Source and Target namespaces.
- No partial Undo of a recursive Merge; generic mixed update/creation
  restoration remains unimplemented.
