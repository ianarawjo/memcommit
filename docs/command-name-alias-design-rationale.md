# Command-name alias design rationale

## Motivation

Users should not have to remember whether a multiword command contains a
hyphen or whether the object in a `find-*` command is singular or plural.
Those spelling differences do not change the operation, but unconstrained
normalization or fuzzy execution would be unsafe for a CLI that also exposes
mutating commands.

## Input contract

Canonical command names remain lowercase kebab-case and are the only names
shown by Help, completion, receipts, replay output, and the command-attempt
ledger. Every command group accepts the hyphen-omitted form of a registered
command, so `initstudy`, `checkconformance`, and nested forms such as
`profile archivestudy` resolve to their canonical commands.

The quality finders additionally accept these explicit grammatical aliases:

| Accepted input | Canonical operation |
| --- | --- |
| `find-redundancy`, `findredundancy` | `find-redundancies` |
| `find-duplicate`, `findduplicate` | `find-duplicates` |
| `find-ambiguity`, `findambiguity` | `find-ambiguities` |
| `find-conflict`, `findconflict` | `find-conflicts` |

An underscore is not a command separator, case is not normalized, and
operands and options are never rewritten. Unknown spellings may receive a
bounded canonical suggestion, but a fuzzy or prefix match never executes.

Resolution gives an exact registered command precedence, then considers the
shared hyphen-omission and explicit grammatical aliases. An alias executes
only when it has exactly one canonical target. A CI audit walks every root and
nested command group and rejects ambiguous alias projections.

## Identity and compatibility boundaries

Aliases are parser inputs, not registered operations. They therefore do not
create duplicate Help rows, completion entries, route classifications, or
evidence-ledger records. Click receives the canonical command name after
resolution, so command Help renders canonical usage and the root attempt
ledger records the canonical operation instead of the entered alias.

The shared Click routing implementation is owned by
`memcommit.interfaces.cli.command_group`. The historical
`memcommit.commands.command_group` import is a true module alias, rather than
a wrapper or copied export list. This preserves class and alias-map identity,
including legacy-path monkeypatches, while command adapters may import the
interface owner directly. The ownership move deliberately did not change
accepted spellings, collision handling, suggestion order, stderr text, exit
codes, or Typer/Click routing behavior.

The Profile group resolves a known command alias before applying its existing
`mem profile NAME` fallback. This keeps `mem profile archivestudy` attached to
`archive-study` while other unknown tokens retain their meaning as Profile
names.

The generated zsh integration recognizes both `init-study` and `initstudy`
before pushing an isolated Study history. Supporting the CLI alias must not
provide a route around that parent-shell privacy boundary. The `--help` form
of either spelling remains non-isolating.

## Rejected alternatives and limits

- Registering every alias as a hidden Typer command would duplicate routing
  metadata and make canonical operation recording depend on the entered form.
- General English singularization was rejected because names such as
  `contexts` and future commands do not necessarily have a safe inferred
  singular operation.
- Underscore normalization was deliberately excluded from the accepted input
  grammar.
- Fuzzy autocorrection and abbreviated-prefix execution were rejected because
  a close spelling is not authority to run a possibly mutating operation.
- `mem find redundancy` cannot be introduced as an alias because `mem find`
  already owns literal-search operands.
