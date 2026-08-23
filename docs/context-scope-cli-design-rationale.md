# Context-scope CLI presets

## Decision

Context-scope commands use two common convenience presets:

```text
-d, --direct
-r, --recursive
```

`DIRECT` selects the narrow operation-supported scope. `RECURSIVE` selects the
broad operation-supported scope. Direct is the default for a newly migrated
plain CLI route. The presets are input conveniences; cache, receipt, session,
provider, and Apply code continues to persist the operation's precise typed
scope fields rather than the spelling of the flag.

Last reviewed: 2026-08-20.

## Motivation

Before this decision, scope grammar varied by command. `mem list` used `-R`,
lock and unlock used `-r`, Summarize exposed only `--direct`, Find exposed
unshortened independent flags, and multi-frame operations exposed only
role-qualified descendant flags. Summarize also labelled embedded traversal as
`RECURSIVE` without expanding lexical descendants, so a namespace parent could
produce an empty result while `mem list -R` showed populated descendants.

The common presets make the ordinary narrow and broad requests easy to type
and visible in help while retaining the precise controls needed by operations
with multiple roles or independent traversal axes.

## Command contract

- `-d/--direct` and `-r/--recursive` are mutually exclusive.
- On a one-shot route, supplying either preset makes the read boundary
  explicit. An operation may also use it to seed equivalent, visibly selected
  TUI controls, as Find does; otherwise a TUI-owned setup rejects the flag
  instead of applying hidden scope. Scope alone does not authorize an
  operation to reinterpret a saved session.
- Every multi-role route exposes the same canonical role pair:
  `--<role>-descendants/--<role>-root-only`. A role-qualified flag refines
  that role after the common preset, so `mem update -r --target-root-only` is
  an order-independent request for a recursive Source and exact Target.
  Existing `--<role>-only` spellings remain accepted as compatibility aliases
  for `--<role>-root-only`, but new help, receipts, and replay output use the
  canonical pair.
- An independent axis such as `--exclude-embeds` refines only that axis. It
  does not silently change lexical descendant reach.
- Existing `-R` remains an alias for recursive `mem list`/`mem ls` behavior
  because it is an established Unix-style spelling.
- Lowercase `-r` is reserved across the public CLI for the recursive scope
  preset. Elaborate therefore exposes repeatable rules as `--rule` only; a
  short alias there would make the same token mean unrelated concepts.
- Commands whose semantic invariant is intentionally direct-only—Atomize,
  whole-frame Forget, and the semantic quality operations (`dedun`,
  `find-ambiguities`, and `find-conflicts`)—do not advertise `-r`; accepting a
  flag must mean the operation can actually execute that scope. The Atomize
  branch of `impact` rejects the common flags even though directional Update
  Impact supports them.
- A shared parser may host several resource kinds, but presets remain valid
  only for kinds with Context scope. Context import accepts them; Profile and
  Memory import reject them. Replays such as `list --paste` also reject both
  presets because their scope is already frozen in the copied receipt.
- A bare command may launch its saved-session browser or setup TUI. Operations
  with incomplete explicit endpoints fail rather than falling back to a saved
  session browser. Scope flags apply only to a new request or to visible setup
  controls and never rewrite a persisted session.

## Operation mapping

Single-scope operations map the presets to their typed scope. Operations with
independent lexical and embedded traversal map `DIRECT` to both axes false and
`RECURSIVE` to both axes true, unless an explicit axis flag overrides one.
Multi-role operations apply the preset to every role and then apply explicit
role overrides. Operations such as lock or Grant creation that have no
embedded traversal map only the lexical descendant value.

Summarize must not map `RECURSIVE` to its former embedded-only boolean. It must
freeze every readable lexical descendant and follow permitted embedded edges,
deduplicate Context identities, and revalidate the same precise scope before
publishing the result. Its frozen public namespace therefore combines ordinary
local names with effectively READ-granted public names and retains the exact
Grant binding for every selected granted name. Direct must open only the
selected Context record.

| Command family | `-d` mapping | `-r` mapping | More precise controls |
| --- | --- | --- | --- |
| `list` / `ls` | selected Context | existing recursive listing | `-R` remains a compatibility alias |
| `show` | selected Context or direct item | readable lexical descendants and embedded Contexts | recursive scope rejects the direct-item selector |
| `branch` / `checkout -b` | Source root | Source lexical subtree | `--source-root-only` / `--source-descendants` (`--source-only` is compatible) |
| `import context` | Source root | Source lexical subtree | presets are rejected for Profile and Memory import |
| `lock` / `unlock` (current or `context`) | selected Context | frozen lexical namespace | Memory and Profile subcommands have no scope choice |
| `profile grant create` | resource root | frozen resource subtree | none |
| `profile grant update` | replace with root | refreeze current subtree | omission preserves the existing frozen scope |
| `find` / ordinary `query` / `summarize` | both traversal axes false | lexical descendants and embedded traversal | operation-specific axis flags override the preset |
| `find-duplicates` / `dedup` | one exact direct Context | each lexical Context in the frozen subtree, judged independently | recursive Dedup remains within one local Store and never follows embeds |
| `compare` / `meld` / `update` / `sever` | every endpoint root | every endpoint subtree | role-qualified long flags override individual endpoints |
| directional Update `impact` | both endpoint roots | both endpoint subtrees | role-qualified flags; saved-session and Atomize routes reject presets |

Atomize, Forget, and the semantic quality finders remain direct-only rather
than recognizing a recursive option that has no executable meaning. Exact
Find Duplicates and Dedup are different: they can enumerate a lexical subtree
without changing the direct, role-aware identity frame used for each Context.

## Safety and compatibility boundaries

Changing a default can change provider disclosure, cache identity, receipt
selection, and durable results. Each operation therefore receives focused
tests for its default, both presets, explicit overrides, authority boundary,
and persisted scope. Existing session schemas remain unchanged; adapters map
the new input spelling to existing fields.

Canonical replay output must not perpetuate compatibility aliases. Restoration
commands therefore emit `--source-root-only` and `--criteria-root-only` even
though older copied commands using `--source-only` or `--criteria-only` remain
valid input.

TUI controls do not execute CLI commands. They map their visible exact/subtree
and embed choices to the same typed application fields. A TUI default is
changed only with its required interaction captures and compatibility review;
adding CLI aliases alone is not evidence that an interactive default changed.

## Rejected alternatives

- `-d` for descendants was rejected because it would make the paired
  `-d/-r` grammar name two broad scopes and leave no mnemonic for the narrow
  direct request.
- `-c` for Context-only was rejected because `-c` already selects Contexts or
  commands across many public routes.
- Treating `recursive` as one universal storage traversal was rejected because
  lexical descendants and embedded Context edges are independent axes.
- Adding `-r` to direct-only operations was rejected because a recognized flag
  that cannot change the executable frame is misleading.
- Binding `-d` or `-r` to the nearest positional operand was rejected because
  option order would change meaning and paired endpoints would become hard to
  audit. Presets always apply to every input role, then explicit role flags
  override individual roles. Meld's `--to` names its result location and is
  not an input-scope role.

## Remaining limits

Role-qualified short aliases are intentionally not introduced. `-r` applies a
common broad preset and the canonical long role flags express mixed scopes.
Operation-specific TUI defaults and persisted-session compatibility are
reviewed separately as their operation slices are migrated.
