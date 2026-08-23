# `mem lock` / `mem unlock` design rationale

## Problem

Memcommit already uses short-lived filesystem locks to serialize cooperative
writers, but those locks are concurrency machinery. They do not express a
person's durable instruction that reviewed Context or Memory state must remain
unchanged across later commands.

The user-facing protection surface is:

```text
mem lock | mem unlock
mem lock TARGET [--recursive] | mem unlock TARGET [--recursive]
mem lock --context CONTEXT [--recursive]
mem unlock --context CONTEXT [--recursive]
mem lock --memory SELECTOR [--context CONTEXT]
mem unlock --memory SELECTOR [--context CONTEXT]
mem lock --profile | mem unlock --profile
```

Bare lock and unlock target the current Context. A positional `TARGET` uses the
shared direct-Memory locator grammar: an eight-or-more-character UUID-shaped
operand or `CONTEXT:UID` selects Memory without storage-dependent typing. A
shorter hexadecimal target preserves an exact Context first and otherwise
selects Memory only when one ordinary-local direct owner matches. A bare Memory
selector scans one strict snapshot of every ordinary local direct Context and
must have exactly one owner; a qualified selector searches only its canonical
owner. `--memory` explicitly types any short prefix, while `--context`
qualifies its owner or, without `--memory`, selects an explicit Context. All
Context locators, including `.`, `..`,
`./...`, and `../...`, resolve against one current-name snapshot captured at
command start.

Profile is deliberately explicit through `--profile`: `profile` is otherwise a
valid existing Context name and cannot safely participate in Context/Memory
shape classification. The former `context`, `memory`, and `profile` subcommand
forms remain compatibility routes. Consequently `mem lock profile` retains its
historical active-Profile meaning, while `mem lock --context profile` selects a
Context literally named `profile`.

Memory targets resolve only a directly owned `Memory`. Embedded Contexts,
`MemoryRef` pointers, and query-only references are not lockable as Memories.
`--direct` and `--recursive` are rejected for Memory and Profile targets before
protection metadata changes.

Lock and unlock are explicit, reversible policy changes and therefore do not
ask for an additional confirmation. Repeating the same operation is an
idempotent success. There is deliberately no `--force` mutation bypass: a
protected target must be explicitly unlocked first.

## Protection semantics

| Target | Blocked | Still allowed |
| --- | --- | --- |
| Context | Any change to that exact Context record, namespace rename that rewrites it, and deletion | Read commands, switching, checkpoint creation, using it as a read-only source, and branching to a new Context identity |
| Memory | Editing or removing that directly owned Memory occurrence, including whole-Context clear, deletion, revert, Undo, or Redo that would replace or remove it | Adding or changing other direct items and metadata-only Context rename |
| Profile | Durable writes anywhere inside the active Profile store, including new or changed Contexts, checkpoints, query-only sources, Ground/workflow sessions, and derived analyses | Reads, one-shot queries, current-Context switching, active-Profile switching, and protection policy changes |

A Context lock applies to one exact Context identity, not its lexical
descendants unless `--recursive` is supplied. Recursive mode freezes the root
and every existing ordinary Context whose canonical name begins with
`ROOT/`. The strict Context catalog, UIDs, and digests are revalidated while
an exclusive graph lock and all target locks are held, and the registry update
is atomic. It deliberately has snapshot semantics: a descendant created later
does not inherit the lock. This matches a recursive bulk operation and avoids
introducing a hidden namespace-policy language. Use the Profile lock when new
Contexts and future writes must also be blocked.

Context and Memory locks are independent. Unlocking a Context does not clear
its Memory locks. This preserves an intentionally narrower protection after a
temporary whole-Context freeze is lifted.

A Memory lock is keyed by `(Context UID, Memory UID)`. Branches retain Memory
UIDs for lineage and merge deduplication, but they receive a new Context UID;
therefore a lock does not silently make a branch copy read-only. This was
selected over a global Memory-UID lock because the current model treats branch
copies as independently editable occurrences. Namespace rename preserves the
Context UID, so its Memory locks follow the renamed Context without rewriting
the registry.

The protected Memory's serialized record and presence are invariant. Direct
item ordering belongs to the containing Context and remains mutable unless the
Context itself is locked. There is currently no public reorder command.

## Persistence and enforcement boundary

Protection state is stored per Profile in:

```text
write-protection.json
```

