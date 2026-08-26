# Runner isolation analysis

This note distills the execution bottleneck observed during the fixed
`study-long-audit-20260823` campaign. It describes a later runner; it does not
change the frozen boundary of the current campaign.

## What is parallel now

Each world worker launches a separate frozen CLI process. Provider turns from
different workers can therefore overlap; they are not intentionally routed
through one root-agent call queue. The provider cache lock in
`memcommit/semantic_provider.py` is process-local and protects provider
initialization, not a cross-process completion queue.

The participant Profile is nevertheless shared. Its Store implements different
lock widths:

- `context-write-locks/<digest>.lock` protects one canonical Context and permits
  unrelated Context writers to overlap.
- `context-command-write.lock` serializes the short publication boundary for
  checkpoint-producing commands because Undo/Redo reconstruct one Profile-wide
  command stack.
- `state-write.lock` protects the one current Context.
- `update-session-write.lock` protects the one active Update session.
- several operation session stores are Profile-owned even when their payload
  names explicit Contexts.

This explains why explicit disjoint Context work can run concurrently while
current, Undo/Redo, Update/Diff, Profile, provider configuration, and some saved
session routes cannot.

## Why registered Profiles alone do not fully isolate the CLI

The ordinary CLI resolves its default Store through the registry's single
`active_uid` (`memcommit/profile_config.py`). `mem profile use` changes that
global selection. Switching it before every command from six workers would
replace one Store bottleneck with a Profile-selection race.

The lower application boundary already demonstrates the missing shape:

- `MemCommitClient(profile=NAME)` freezes an explicit Profile Store without
  changing `active_uid`.
- `mem-mcp --profile NAME` exposes that process-pinned selection for the current
  agent-tool subset.

The public 66-operation CLI/TUI surface does not yet expose an equivalent root
option such as `mem --profile NAME OPERATION ...` or
`mem --store-root PATH OPERATION ...`. The MCP/agent-tool subset therefore
cannot substitute for this audit, which must exercise every public CLI
operation and its TUI where meaningful.

## Recommended two-lane campaign

### Lane A: isolated goal worlds

Create six Profile Stores from one identical baseline/Grant snapshot. Pin one
long-lived worker to each Store through an explicit process boundary rather than
mutating registry `active_uid`.

```text
one read-only code snapshot
|- task-1 Profile Store       <- one worker
|- task-2 Profile Store       <- one worker
|- task-3 Profile Store       <- one worker
|- ticker Profile Store       <- one worker
|- a-is-apple Profile Store   <- one worker
`- practice-source Profile    <- one worker
```

Each worker accumulates its own 66 operations x 5 methods = 330 attempts. Its
current Context, Undo/Redo cursor, command stack, Update session, operation
sessions, checkpoints, locks, and run logs are isolated. All workers retain the
same code digest, provider-policy digest, initial-store digest, Help catalog,
and evidence schema.

The runner must record the pinned Profile UID and resolved Store root in every
attempt and reject a command if either changes. A Profile or Store option must
be resolved once before application construction; it must not become a late
command-local override that leaves some adapters on the global active Profile.

### Lane B: shared-Profile concurrency stress

Full isolation would hide the defect class already observed in this campaign:
task-1/ticker Diff and Update consumed another world's saved applied Update.
Keep a smaller deliberate shared-Profile lane for operations whose contract is
supposed to isolate explicit endpoints or coordinate global state:

- Update, Diff, Review, Impact, and saved-session resume;
- current Context, Status, Switch, Checkout, Undo, and Redo;
- Profile and provider-route changes;
- simultaneous checkpoint-producing mutations to disjoint Contexts;
- simultaneous exact operations whose receipts must remain attributable to the
  correct world.

This lane should synchronize starts with barriers and assert both positive
ownership and absence of another world's identifiers/content. It is a focused
concurrency campaign, not the place to collect all 1,980 goal attempts.

## Why the current run should not migrate mid-phase

The six worlds have already accumulated different histories inside one fixed
Study. Copying the Store while provider turns or commands are in flight would
produce different handoff moments, duplicate unrelated world state into every
clone, and change the exact concurrency condition that produced the saved-state
bleed. It would also have split the evidence boundary after collection had
already crossed 1,110 verified attempts. The current provisional report now
records 1,350 attempts and 270/396 operation-world units; the historical
handoff reason is unchanged.

Finish the current shared-Profile campaign as declared. Use the isolated runner
from the start of a fresh campaign, and retain Lane B so the speed improvement
does not erase cross-world isolation coverage.
