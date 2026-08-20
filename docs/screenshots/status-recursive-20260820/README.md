# Recursive Status CLI capture

This capture records the actual installed `mem status -r` projection after
commit `fcb1f8e1`. It uses the live `practice` Context hierarchy rather than a
synthetic fixture.

## Interaction log

| Capture | Exact command | PTY | Profile / current Context | Preceding action | Visible state | Durable mutation |
|---|---|---|---|---|---|---|
| `01-practice-recursive-status` | `mem status -r` | `180×52` | `study-20260819T175451Z-5ce5d722` / `practice` | Temporarily switch from `practice/source` to `practice` | Recursive aggregate and one compact direct-inventory row per reachable Context | Current pointer temporarily changed for capture, then restored to `practice/source` |

The capture process removes `NO_COLOR`, sets `TERM=xterm-256color` and
`COLORTERM=truecolor`, verifies the live PTY size as `52 180`, and preserves a
true-color prompt foreground sequence. The PNG is rendered from the matching
real PTY `.typescript` stream; the `.txt` file is its plain visible-canvas
projection. The command is read-only, and the harness restores the original
current Context even if capture fails.

Regenerate from the repository root with:

```sh
python docs/screenshots/status-recursive-20260820/capture.py
```
