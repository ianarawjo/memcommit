# Context locator suggestions: design rationale

## Problem

An existing-Context operand can be classified correctly as a Context and still
fail exact lookup because of a small spelling error. The command-name router
already made that failure recoverable with `Did you mean?`, but Context-aware
commands returned only a not-found error. Command-local fuzzy matching would
make ranking and safety behavior drift between automatic target classifiers.

## Contract

`resolve_context_locator` remains a pure canonical lexical resolver. After an
operation has proven that exact Context interpretation failed, it may call
`suggest_context_locators` with the frozen command-start current Context and
the exact Context catalog already authorized for that operation. Suggestions
use the same conservative similarity ranking as command-name diagnostics,
return at most three canonical names, and are display-only. They never load,
select, execute against, or persist a similar Context.

Relative input is resolved against the frozen current Context before ranking,
so `./rulse` can suggest `practice/rules` without changing meaning if the
global current Context moves later. Bare names remain global. The caller still
owns whether its catalog is ordinary-local, selected-readable, or
Profile-readable; suggestion breadth must never reveal a name outside that
operation's already visible namespace.

## Initial rollout and boundary

The overloaded Diff Context/checkpoint resolver is the first consumer because
its exact failure previously obscured an otherwise recoverable Context typo.
The helper is operation-neutral so other existing-Context failure paths can
adopt it without copying the algorithm. Memory UIDs, provider output, new
Context identifiers, and exact checkpoint lookup are intentional non-goals.
