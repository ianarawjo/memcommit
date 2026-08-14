# Profile-wide Context navigation design rationale

## Motivating failure

When a participant ran List from a nested Context, the TUI rooted itself at
that exact Context. The command displayed the requested material but hid the
parent, sibling, and other Profile branches needed to understand where that
material lived. `mem contexts` had a related granted-current edge: an active
READ-granted Context could be present in the Profile while the browser still
fell back to the first local row.

The resulting confusion was not about missing data from List. It was about
turning an operation's input scope into a navigation boundary.

## Contract

Interactive `mem list` / `mem ls`, `mem contexts`, and bare `mem switch` share
one public Profile tree:

- every ordinary local Context;
- every valid READ-granted public Context; and
- opaque QUERY-only Grant routes for namespace orientation.

The exact or current Context selects the initial row only. It does not crop the
tree. READ-granted current rows remain valid initial rows. QUERY-only rows are
never materialized, selected as an ordinary Context, or passed to a Memory
loader.

List keeps two independent scopes. Its noninteractive output, clipboard
receipt, and paste verification remain rooted at the resolved operand. Its TUI
uses the Profile tree for orientation. Plain List initially exposes direct
items only for the resolved Context; recursive List expands and exposes the
resolved lexical subtree, not every Profile branch.

## Implementation boundary

`freeze_profile_context_navigation` composes the Profile-wide readable catalog
with the same Grant navigation snapshot used by Switch. It returns local rows,
virtual rows, the exact selectable virtual subset, annotations, and the
readable catalog that owns loading. Commands decide only their initial row and
display scope.

The common picker supports a selected initial expansion subtree and an exact
set of Contexts whose item previews start visible. These are presentation
values. They do not become locators, receipts, persisted preferences, or
authority decisions.

## Alternatives and limitations

Keeping the exact target as the TUI root was rejected because it reproduced the
study confusion even though the list result itself was correct. Expanding and
loading the entire Profile was rejected because orientation does not justify
eager reads and produced a noisy initial screen. Reusing Switch by invoking its
CLI was rejected because human output and mutation continuations are not
internal APIs.

The catalog and current pointer are separate read snapshots, so concurrent
creates, deletes, Grant changes, or switches may make a browser temporarily
stale. The browser is read-only, while operations that later execute or mutate
must retain their own resolution, authority revalidation, and CAS boundaries.
