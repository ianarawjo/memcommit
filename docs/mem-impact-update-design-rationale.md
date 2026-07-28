# `mem impact` and `mem update`

## Intent

These commands express a directional semantic operation:

```text
update target Context B from current Context A
```

Context A is verified evidence. Context B is the working target. This is not a
symmetric merge and it is not a command for manually replacing one Memory by
UID.

## Usage

```bash
mem switch construction-updates
mem impact --to campus-wiki
mem update --to campus-wiki
```

`impact` plans and previews the edits and additions that would make B reflect
A. It does not change either Context. The validated plan is cached locally so
an immediately following `update` can reuse exactly what the participant
reviewed.

`update` stages that validated plan locally. It still does not modify B.
`mem diff` renders the same staged operations as a deterministic unified diff.
A future `mem push` can verify the recorded base state before applying or
contributing them.

If the cached impact plan is stale because A or B changed, `update` plans again
instead of promoting stale operations. Running `update` repeatedly with the
same A and B is idempotent. A different staged update is preserved unless the
participant explicitly supplies `--replace-stage`.

## Method

Both commands use one planner:

1. Recursively visit explicitly embedded Contexts in A and B.
2. Treat directly owned `Memory` values in B as writable.
3. Treat resolved `MemoryRef` values in A as readable evidence.
4. Never open `QueryContextRef` sources and never edit `MemoryRef` values.
5. Give a temporary Codex process only per-run candidate IDs and visible text.
6. Require strict JSON containing full-content edits and additions.
7. Map every returned ID back to canonical local objects and reject unknown,
   duplicate, empty, or unsupported operations.
8. Generate new Memory UUIDs locally and record source provenance plus source
   and target fingerprints.

An edit preserves the target Memory UID and replaces its string content with a
complete revised version. The planner must preserve unrelated target facts. An
addition receives a new local UUID and names its owning target Context.

## Diff

```bash
mem diff
mem diff --raw
mem diff --stat
mem diff --verbose
```

`diff` makes no model or network call. Its default semantic view uses yellow
operation headings, red deleted text, green added text, dim unchanged lines,
and cyan provenance. It shows collision-safe short UID prefixes and hides
low-level Git headers and terminal-newline markers. `--verbose` shows complete
UIDs and the source/target fingerprints.

`--raw` renders the exact Git-style `---`, `+++`, and `@@` representation,
including additions from `/dev/null` and terminal-newline markers. `--stat`
shows only the edit/addition counts. Raw and stat modes are mutually exclusive.

Every detailed mode prints each operation's source provenance and reason. The
command does not depend on the currently selected Context and it does not write
Contexts, checkpoints, state, or session files.

Before rendering, the command reloads the recorded A and B Context graphs. If
their identities or planner-visible contents changed after staging, the
captured diff is still shown but marked stale and the command exits with a
failure status. A future push must refuse that stale stage.

## Local artifacts

```text
~/.mem/impact-plan.json
~/.mem/staged-update.json
```

These files contain canonical operation records, owner Context identities,
old and new content, provenance hashes, and source/target fingerprints. They
are written atomically. Context JSON and checkpoints are not modified by
either command.

This is a research-prototype trust boundary, not remote collaboration or an
access-control system. A later push implementation must reload every owner
Context, verify the recorded identities and base fingerprints, and perform a
full preflight before writing any Context.
