# Direct Forget Impact and Apply: ordered PTY record

Agent-produced execution evidence. These captures do not assert human review.

## Reproduction and provenance

Run `python agent-records/docs/screenshots/forget-impact-apply-20260906/capture.py`
from the repository root with pexpect, pyte, and Pillow available. The real CLI
child runs with `.venv/bin/python`. Only the provider response is deterministic;
command entry, whole-frame decoder, frozen snapshot, Impact projection, shared
report/Apply screen, authority checks, CAS, publication, checkpoint, and read-only
Show are production paths.

Every child starts in an isolated temporary profile and store. `HOME` and the
user's profile registry remain untouched. Local scenarios use current Context
`notes`; the granted scenario uses current `participant`, a separate `authority`
profile, and the public Source `granted/authority/notes` with READ/UPDATE/DELETE.

The exact changed-batch command is:

```text
mem forget "Forget the obsolete desk location and access code; keep accessibility guidance." --from notes
```

The granted command substitutes `--from granted/authority/notes`. The no-op
command uses `"Keep everything unchanged."`. Each verification runs
`mem show SOURCE --direct`. The fixture contains an obsolete desk location
mixed with step-free guidance, one obsolete code, and one independent retained
Memory. Analysis returns one TRANSFORM, one DROP, and one KEEP, except in the
all-KEEP scenario.

Captures preserve the actual ANSI PTY stream, rendered with pyte/Pillow; these
are not desktop screenshots or synthetic reconstructions of UI text. Viewport
**180 columns × 52 rows** is set before launch and asserted in the live child.
`NO_COLOR` is removed; TERM=xterm-256color, COLORTERM=truecolor and 24-bit
prompt-toolkit output are set. Foreground and background ANSI codes are checked
for every interactive branch. Full 1832×1124 PNG canvases accompany each raw
`.typescript` stream and `.txt` terminal projection.

## Ordered interaction log

The parent waits for stable visible states between the following inputs. Each
scenario starts from its own pristine fixture. Receipt-to-verification Enter is
a capture-harness gate after the real command has returned, not an application
approval or navigation key.

| Image | Scenario and visible state | Preceding keys/action | Durable effect |
| --- | --- | --- | --- |
| 01-analysis-entry.png | apply · analysis-entry | explicit command; no keys | fixture setup only |
| 02-apply-impact.png | apply · apply-impact | provider response; no keys | none; complete process-local batch only |
| 03-apply-focused.png | apply · apply-focused | Shift-Tab | none |
| 04-apply-receipt.png | apply · apply-receipt | Enter on Apply | owner edit/removal/checkpoint |
| 05-apply-verification.png | apply · apply-verification | harness gate Enter; mem show notes --direct | none |
| 06-cancel-impact.png | cancel · cancel-impact | provider response; no keys | none; complete process-local batch only |
| 07-cancel-receipt.png | cancel · cancel-receipt | Escape | none from Forget; stale scenario preserves a concurrent write |
| 08-cancel-verification.png | cancel · cancel-verification | harness gate Enter; mem show notes --direct | none |
| 09-granted-impact.png | granted · granted-impact | provider response; no keys | none; complete process-local batch only |
| 10-granted-receipt.png | granted · granted-receipt | Enter on Apply | owner edit/removal/checkpoint |
| 11-granted-verification.png | granted · granted-verification | harness gate Enter; mem show notes --direct | none |
| 12-noop-receipt-and-verification.png | noop · noop-receipt-and-verification | explicit all-KEEP command, then read-only Show | none |
| 13-stale-impact.png | stale · stale-impact | provider response; no keys | none; complete process-local batch only |
| 14-stale-receipt.png | stale · stale-receipt | Enter on Apply | none from Forget; stale scenario preserves a concurrent write |
| 15-stale-verification.png | stale · stale-verification | harness gate Enter; mem show notes --direct | none |

## Verified boundaries

Apply changes exactly two Memories and creates one owner checkpoint; one KEEP
Memory remains unchanged. Cancel publishes nothing. The granted case writes
only the authority Source, leaves the participant unchanged, and uses owner
recovery. All-KEEP finishes without a screen or checkpoint. In the stale case,
the harness inserts a concurrent Memory after the report returns Apply but
before command publication: the real CAS boundary rejects the old batch,
preserves all original Memories and the concurrent addition, and creates no
Forget checkpoint. Every branch asserts one provider call. Interaction metadata
records the base commit; captures include this task's then-uncommitted focused
changes and are retained in the same commit as the implementation.
