# Profile-wide Context navigation design rationale

## Historical motivation and revised boundary

The original browser experiment made List's exact result available inside a
Profile-wide Context tree. Rooting that tree at the exact Context hid useful
orientation; broadening it to the full Profile fixed orientation but made
List look like a second Switch operation. `mem contexts` created the same
overlap in browse-only form.

The later decision is to remove the competing presentation. Top-level
`mem list` / `mem ls` and `mem contexts` now print static reports in every
terminal. Bare `mem switch` owns interactive Profile navigation. The
Profile-wide navigation projection remains useful inside operation-owned setup
screens whose explicit purpose is selecting a Context.

## Contract

Interactive Context selectors such as bare `mem switch` and Merge setup share
one public Profile tree:

- every ordinary local Context;
- every valid READ-granted public Context; and
- opaque QUERY-only Grant routes for namespace orientation.

The caller's exact or current Context selects the initial row only. It does not
crop the tree. READ-granted current rows remain valid initial rows. QUERY-only
rows are never materialized, selected as an ordinary Context, or passed to a
Memory loader.

List no longer has a separate presentation scope. Its output, clipboard
receipt, and paste verification are all rooted at the resolved operand.
`mem contexts` similarly renders its readable catalog without entering this
tree component. Its static rows nevertheless use the same frozen public-name
hierarchy order as a fully expanded Switch tree: local and granted names appear
under their nearest real Context parent instead of forming separate ownership
blocks. Siblings retain the frozen catalog order, so local siblings precede
appended Grant siblings within one branch. A fixed `GRANT` column precedes
every non-owned public name, while a compact colored capability cluster follows
the name. The prefix, rather than a distant Grant-only block, carries ownership
meaning. This separates ownership from usable authority without restoring the
former interactive browser or repeating exact dependency permissions on every
descendant.

## Implementation boundary

`freeze_profile_context_navigation` composes the Profile-wide readable catalog
with the same Grant navigation snapshot used by Switch. It returns local rows,
virtual rows, the exact selectable virtual subset, annotations, and the
readable catalog that owns loading. Interactive operation adapters decide
their initial row and display scope.

The common picker supports a selected initial expansion subtree and an exact
set of Contexts whose item previews start visible. These are presentation
values. They do not become locators, receipts, persisted preferences, or
authority decisions.

## Alternatives and limitations

Keeping the exact target as a List TUI root and showing a grayscale
Profile-wide tree were rejected because both retained two visible meanings for
List. Reusing Switch by invoking its CLI remains rejected because human output
and mutation continuations are not internal APIs.

The catalog and current pointer are separate read snapshots, so concurrent
creates, deletes, Grant changes, or switches may make an interactive selector
temporarily stale. Operations that later execute or mutate must retain their
own resolution, authority revalidation, and CAS boundaries.
