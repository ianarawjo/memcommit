# Distill and Elaborate shared-application TUI evidence

These captures use the actual prompt-toolkit Distill/Elaborate screens in a
color-capable `180×52` PTY. `NO_COLOR` is removed, `TERM=xterm-256color`,
`COLORTERM=truecolor`, and 24-bit prompt-toolkit color are set. The capture
script injects deterministic provider responses at the provider port; it does
not replace the application, command, setup workbench, semantic Viewer,
clipboard, Apply, Store, or CLI routes. Every run uses a disposable Store.
The set can be reproduced from the repository root with
`uv run --with pexpect --with pyte --with pillow python docs/screenshots/distill-elaborate-shared-app-20260815/capture.py`.

| Capture | Exact command / preceding input | Visible state | Durable mutation |
| --- | --- | --- | --- |
| `01-distill-context-entry` | `mem distill capture/cases --goal "Confirm before acting." --save-as capture/rules --tui` | Context selector is the initial focus | none |
| `02-distill-descendants-selected` | `Shift-Tab`, `Right` | descendants range selected; no ambiguous BOTH option | none |
| `03-distill-run-ready` | `Tab` ×2 | explicit Run action focused | none |
| `04-distill-reviewed-result` | `S` | one evidence-linked Rule; Goal marked relevance-only | none |
| `05-distill-focused-rule-copied` | `Down` ×4, `y` | focused Rule clipboard receipt | none |
| `06-distill-whole-proposal-copied` | `Y` | complete-proposal clipboard receipt | none |
| `07-distill-not-created-verification` | `q`, answer `n` to create prompt | Source byte-identical; proposed Result absent | none |
| `08-distill-cancel-before-provider` | fresh command, `q` | provider calls 0; Source unchanged | none |
| `09-distill-apply-and-show-verification` | `mem distill capture/cases --save-as capture/rules --apply --plain`, then `mem show --context capture/rules` | creation receipt plus read-only Result inspection | one new Result Context and one Distill checkpoint; Source unchanged |
| `10-ground-distill-frozen-source` | `mem distill --ground capture-ground --tui` | exact bound candidate Context and reach are visible but locked; Run owns initial focus | none |
| `10-ground-distill-reviewed-result` | `Shift-Tab`, `Right`, `S` | retarget keys cannot broaden the caller-frozen Source; exact proposal shown | none |
| `10-ground-distill-read-only-verification` | `q` | Ground record and all bound Context bytes unchanged; no Apply offered | none |
| `11-elaborate-goal-result` | `mem elaborate --goal "Confirm before acting." --tui` | Goal → suggested unverified Rule | none |
| `11-elaborate-goal-focused-copied` | `Down` ×3, `y` | focused suggested Rule copied | none |
| `11-elaborate-goal-read-only-verification` | `Y`, `q` | complete copy and unchanged Store verification | none |
| `12-elaborate-rules-result` | `mem elaborate --rule "Confirm the selected option before acting." --tui` | Rules → FIT/BOUNDARY suggested Cases | none |
| `12-elaborate-rules-focused-copied` | `Down` ×3, `y` | focused suggested Case copied | none |
| `12-elaborate-rules-read-only-verification` | `Y`, `q` | complete copy and unchanged Store verification | none |

Each numbered state has a raw `.typescript`, extracted `.txt`, and native-size
`.png`. Ground Distill's distinct frozen-source interaction is captured above;
UID, revision, frame-digest, and pre/post freshness checks are additionally
covered by application tests. Ground Elaborate uses the same result-only Viewer
as standalone Elaborate, so its nonvisual revision boundary is test evidence.
