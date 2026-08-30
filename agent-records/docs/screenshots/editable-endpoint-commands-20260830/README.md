# Editable Endpoint Setup commands · 2026-08-30

All images are actual prompt-toolkit PTY renders captured at `180×52` with
`TERM=xterm-256color`, `COLORTERM=truecolor`, 24-bit color enabled, and
`NO_COLOR` removed. Fixtures use process-local frozen catalogs, no Profile
Grant, and no Store. Every child verifies the live terminal size before its
screen opens. Returning an Endpoint Setup receipt starts no provider, session,
Context creation, publication, or final semantic Apply.

| Image | Fixture and preceding keys | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-update-entry` | Update `capture/source → capture/target`; none | unchanged WORKBENCH upper selectors and blue editable proposed command | none |
| `02-update-invalid-command` | `Tab×6`, replace arguments with `--from capture/target --to missing` | red invalid command; upper Source and Target remain unchanged | none |
| `03-update-command-reprojects-upper-fields` | replace arguments with `--from capture/target --to capture/source --source-descendants` | Source/Target swap and Source descendants update atomically while the command remains focused | none |
| `04-update-receipt-verification` | `Enter` | typed reversed Update setup receipt; provider and Store unchanged | none |
| `05-branch-entry` | Branch from `capture/alpha`; none | unchanged COMPACT upper rows and blue editable proposed command | none |
| `06-branch-command-reprojects-upper-fields` | `Tab×5`, replace arguments with `capture/beta/new-branch --from capture/beta --source-descendants` | Source, new Target, parent, and Source reach reproject together | none |
| `07-branch-receipt-verification` | `Enter` | typed Branch setup receipt; no Context created or switched | none |
| `08-meld-entry` | symmetric Meld fixture; none | Mode, A, B, C controls and editable proposed command | none |
| `09-meld-command-reprojects-upper-fields` | `Tab×9`, replace arguments with `capture/baseline capture/incoming --left-descendants` | Mode becomes directional, endpoints swap, C disappears, and A descendants updates | none |
| `10-meld-receipt-verification` | `Enter` | typed directional Meld setup receipt; no provider or session | none |
| `11-sever-entry` | Source `capture/source`, Criteria `capture/criteria`; none | three compact endpoint rows and editable proposed command | none |
| `12-sever-command-reprojects-upper-fields` | `Down×3`, replace arguments with `capture/criteria capture/source capture/result --criteria-descendants` | Source/Criteria swap, Result becomes new, and Criteria descendants updates | none |
| `13-sever-receipt-verification` | `Enter` | typed Sever setup receipt; no provider, session, or save | none |

The command prefix (`mem update`, `mem branch`, `mem meld`, or `mem sever`) is
fixed presentation outside the writable buffer. Printable keys, Backspace,
`Ctrl-U`, and paste edit only arguments. Invalid text stays visible and changes
no upper field; Enter reparses the current visible line and can run only while
that complete command is valid.
