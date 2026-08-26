# Granted direct-Memory `mem embed` capture log

This ordered set records the actual color-preserving TUI path from an explicit
`READ + EMBED` public Memory Source into one owned local Target. All Stores and
Profile records are disposable; no user Context is changed.

## Reproduction

- Command: `mem embed`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, verified inside the child process
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Active Profile/current Context: authoring Profile / owned local `guide`
- Source: public `advisor`, backed by authority Context `private-advice`
- Source permissions: exact same Grant supplies `READ + EMBED`
- Target: local-only `guide`, containing two owned marker Memories
- Renderer: cumulative ANSI PTY streams replayed with `pyte`; `.typescript`,
  `.txt`, and `.png` are retained for every state

```bash
env -u NO_COLOR TERM=xterm-256color COLORTERM=truecolor \
  python agent-records/screenshots/granted-memory-embed-20260823/capture.py
```

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable effect |
| --- | --- | --- | --- |
| `01-entry.png` | Launch | Embed opens in Context mode with the owned Target and public Grant namespace frozen. | None |
| `02-memory-mode.png` | Right | Link type changes to direct Memory; local `guide` remains the initial Source preview. | None |
| `03-granted-source.png` | Tab, Up, Enter | Public `advisor` is opened as a Memory Source and visibly annotated `GRANT · READ · EMBED`. | None |
| `04-granted-memory-focus.png` | Down | Focus moves from the public Context row to its exact authority-owned Memory. | None |
| `05-granted-memory-selected.png` | Enter | The exact direct Memory is staged while ownership remains with public Source `advisor`. | None |
| `06-local-target.png` | Tab | Focus moves to owned local `guide`; the granted Source never appears in the Into catalog. | None |
| `07-gap-staged.png` | Tab, Up, Enter | The gap between the two owned Target markers is staged. | None |
| `08-exact-qualified-command.png` | Tab | Review shows `mem embed advisor:UID --into guide --before UID`; the granted Memory is owner-qualified and no bare-UID scan is implied. | None |
| `09-success-receipt.png` | Enter | CLI receipt confirms one live Memory link at the reviewed gap. | One local Target checkpoint with Grant provenance. |
| `10-live-read-only-verification.png` | Enter at capture pause | After the authority changes the same Memory UID, `mem ls -R guide` reads the updated value through the stored link. | Authority test fixture updated; local Target unchanged after Embed. |
| `11-content-free-link-receipt.png` | Enter at link pause | Raw local record reports `granted_memory_ref`, matching Grant identity, and `LINK CONTENT CACHED · NO`. | None. |
