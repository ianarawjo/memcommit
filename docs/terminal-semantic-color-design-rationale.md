# Shared terminal semantic color design rationale

## Problem

Terminal presentation historically owned color at the individual command or
screen. The interactive semantic Viewer used ADD blue, EDIT green, and REMOVE
red, while line-oriented Diff and restoration receipts used different colors
for the same labels. `mem log` printed automatic command rows without action
color, and source rows could show GRANT and permissions through another local
palette. A person therefore could not reuse color as a stable scanning aid
across retained history, current review, and authority orientation.

The current command refactor also makes presentation boundaries important.
`mem log` is now one terminal-independent report; Diff, Revert, and saved
Update retain checkpoint-oriented History surfaces; and interactive Trace uses
one continuous read-only lineage document after its Memory is known. A shared
palette must not reverse those separations or make terminal capability select a
different command flow.

## Contract

`memcommit.interfaces.console.theme` is the sole authored palette and semantic
classification source. It has no Typer or prompt-toolkit dependency. Console
adapters translate a semantic role to a Click-compatible RGB tuple; TUI themes
translate the same role to one prompt-toolkit class.

The stable role mapping is:

| Semantic role | Visible examples | Foreground |
| --- | --- | --- |
| CREATE | `create`, `init`, `branch`, `CREATED` | blue `#8aadf4` |
| ADD | `add`, `ADD`, `ADDED`, `SURVIVOR(S)` | blue `#8aadf4` |
| EMBED | `embed`, `VIA EMBED`, embedded Context kind | yellow `#eed49f` |
| EDIT | `edit`, `replace`, `EDITED` | green `#a6da95` |
| REMOVE | `remove`, `delete`, `clear`, `REMOVED`, `ABSORB(ED)` | red `#ed8796` |
| UNDO | `undo`, `revert`, `RESTORED` | peach `#f5a97f` |
| REDO | `redo` | lavender `#b7bdf8` |
| HISTORY | manual checkpoint and historical-version kind | brown `#c9ad93` |
| GRANT | Grant ownership marker | neutral white `#f4f5f7` |
| NAVIGATION_GRANT | Switch Context-category `GRANT` marker | green `#a6da95` |
| CAPABILITY | READ/QUERY/EDIT capability cluster | teal `#8bd5ca` |
| REFERENCE | durable Reference kind | mauve `#c6a0f6` |
| JUDGMENT_YES | semantic judgment `YES` | green `#a6da95` |
| JUDGMENT_MAY | semantic judgment `MAY` | yellow `#eed49f` |
| JUDGMENT_NO | semantic judgment `NO` | red `#ed8796` |

CREATE and ADD deliberately share a constructive family. Their explicit text
continues to distinguish lifecycle creation from adding one direct item. A new
hue is not assigned to every command because the number of operations exceeds
the reliably distinguishable palette and color is never the only information
channel.

Mixed operations such as Update, Meld, and Atomize remain neutral at the
top-level command label unless their own model proves one disposition. Their
typed child effects carry ADD, EDIT, or REMOVE colors. This avoids presenting a
mixed Update as an edit merely because EDIT happened to be its historical
default color.

Fit judgments use separate `JUDGMENT_YES`, `JUDGMENT_MAY`, and `JUDGMENT_NO`
roles even though their hues intentionally reuse green, yellow, and red.
Compatibility is not an EDIT, EMBED, or REMOVE action, so the shared
classifier preserves that distinction instead of borrowing an action role.
Only the exact `YES`, `MAY`, or `NO` token is colored. `FIT`, punctuation,
operand labels, Ground and Context names, counts, relation marks, and Memory
bodies remain neutral. `STALE` and legacy `N/A` remain explicit neutral text
until their meanings receive separately reviewed semantic roles.

Compact quality issue rows likewise classify their typed category before
rendering. Only `DUPLICATE`/`REDUNDANT`, `AMBIGUOUS`, or `CONFLICT` receives its
shared quality role: lavender for redundancy evidence, yellow for ambiguity,
and red for conflict. The `WHY` token has a separate soft-Sky `RATIONALE` role.
It deliberately does not reuse the brighter focus blue, because explanatory
structure must remain distinguishable from the keyboard target. Relation
values, Context and Memory references, punctuation, and rationale prose remain
neutral; individual Memory bodies retain the shared Memory lavender. Focus
temporarily overrides the complete active row.

Read-only Duplicate and Redundancy cleanup maps use the same child-disposition
rule without implying execution. `SURVIVOR` is ADD blue because that existing
member remains in the proposed resulting set; `ABSORB` is REMOVE red because
that member would leave it. Only those two tokens are colored. Find
Redundancies keeps the adjacent `PROPOSED · NOT APPLIED` boundary; provider-free
Find Duplicates keeps its read-only/non-applying boundary in the command footer
so a two-member exact group can remain exactly two self-contained member rows.
The colors classify result-set membership, not a completed storage mutation.
Applied Dedun Review preserves those roles as typed report fragments, so both
the immediate Find projections and the later checkpoint snapshot color the
same shortest tokens without parsing report text. Legacy plain Dedun plans and
receipts likewise color `RECOMMENDED SURVIVOR`/`SURVIVORS` as ADD and
`ABSORBED` as REMOVE; surrounding UIDs, counts, and evidence remain neutral.

