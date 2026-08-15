# Ground Example USE and Distill input

## Problem

The named-Ground Memory list displayed a durable `USE` disposition, and Fit
already selected active `INCLUDE` Examples. `mem distill --ground`, however,
ignored that disposition and distilled the complete bound
`WORKING_CANDIDATES` Context. Turning a checkbox off therefore did not prevent
that Example text from reaching the Distill provider.

## Contract

`Space` on one selected active Ground Memory prepares, but does not immediately
apply, one exact command:

```text
mem ground NAME --if-ground-version TOKEN \
  --set-example-use EXAMPLE_UID --use INCLUDE|EXCLUDE
```

Approval changes one existing Example in one new Ground revision and appends a
linked Decision record. Rules, bound Contexts, ordinary Context Memories, and
checkpoints remain unchanged. The command rejects an incomplete option pair, a
no-op value, ambiguous identity, inactive Example, stale bound frame, or stale
Ground CAS token.

For a Ground containing Example records, Ground Distill constructs its frozen
source from active `PROPOSED` or `ACCEPTED` Examples whose USE is `INCLUDE`.
Version-3 sources use the authoritative proposition. Version-2 sources retain
their exact `input -> expected` compatibility projection. Each provider alias
maps to the Ground Example UID, so returned evidence citations identify the
reviewed proposition rather than merely its original Context Memory.

`EXCLUDE`, `UNRESOLVED`, `REJECTED`, and `DEFERRED` Example content does not
enter the provider payload. If Example records exist but none are active and
included, freezing fails before provider construction. The Ground revision,
record digest, bound candidate frame, and Context digest are revalidated before
and after inference, so a concurrent toggle cannot publish a result for a
different participation set.

## Compatibility boundary

Older bound Grounds can contain no Example records and historically distilled
the complete `WORKING_CANDIDATES` Context. That exact no-Example shape retains
the legacy route. It is not used as an all-off fallback: once any Example
record exists, USE is authoritative.

The binary checkbox does not cycle back to `UNRESOLVED`. An explicit toggle
from `UNRESOLVED` means INCLUDE; a future semantic review action may restore
unresolved state if that workflow is needed. Inactive rejected/deferred rows
remain inspectable but cannot be toggled back into semantic input without a
separate review-state transition.

## Verification

Focused tests cover revision and Decision recording, CLI pairing and mutation,
stale/no-op failure, TUI Space-to-exact-approval behavior, and provider payload
exposure before and after a toggle. The all-off case proves failure before the
provider factory is called. The ordered 180×52 true-color capture under
`docs/screenshots/mem-ground-use-toggle-distill-20260815/` records the list,
exact approval, applied checkbox, and post-close payload verification.
