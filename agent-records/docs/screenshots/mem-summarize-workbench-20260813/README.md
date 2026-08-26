# Summarize picker-first workbench capture log

> Superseded by the Run-first, three-way range, dual-result evidence under
> `mem-summarize-both-workbench-20260813/`.

This ordered set records the Summarize TUI after Context selection and
descendant reach became explicit controls above the read-only Summary. It
supersedes the completed-result-only interaction recorded in
`mem-summarize-tui-20260813/`.

## Reproduction frame

- Command: `python agent-records/docs/screenshots/mem-summarize-workbench-20260813/capture.py`
- Command under capture: `mem summarize task-1/participant --tui`
- Plain verification: `mem summarize task-1/participant --plain`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Profile/current Context: Study participant Profile; explicit initial Context
  `task-1/participant`
- Precondition: the selected Context has no direct ordinary Memories, so the
  approved direct run is deterministic and provider-free
- PTY: `180` columns × `52` rows, verified by the child process
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset;
  command-attempt logging disabled
- Renderer: cumulative real PTY ANSI streams replayed through `pyte` at the
  full Menlo canvas; raw `.typescript`, plain `.txt`, and PNG evidence retained

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-picker-entry.png` | Launch | Frozen readable Context tree owns focus; the explicit Context is checked | None |
| `02-descendants-focused.png` | `Tab` | Separate `DESCENDANTS` frame owns focus; direct is retained | None |
| `03-descendants-included.png` | `Right` | `INCLUDE DESCENDANTS` is staged; no summary execution occurred | None |
| `04-direct-ready-to-run.png` | `Left`, `Tab` | Direct is restored and the exact To Do receipt owns focus | None |
| `05-result-focused.png` | `Enter` | Provider-free direct result appears below the unchanged picker and range | None |
| `06-result-status-focused.png` | `Down` | Typed result status owns semantic focus | None |
| `07-result-understanding-focused.png` | `Down` | Empty-frame understanding owns semantic focus | None |
| `08-read-only-close-verification.png` | `Q` | Child verifies Context bytes and checkpoint identities are unchanged | None |
| `09-cancel-before-execution.png` | Separate launch, `Q` | Setup cancellation completes before application execution | None |
| `10-nontui-plain-verification.png` | Separate `--plain` launch | Stable noninteractive direct summary and read-only verification | None |
| `11-recursive-provider-result.png` | Separate launch, `Tab`, `Right`, `S` | The staged descendant range executes through the real provider and returns a recursive typed result | None |
| `12-recursive-read-only-verification.png` | `Q` | Child again verifies Context bytes and checkpoint identities after the recursive provider run | None |

The picker never switches the global current Context. The executable request
uses its selected canonical public name and the separately staged reach;
runtime READ/Grant resolution, source freezing, provider avoidance for empty
frames, and source revalidation remain authoritative.
