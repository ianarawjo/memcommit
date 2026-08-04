# Granted Context navigation design rationale

## Motivating failure

Study Task 2 exposes `advisor1` and `advisor2` as recursive `READ` grants and
the proposal-submission guidelines as a `QUERY`-only grant. The switch picker
rendered all three routes, but classified every granted row as a virtual,
non-materialized namespace. Enter therefore expanded or reported the row as
unavailable, and the switch command later required a local `context.json`.
Participants could see the advisors but could not enter them, which blocked the
Task 2 workflow.

## Navigation contract

- Every granted row displays its complete normalized permission tuple, such as
  `[grant READ]`, `[grant CREATE + READ + UPDATE + DELETE + QUERY]`, or
  `[grant QUERY + SAVE QUERY SESSION]`. This keeps the experimental condition
  visible instead of collapsing several capabilities into an ambiguous edit
  label. `SAVE QUERY SESSION` is the user-facing name for the persisted
  `SESSION_LOG` permission; the friendlier label does not change serialized
  grants or command authorization.
- A granted `READ` Context and every READ-visible frozen descendant are
  selectable in `mem switch`. Selectability is derived from the structured
  `READ` permission, never by interpreting the user-facing annotation.
- A `QUERY`-only route remains visible but non-selectable. It is opened only by
  `mem query`, because ordinary navigation must not disclose its content.
- Selecting a granted Context stores only its public canonical name as the
  current navigation pointer. It never copies or materializes authority
  Memories in the participant Profile.
- Every command that consumes that current pointer resolves and authorizes the
  grant again. Revocation, permission loss, attachment replacement, missing
  authority bindings, or an ambiguous public name fails closed.
- Explicit public granted names may be resolved from any valid local attachment
  in the active Profile. This is necessary because the picker shows all views
  for the Profile, not only views attached directly to the current owned
  Context. If more than one distinct attachment resolves the same public name,
  the command rejects it as ambiguous rather than choosing one implicitly.
- Lexical parent navigation continues to prefer owned Contexts. Within a
  granted tree, `..` may return to another READ-granted parent; it never opens a
  query-only override.

## Read and query surfaces

`mem ls`, `mem show`, and `mem status` resolve the current READ grant through
the bounded `GrantedReadStore`. `mem contexts` marks the public granted name as
current, and Profile inventory accepts it only when the active registry still
contains an effective READ grant for that public name. Mutating commands use
the same resolver with their required permission and therefore reject an
Advisor READ grant.

READ does not expose authority checkpoint history. Current-state `mem find`
and the three quality finders (`find-duplicates`, `find-ambiguities`, and
`find-conflicts`) use the same bounded READ projection as listing: recursive
Find includes READ-visible namespace descendants, while a more-specific
QUERY-only override never becomes candidate evidence. Temporal Find fails
closed with an explicit history-boundary error instead of opening the
authority store's checkpoints. Query routing recovers the owned attachment
behind a current READ-granted view so a
participant may enter an advisor and still invoke the separately authorized
proposal-guidelines query route.

An explicit `mem ls --copy` may place READ-visible text on the operating-system
clipboard, which is an intentional user-controlled disclosure and cannot be
revoked afterward. The participant Profile's private structured clipboard is
different: for a granted list it stores only the exact grant binding, copy
mode, recursive flag, and snapshot digests. `mem ls --paste` must re-resolve
the same grant and unchanged authority projection before replaying the text.
It therefore fails after revocation, grant revision, Profile change, or source
drift instead of retaining a hidden durable copy of authority Memories.

Compare resolves both the active reference and `--to` peer through the same
READ boundary. When a selected root contains descendant Contexts, its bounded
current projection is flattened in deterministic traversal order and each
Memory is labelled with its public source Context; nested QUERY-only overrides
are omitted. A comparison involving any granted frame is initially
process-local and visibly marked `NOT SAVED (GRANTED VIEW)`: persisting the
ordinary full-frame artifact would copy authority source text into the
participant Profile. The grant and source projection are revalidated after the
provider call before even that ephemeral result is published. Durable granted
Compare sessions require a separately redacted artifact schema.

## Safety and limitations

The persistent current pointer intentionally does not freeze a grant revision.
Like an ordinary current Context name, it is orientation state rather than an
authorization receipt. Each consuming command freezes the current registry and
authority identities for its own operation. A replacement grant with the same
unambiguous public route can therefore become the newly resolved view; a stale
or revoked route cannot continue exposing its earlier authority content.

This change does not grant query permission to Advisor content and does not
make proposal guidelines readable. It also does not add authority history,
revert, or checkpoint browsing to a READ grant.
