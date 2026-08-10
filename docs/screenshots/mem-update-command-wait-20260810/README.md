# `mem update` shared command-wait capture log

These images render the actual color-preserving PTY byte stream produced by the
real `mem update` Typer command boundary. The run uses a delayed deterministic
provider so the shared wait can be inspected without an external semantic
request. The provider still receives Update's real prompt and schema and its
response passes through the production planner and staged-session save path.

## Reproduction frame

- Command: `mem update --from capture/update/source --to capture/update/target`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- PTY: `180` columns × `52` rows, verified inside the child process
- Environment: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` unset
- Profile/current Context: disposable local store; current
  `capture/update/source`
- Source: one direct Memory describing the updated south-entrance route
- Target: one direct Memory describing the superseded north-entrance route
- Provider: deterministic one-edit Update response; 1.2-second connection and
  18-second completion delays
- Renderer: cumulative ANSI stream replayed with `pyte`, then drawn at
  `1980×1092` with DejaVu Sans Mono; each matching `.typescript` and `.txt`
  artifact is retained beside the PNG
- Durable scope: a temporary store removed after capture; no real Profile,
  Context, staged session, or current-Context pointer was changed

The capture command was:

```bash
capture_pyte_dir=$(mktemp -d /tmp/memcommit-pyte.XXXXXX)
python -m pip install --quiet --target "$capture_pyte_dir" pyte
PYTHONPATH="$capture_pyte_dir${PYTHONPATH:+:$PYTHONPATH}" \
  python docs/screenshots/mem-update-command-wait-20260810/capture_update_wait.py
```

The driver fails unless the raw PTY stream contains ANSI controls and an
explicit foreground-color sequence. It sets the PTY dimensions before launch
and the child records the live `os.get_terminal_size()` value in the stream.

## Ordered interaction

| Image | Input since preceding image | Visible state | Durable mutation in disposable store |
| --- | --- | --- | --- |
| `01-dot-cycle-report.png` | Launch command | `UPDATE REPORT · BUILDING` at `1/2 · CONNECTING PROVIDER`; `PLAN`, `WHAT WILL CHANGE`, `PLANNED CHANGES`, and `TO DO` reuse the shared staggered `.`, `..`, `…` busy cadence | None after the already-frozen setup |
| `02-context-browser.png` | `c` | Switch-shaped frozen readable namespace with current `capture/update/source` marked; browsing is read-only and cannot switch | None |
| `03-context-memory-preview.png` | `m`, `Down` | The selected Context's direct Memory is expanded and receives the blue viewport focus; it remains preview-only and produces no Context-selection receipt | None |
| `04-report-after-context-repeat.png` | `c` | Repeating the active Context key returns to the report that opened it | None |
| `05-confirmed-inputs.png` | `i` | Exact Source A, Target B, selected-graph scopes, and read-only/until-Apply boundaries | None |
| `06-report-after-input-repeat.png` | `i` | Repeating the active input key returns to its report origin | None |
| `07-inputs-before-help.png` | `i` | Input is reopened as a named destination, establishing a fresh report origin | None |
| `08-help-during-update.png` | `h` | Shared root `mem help` inventory while the same Update worker and elapsed clock continue | None |
| `09-inputs-after-help-repeat.png` | `h` | Repeating Help returns to the exact confirmed-input view that opened it; the worker was not restarted | None |
| `10-report-destination.png` | `r` | Report is opened directly from inputs | None |
| `11-inputs-after-report-repeat.png` | `r` | Repeating the active report key returns to its input origin | None |
| `12-report-restored.png` | `r` | Report is reopened directly and continues at the worker's current planning stage | None |
| `13-staged-review.png` | Provider completes | Normal Update Resolution Workbench with one staged EDIT and explicit `REVIEW AND APPLY` | One staged Update receipt saved; Source and Target Contexts unchanged |
| `14-staged-receipt-verification.png` | `Escape` | Canonical staged report, “no target changes were applied,” staged-receipt presence, and read-only Source/Target verification | No additional mutation; staged receipt remains and both Contexts are byte-semantically unchanged |

The capture intentionally closes final review rather than approving Apply.
This verifies that Help and the temporary report do not bypass Update's
separate review, CAS publication, or target-application boundary.