The schema contains one Profile-level boolean plus stable Context and Memory
identity keys. It does not copy Context names, Memory content, reasons, or user
identity. Keeping policy outside `context.json` avoids a circular design in
which unlocking a Context would require rewriting the protected record itself.
It also prevents a lock or unlock from changing Context digests, checkpoints,
or command history. Schema version 2 reads version-1 Context/Memory registries
as an unlocked Profile and upgrades them on the next policy change.

Registry updates are serialized by a dedicated `flock` file under the existing
transient `context-write-locks/` directory and published by same-directory
atomic replacement plus file and directory `fsync`. The lock order is:

```text
Context graph / command coordination when required
  -> affected Context write lock(s)
    -> write-protection registry lock
```

Lock and unlock capture the target Context UID and digest before entering the
store operation, then recheck both while holding the Context write lock. Every
ordinary save checks the persisted before/after Context records against the
current protection snapshot immediately before publication. Delete has a
separate guard because it removes the whole record. Namespace rename checks
every changed owner record, including moved Context headers and inbound
reference owners, while the complete graph lock set is held.

Profile locking is a persistent upper barrier, not an enumeration of current
Context UIDs. Profile-level Context commands serialize through the existing
global command lock. Non-Context artifacts hold the registry lock shared from
their final policy check through publication; `lock profile` takes it
exclusively. Therefore a write admitted under an older policy generation
cannot publish after `mem lock profile` has returned. Unlocking the Profile
changes only the upper boolean: explicit Context and Memory locks remain in
place.

This store-level boundary is intentional. Individual commands must not each
implement their own incomplete list of protected operations. Consequently,
direct edits, batch edits, semantic applications, merge, clear, restore,
Revert, Undo, and Redo all fail if their final Context record would cross a
lock. Typed protection failures are converted once at the root CLI group into
a terminal-safe `Error: ...` line rather than a Python traceback or
framework-owned Rich error panel. The root and command-local failures share
one line-oriented renderer so a protection failure does not change shape
according to which command happened to catch it first. Plain text remains the
complete channel; red is only supplemental terminal emphasis.

An invalid or unsafe protection registry fails closed for mutations. Read-only
Context inspection can continue because it does not need to open the policy
file. Removing the final policy removes the empty registry file.

## Profile boundary

The Profile target means the active Profile's durable store, not every global
control plane that can route to it. It freezes ordinary Contexts, checkpoints,
query-only sources, Ground/Meld/review/update/atomize sessions, translations,
comparisons and rationale caches. It also blocks new
Context identities, so it protects future names without requiring enumeration.

It does not prevent selecting a current Context or switching to another
Profile. Those pointers are navigation state needed to inspect or leave a
locked Profile. It also does not rewrite or revoke cross-Profile authority
grants in the global Profile registry; such revocation is an authority action,
not a content write inside the locked store. Profile import, replacement, and
administrative filesystem operations remain outside this cooperative command
policy and must retain their own explicit safety checks.

## Boundaries and non-goals

- Protection is cooperative application policy, not encryption, filesystem
  permissions, or defense against someone editing store files directly.
- A Context lock allows checkpoint creation because it records the current
  Context without changing it. A Profile lock blocks checkpoints because they
  are durable Profile writes. Restoring one remains subject to both policies.
- Switching the current Context changes Profile navigation state, not the
  protected Context record, and is allowed.
- Derived read-only analyses and Ground/session artifacts are not frozen by a
  Context lock unless applying them would change a protected Context; the
  Profile lock does freeze their durable saves.
- Version 2 has no lock owner, reason, expiry, `--all` alias, inherited subtree
  rule, or standalone lock-list command. Those require their own data and
  interaction contracts rather than optional fields with undefined
  enforcement.
- Query-only sources remain governed by their existing authority and privacy
  boundary; ordinary `mem lock` does not open or convert them.

## Operand alternatives considered

- **Keep resource-kind subcommands as the primary grammar:** rejected because
  Context and direct-Memory operands already have a shared, storage-independent
  classifier. Requiring `context` or `memory` only for protection made the same
  locator change meaning at the command boundary and prevented the ordinary
  `mem lock CONTEXT` form.
- **Resolve every nonempty target by searching both Context and Memory
  storage:** rejected because operand meaning would then depend on unrelated
  namespace occupancy. The shared UUID-shape and `CONTEXT:UID` grammar keeps
  classification deterministic before storage lookup.
- **Treat bare `profile` as part of automatic resource classification:**
  rejected because it collides with a valid Context name. `--profile` is the
  canonical explicit spelling; the bare word remains only as a compatibility
  command.
