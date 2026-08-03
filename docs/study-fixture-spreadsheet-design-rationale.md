# Bilingual study-fixture spreadsheet design rationale

## Problem

The study fixtures are reviewed in a spreadsheet, but the spreadsheet must
not become an independent source of truth. The runtime also needs English
canonical Memory content and an editable Korean rendering without allocating
a second Memory UID. Earlier workbook drafts contained fewer rows than the
current fixture corpus, so copying one of them would silently restore obsolete
content and counts.

## Selected design

The workbook is rebuilt from the same strict parser used by the `.mem` bundle
builder. It contains two adjacent review tabs for each of the nine datasets,
plus Korean and English overview tabs: 20 tabs in total. English and Korean
rows are joined by fixture ID or canonical locator before any workbook is
created. A failed identity, purpose, audience, or review-state match stops the
build instead of aligning rows by position.

Every data tab uses a compact two-row structure:

1. one title row with task, Context, count, and reviewed count;
2. one filterable header row followed immediately by Memory candidates.

All cells wrap naturally. The first row and header remain compact, while data
rows may grow enough to show their text. The workbook keeps a deliberately
neutral visual language; the only semantic colors are pale red for a Task 1
baseline value and pale green for its proposed replacement. This preserves
the requested diff cue without assigning decorative colors to tasks or Memory
purposes.

## Review metadata

`Verified`, Task 1 audience checks, purpose codes, update patches, Task 2
relationship bands, storage boundary, and source filename are designer
sidecars. They never enter a Memory's `content`. Checkbox columns are native
Google Sheets checkboxes after import, so a reviewer can mark progress without
editing the Memory body.

`Verified` does not cross the language boundary automatically. A checked
Korean source row can establish that the Korean fixture was reviewed, but it
does not by itself prove that the English translation is equivalent. Runtime
Korean translation catalogs are therefore imported as `UNREVIEWED` until the
translation itself is explicitly verified.

Task 1 audience checks express intended disclosure only. The current
prototype has no per-Memory role ACL, so the workbook and package manifest
must not present those checks as enforcement. Query-only datasets instead use
the existing Context-wide concealment boundary and remain available only
through `mem query`.

## Runtime identity

The English and Korean spreadsheet rows are review projections of one logical
fixture. The bundle builder allocates one deterministic Memory UID for each
ordinary pair, stores English in `Memory.content`, and attaches Korean as an
imported same-UID translation catalog entry. Query-only pairs receive one
deterministic concealed entry UID with English canonical text and a Korean
language variant.

This makes a correction to Korean a translation-view edit rather than a
branch, copied Context, or second Memory. Source-content hashes prevent a
translation reviewed against an older English body from appearing current.

## Creation and verification

The local `.xlsx` is produced with the workspace spreadsheet runtime, checked
for formula errors, and rendered across all 20 tabs before it is imported as a
new native Google Sheet. The imported Sheet is read back by metadata and
bounded cell ranges, and checkbox validation is applied using stable sheet
IDs. The older Korean-only workbook is retained only as historical output and
is not used as a data source.

## Limitations and non-goals

- The spreadsheet is a review and editing surface, not a transactional Memory
  store. Changes made in Google Sheets are not automatically imported.
- Translation review is per exact source hash; it is not semantic proof.
- Query-only concealment is a research UI boundary, not a security or legal
  access-control claim.
- Audience columns do not authorize a reader or filter `mem ls`/`mem show`.
- Automatic bidirectional spreadsheet synchronization and role-aware ACLs are
  intentionally outside this fixture-building change.
