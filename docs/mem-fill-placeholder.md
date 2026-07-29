# Future `mem fill` placeholder

Status: design only. No `mem fill` command or saved fill-plan format is
implemented.

## Intended meaning

`fill` will compare a target Context with an explicit request, template, or
set of coverage requirements. It will use a separate verified source Context
as evidence for proposed additions or edits.

The operation is intended to answer both:

- which requested parts the target already covers; and
- which requested parts can be filled, remain unsupported, or are blocked by
  ambiguous or conflicting evidence.

`fill` must not treat a requirement as a fact or invent a value merely to make
the target appear complete.

## Illustrative command shape

The following syntax is only a design example:

```bash
mem impact fill \
  --from temp/task-1-atomized \
  --against task-1/fill-guide

mem fill --save
```

The current Context would be the target. A future coverage plan could classify
each requirement as already covered, partially covered, fillable from cited
source Memories, unsupported by the available source, or blocked by
ambiguity/conflict. Any proposed edit or addition would cite both the
requirement and the source Memories that support it.

## Boundary with other operations

- `add` stores supplied content without semantic completion.
- `update` transfers supported differences from one Context to another but
  cannot identify a requirement missing from both.
- `place` is the proposed operation for assigning an existing Memory to an
  organizational Context.
- `fill` is requirement-driven coverage and evidence-backed completion.
- `ground` is the separate interactive process for jointly establishing rules,
  reviewed cases, and decisions. `induct` is its narrower rule-proposal step.

The first safe implementation should preview before mutation, bind a plan to
the requirement, source, and target fingerprints, keep query-only sources
opaque, and apply to one writable Context at a time. Detailed implementation
and interaction design are intentionally deferred.
