# Checkpoint targeting and recursive-set design rationale

## Problem

`mem checkpoint` originally accepted at most one positional message and always
loaded the current Context directly. A person could therefore save
`mem checkpoint "baseline"`, but the otherwise natural command
`mem checkpoint task-1 "baseline"` failed with an unexpected-extra-argument
parser error. History commands already accept explicit existing-Context
locators, so requiring a temporary Context switch merely to append a manual
recovery point was unnecessary global-state churn.

The command also had no lexical-subtree form. Repeating one direct checkpoint
per descendant would expose partial history if a later append failed and would
not retain which Contexts belonged to the originally selected scope.

## Operand contract

Checkpoint preserves the established one-positional message form while adding
an arity- and option-disambiguated Context role:

| Form | Context | Message |
| --- | --- | --- |
| `mem checkpoint` | current | empty |
| `mem checkpoint MESSAGE` | current | positional |
| `mem checkpoint CONTEXT MESSAGE` | first positional | second positional |
| `mem checkpoint CONTEXT --message MESSAGE` | positional | named |
| `mem checkpoint --context CONTEXT MESSAGE` | named | positional |
| `mem checkpoint --context CONTEXT --message MESSAGE` | named | named |

`-c`/`--context`, `-m`/`--message`, `-d`/`--direct`, and
`-r`/`--recursive` expose both short and long spellings. When both named roles
are present, positional operands are rejected. A two-positional form combined
with either corresponding named role is likewise rejected instead of applying
an option-precedence rule.

Shell quotation is not semantic input: the shell removes quotation marks and
uses them only to retain a multi-word message as one argument. The command
classifies the resulting zero, one, or two argument values; it never guesses a
one-argument Context by checking whether that name happens to exist. Thus a
legacy `mem checkpoint task-1` remains a message for current, while a
message-less explicit target uses `mem checkpoint --context task-1`.

An explicit Context is an existing ordinary-local locator. The command captures
current once and resolves `.`/`..` spellings through the shared locator before
loading, checking, recording, or displaying the canonical target. Granted
public names are not manual-history targets because their authority checkpoint
history is a separate capability.

## Scope and persistence contract

Direct is the default; `--direct` makes that choice explicit. It appends one
ordinary manual checkpoint to the selected Context without changing Context
content.

Recursive checkpoint freezes the selected local root and every materialized
lexical descendant from one command-start local catalog. It deliberately does
not follow embedded Context edges: an embed is a graph relationship rather
than lexical ownership and may point outside the namespace or authority
boundary.

Every recursive member is loaded directly and carries its frozen UID and
content digest into one Store batch. Under the global command-order, Context
graph, and complete member-lock boundary, the Store revalidates catalog
membership and every Context before the first checkpoint append. An exception
during a later append removes every provisional checkpoint already written by
the batch. No Context bytes are rewritten.

Each recursive checkpoint remains manual (`auto: false`) and records the same
version-1 `checkpoint_set` metadata: one set UID, canonical root, recursive
scope, and complete Context UID/name membership. This retained membership
supports inspection and a future grouped restore contract without making the
no-content-change checkpoint set enter the Undo/Redo mutation stack.

## Alternatives and limitations

Changing the first positional operand unconditionally from MESSAGE to CONTEXT
was rejected because it would silently retarget existing scripts. Guessing by
Context existence was also rejected because creating or deleting an unrelated
Context could change the interpretation of the same command line. The selected
arity grammar adds the requested two-positional route while preserving stable
one-positional behavior.

Writing recursive checkpoints through repeated public `checkpoint` calls was
rejected because it would re-read and re-lock each member independently and
could publish a partial set. Reusing the Context-save batch was also rejected:
manual checkpointing changes history only, so rewriting identical Context
records or fabricating automatic mutation checkpoints would misstate the
operation.

Exception rollback is not a durable crash journal. A machine failure can still
interrupt several filesystem replacements. Recursive checkpointing also does
not currently make `mem revert` restore the complete set at once: each member
is an independently selectable recovery point, and Revert remains exact to one
Context. The common set metadata is retained for a later explicitly reviewed
multi-Context restore design; the current command receipt promises an atomic
history append, not an atomic future subtree restoration.