Only the shortest trusted semantic token is tinted. Timestamps, UIDs,
descriptions, report chrome, explanatory prose, and Memory bodies remain
neutral or retain the Memory-object lavender. A focused History row uses the
common focus treatment across the complete row; focus therefore overrides its
unfocused action color instead of presenting two active visual states.

Typed Source relationship rows use the same rule. List and Show classify
`MEMORY_EMBED`/legacy live `MEMORY_REF` as EMBED and immutable Memory or Context
Reference forms as REFERENCE before rendering. Only the relationship noun is
colored; the relationship UID, `[Context][memory UID]` Source identity, content,
and `READ ONLY` state are not inferred from or absorbed into that color.

Grant ownership and available capability are independent roles. Source
projection in operation workbenches and static authority reports keeps the
`GRANT` ownership identity neutral and bold, while a `READ + EDIT` capability
cluster carries teal. The Switch Context picker has a narrower categorical
scan contract established by the current navigation refactor: only `GRANT`,
`VIA EMBED`, and `QUERY ONLY` are colored, so its `GRANT` marker uses the
separate green `NAVIGATION_GRANT` role and its name and compact capability
summary stay neutral. Both variants resolve through the same palette module;
neither screen owns a raw green value.

The exact stored permission atoms remain authoritative. Color does not grant
access and does not collapse CREATE and UPDATE authority into a new persisted
EDIT permission.

## Plain and interactive adapters

`mem log` and Fit retain identical line structure in terminals and pipes. Typer may
emit semantic foreground escapes for a color-capable terminal, but stripping
ANSI yields the same report as `--plain`. The presence of color never opens a
picker or changes the selected Context.

The Fit CLI consumes typed receipt segments, so its adapter styles the
judgment field without reparsing report prose. A color-capable TTY shows
`YES`, `MAY`, and `NO` through the shared judgment roles; `--plain`, a pipe,
or `NO_COLOR` emits the exact same receipt with no ANSI styling.

The shared History picker colors only the unfocused command column. Checkpoint,
restore, and saved-Update details color action and child-effect tokens through
the same classifier. Mechanical before/after Memory diff spans retain their
separate directional contract: removed text is red, new text is green, and
unchanged body text is white. An ADD action can consequently have a blue label
and green newly present content without conflating operation identity with a
textual diff direction.

Trace composes the same palette without inheriting the checkpoint picker's
two-surface topology. Each operation begins with the same adapter-neutral
History row segments consumed by static Log: the action token uses its semantic
role, Memory badges use lavender, receipt badges use retained-history brown,
and source badges remain neutral bold. Timestamps, summaries, evidence labels,
and report chrome remain neutral. Compact direct Add/Remove stop at that colored
Log row; Edit, restoration, and structural or mixed commands append their diff.
Direct Edit leaves its generic summary empty so the colored action token and
the red/green diff do not repeat the same claim in prose.
Verbose Trace expands every diff and adds the typed effect/evidence line without
restating the Log row format in a second renderer. Inline `−` and
`+` markers carry REMOVE plus the proven after-side ADD, EDIT, or restoration
role, while the Memory text beside them stays lavender. A mixed Atomize or
Update command remains neutral even when its lineage block contains colored
child effects. The ANSI-free TUI projection and `--plain` output retain the
same markers, labels, ordering, bounds, and omitted-operation count.

## Alternatives considered

- Giving every command a unique hue was rejected because colors would become
  difficult to distinguish and would not generalize to new or mixed commands.
- Reusing red/green alone for undo and redo was rejected because restoration
  direction is not intrinsically destructive or successful. Their temporal
  roles use peach and lavender, while actual restored effects remain explicit.
- Parsing rendered strings such as `UPDATE · EDIT` or `FIT · NO` was rejected because wording
  and localization would then control semantics. Adapters receive typed command
  or effect labels and resolve only registered aliases. Source rows likewise
  classify `SourceDisplayFacts` rather than parsing `embedded` or `reference`.
- Putting palette constants in the TUI theme was rejected because the static
  CLI would either depend on prompt-toolkit or duplicate the values.

## Boundaries and limitations

This contract covers semantic action, judgment, history, Grant/capability, and
Reference colors. It does not migrate every legacy success, error, loading,
analysis, or provider-status color in one change. Those roles may join the
common palette later only after their meanings are classified.

Color is presentation evidence, not operation evidence. It cannot authorize a
command, prove a checkpoint disposition, alter history reconstruction, or
change a Grant. Labels and symbols remain required so `NO_COLOR`, pipes,
screen-reader-oriented text, and limited terminals preserve the complete
meaning.
