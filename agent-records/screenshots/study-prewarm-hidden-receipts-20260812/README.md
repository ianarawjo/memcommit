# Study prewarm hidden-receipt snapshots

These captures verify the changed Study prewarm boundary in an isolated
temporary `HOME`. The fixture contains one declared exact Tutorial Atomize
artifact. Setup validates it and writes one hidden receipt without creating an
ordinary Atomize analysis or workbench. The first explicit Atomize command
materializes the ordinary session without a provider call.

| Capture | Command / preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-hidden-receipt-empty-state` | fixture setup and read-only counters | One hidden receipt; zero visible Atomize sessions and no analysis | Context fixture and hidden receipt created; no operation session |
| `02-empty-atomize-session-launcher` | `mem atomize` | Empty saved-session catalog with only `Add new Atomize session` | None |
| `03-first-use-exact-materialization` | `mem atomize --context practice/source` | Exact prewarm report and `REVIEW AND APPLY` handoff | Exact analysis and blank workbench materialized; Source unchanged |
| `04-first-use-close-receipt` | same, then `q` | Explicit close receipt reporting provider-free first use | None after the materialization |
| `05-materialized-session-launcher` | `mem atomize` | The now-visible `practice/source` session plus the New row | None |
| `06-read-only-state-verification` | local read-only state inspection | One hidden receipt, one visible session, one visible analysis, Source still one Memory | None |

Capture environment:

- real `mem` executable with this checkout's `src` directory first on
  `PYTHONPATH`;
- verified `180 × 52` PTY;
- `TERM=xterm-256color`, `COLORTERM=truecolor`, and 24-bit prompt-toolkit color;
- `NO_COLOR` removed;
- isolated temporary `HOME`, deleted after capture; and
- raw `.typescript`, terminal-text `.txt`, and full-canvas `.png` for every
  numbered state.

The fixture's prepared analysis is constructed locally before capture. During
the participant-facing explicit command, the provider factory is never needed:
the complete analysis comes from the digest-verified registry artifact selected
by the hidden receipt.
