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

The first recursive implementation did retain that membership, but printed a
new receipt-only set UID instead of any physical checkpoint UID. Revert searched
only the selected Context's physical checkpoint UIDs, so the successful receipt
could not be reused: a displayed set such as `777af68d` failed while separately
rediscovered member checkpoint UIDs worked. Treating that set UID as a second
user-visible selector kind would duplicate the Profile-wide checkpoint lookup
contract and leave History, Diff, and Revert with different identity rules.

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

Each recursive checkpoint remains manual (`auto: false`). Before publication,
Checkpoint plans one physical checkpoint UID per member. Version-2
`checkpoint_set` metadata records the root Context identity, recursive scope,
and every Context UID/name/checkpoint-UID mapping. The root's physical
checkpoint UID is also the canonical recovery-unit UID; the command does not
mint a receipt-only identity beside the global checkpoint catalog. The success
receipt prints that real UID and a directly executable Revert command.

The no-content-change checkpoint set still does not enter the Undo/Redo mutation
stack. Its shared command identity is nevertheless visible to common History
and location projections, so one recursive command is not counted as unrelated
per-Context checkpoint commands.

## Global resolution and grouped Revert

One command-local `CheckpointCatalog` freezes every ordinary local Context and
its retained history. A UID-like explicit Revert selector first prefers the
command-start current Context so inherited Branch behavior remains compatible;
if that location has no match, it resolves the unique directly owned checkpoint
across the Profile. An explicit `--context` remains an exact location constraint.
Natural-language selection stays scoped to its selected Context.

The catalog returns one typed recovery unit rather than making Revert inspect
raw `checkpoint_set` arguments. An ordinary checkpoint produces one member. A
version-2 recursive member UID produces the complete manifest, including when a
child member UID was selected. Version-1 receipt-only set UIDs remain read-only
catalog aliases: the catalog locates the corresponding member records, validates
their identical retained membership, and canonicalizes the unit to the root's
real physical checkpoint UID. New receipts never create that legacy alias form.

Revert freezes every affected Context in its exact-command review and renders
each Context/member checkpoint in the Viewer before Apply. Apply holds the
global command-order lock, shared Context-graph lock, and all member write locks
in deterministic order. It revalidates every current Context digest, history
digest, physical checkpoint, and manifest before the first write. Each member
retains the ordinary pre-Revert recovery checkpoint and `--keep` versus
`--discard-newer` behavior. An outer byte-for-byte Context/history rollback
restores all previously written members if any later member fails.

All pre-Revert checkpoints share one typed Revert receipt and complete
`command_contexts` membership. Global command history therefore groups the
result as one command unit: one `mem undo` or `mem redo` restores every member
rather than consuming the Revert one Context at a time.

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
interrupt several filesystem replacements. Grouped Revert restores the recorded
member Contexts only: it does not delete descendants created after the
checkpoint or recreate a member whose Context identity was deleted. A missing,
recreated, incomplete, or inconsistent member fails the whole operation before
publication. Rename is tolerated when the same Context UID has one unambiguous
current ordinary owner. An inherited recursive checkpoint is not allowed to
retarget its Source unit through a Branch copy; it fails closed until an
explicit cross-lineage group-mapping contract exists.
