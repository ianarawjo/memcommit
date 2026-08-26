# Isolated memcommit study profile packages

Each `task-N/` directory contains two complete stores below `profiles/`: the
participant task profile and its switchable task-specific authority profile.
The task manifest declares authority-owned grant templates that the importer
binds only after allocating both local Profile UIDs. Do not merge or copy
authority Contexts into the task store.

All fixture data, including material exposed through a QUERY grant, is stored
as ordinary authority-owned Contexts. English is canonical Memory content and
Korean is attached to the same Memory UID as an unreviewed imported
translation view. A task profile sees only the READ, CREATE, UPDATE, or QUERY
views declared in its grant templates; study QUERY views also grant explicit
SESSION_LOG retention for named visible Q/A transcripts.
Audience annotations remain review metadata and are not automatically
interpreted as ACL rules.

Run `mem profile import-study` once to compose a clean editable
`study-baseline` Profile without authoring checkpoints or run artifacts. Its
`task-N` branches contain participant starting state and its
`granted-memory/task-N` branches contain authority source material. Refine that
single live Profile, then use `mem init-study NAME` to snapshot its current
state into one ordinary Profile with the complete topology unchanged. The
legacy `~/.mem` remains the `authoring` profile and package sources are never
edited in place.
