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

- Every granted row puts a fixed `GRANT` ownership marker before its public
  Context name. Position carries the primary safety meaning: the row is a view
  of another Profile's Context, not a locally owned Context merely decorated
  with extra metadata. The authority Profile remains visible after `FROM`.
- Static `mem contexts` does not move those rows into a trailing Grant-only
  block. It projects the combined frozen catalog in the same depth-first public
  hierarchy as a fully expanded Switch tree, so one public name has one stable
  neighborhood across the two commands. The explicit `GRANT` prefix remains
  the ownership boundary.
- Context navigation is an orientation surface, not a permission audit. Its
  trailing capability cluster therefore projects the exact normalized Grant
  into the compact vocabulary `READ`, `QUERY`, `EDIT`, `DELETE`, `EXPORT`, and
  `SHARE`. `EDIT` summarizes ordinary `CREATE` or `UPDATE` capability while
  `DELETE` remains explicit because of its different risk. Dependency atoms
  such as `DERIVE`, `COMBINE`, `ACCEPT_DERIVED`, analysis retention, embedding,
  and query-session retention remain on the exact Grant and remain mandatory
  at execution, but are not repeated on every Context row. For example, the
  study views render as `READ + QUERY + EDIT + DELETE + EXPORT`, `READ +
  EXPORT`, or `QUERY` instead of printing the complete atomic tuple.
- The capability cluster uses the shared teal source-capability style. The
  `GRANT` marker and Context name stay neutral, except that the exact current
  Context name and leading `*` retain the established green current treatment.
  A single color for the cluster avoids making `DELETE` look executed or
  `EDIT` look successful; focus still overrides the cluster in an interactive
  picker.
- An operation-owned selector may append the one extra capability that makes a
  row usable in that operation. Embed setup, for example, appends `EMBED` only
  to rows that passed its exact `EMBED` authorization check; the compact base
  catalog itself does not imply that capability.
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
and the semantic quality operations (`dedun`, `find-ambiguities`, and
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

## Composite mutation permissions

Mutation authorization follows the concrete item effects, not the command's
friendly name. `chunk` removes one selected Memory UID or every splittable
direct Memory in its reviewed Context batch and creates replacement UIDs, so a
granted execution requires both `DELETE` and `CREATE`; `clear`
requires `DELETE` for its directly owned items. The complete permission set is
checked again while holding the grant-registry lock through the authority save.
Failure therefore occurs before the first authority write, and the authority
checkpoint records the grant UID, revision, grantee Profile, and public Context
used for the operation.

`forget` cannot authorize from the natural-language request or command name.
It first produces a reviewable proposal, then derives the exact permission
union from the accepted changes: edits require `UPDATE` and removals require
`DELETE`. The accepted changes remain in-memory until that complete union is
revalidated under the registry lock and the single Context save succeeds. The
retired `integrate` command is no longer a granted mutation route; historical
checkpoints retain their original identity for inspection.

`merge` authorizes its source for `READ` and its current target for `CREATE`.
When the two endpoints belong to different Profile stores, only direct ordinary
Memory values are portable: embedded Contexts, Memory references, and
query-only routes are deliberately omitted because their UIDs and locators are
meaningful only inside the source Profile. Both grant bindings and the source
projection digest are rechecked before the target save.

Directional `impact` resolves both `--from` and `--to` as READ endpoints and
stores an exact grant binding for either granted side. A granted-source plan
uses update-session schema 5; applying it to a participant-owned target holds
the registry lock and every authority source Context lock through target
freshness checks and the complete local multi-owner write. Revocation or
source drift therefore invalidates the staged plan instead of treating a saved
digest as continuing authority. The established local-source to granted-target
path still derives CREATE, UPDATE, and DELETE from planned target effects.

An Update whose source and target are both granted but belong to separate
authority Profile stores remains intentionally rejected. Coordinating two
remote authority write domains requires a durable cross-store transaction
journal; approximating that boundary could leave a partial write.

## Safety and limitations

The persistent current pointer intentionally does not freeze a grant revision.
Like an ordinary current Context name, it is orientation state rather than an
authorization receipt. Each consuming command freezes the current registry and
authority identities for its own operation. A replacement grant with the same
unambiguous public route can therefore become the newly resolved view; a stale
or revoked route cannot continue exposing its earlier authority content.

The compact navigation vocabulary is deliberately not reversible into the
complete atomic permission tuple. Permission management and authorization
receipts must continue to use the exact Grant record; no command may authorize
an operation by parsing `mem contexts`, picker text, color, or compact labels.

Missing-name classification follows the same namespace boundary. A failed
ordinary Context lookup becomes a Grant-specific error only when an effective
Grant public name is an exact or lexical-prefix match for the requested name.
The current local Context is orientation, not evidence that an unrelated
operand names a granted view. This keeps missing local operands consistent
across Switch, Embed, and every other consumer of the shared access resolver,
while preserving permission, frozen-scope, and ambiguity errors for names that
actually enter a Grant namespace. Persisted links and analysis receipts retain
their exact attachment UID and Grant binding, so their revalidation bypasses
general locator classification: loss of that route remains an explicit
revocation failure rather than being downgraded to an ordinary missing input.

This change does not grant query permission to Advisor content and does not
make proposal guidelines readable. It also does not add authority history,
revert, or checkpoint browsing to a READ grant.
