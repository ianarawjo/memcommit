# Reviewed `mem help` content

This ordered capture set verifies the accepted Search `USE WHEN` wording and
the reviewed Deterministic Content Changes, Semantic Transformations,
Check/Compare/Review, Ground, History, Profile, and selected System operation
copy. Expanded states also verify the canonical typed details for Merge,
Atomize, Distill, Translate, Impact, Fit, Check Conformance, Log, Revert,
Profile, Provider, and legacy Eval.

Every image comes from the actual installed `mem` executable in a color-capable
PTY with `NO_COLOR` removed, `TERM=xterm-256color`, and
`COLORTERM=truecolor`. Each state is recorded at both `180×52` (`wide`) and
`100×30` (`compact`). Help does not consult a Profile or current Context, and
every state is read-only.

## Ordered interaction log

Every row starts a fresh `mem help` process. `Tab` moves from the initial
Browse category to the named category. The recorder visits that category's
last row with `Down`, returns to the named operation with `Up`, and uses
`Right` to expand the operation and focus its first Form. Visiting the last row
first gives both viewport sizes a stable category-local scroll position.

| Capture stem | Category / operation | Preceding keys | Visible contract | Durable mutation |
|---|---|---|---|---|
| `01-search-{wide,compact}` | Search & Explain / Search | `Tab` ×2, `Down` ×3, `Up` ×2, `Right` | keyword-overlap `USE WHEN` | none |
| `02-merge-{wide,compact}` | Deterministic / Merge | `Tab` ×3, `Down` ×6, `Up`, `Right` | exact-match Summary and `MERGE BOUNDARY` | none |
| `03-dedup-{wide,compact}` | Deterministic / Dedup | `Tab` ×3, `Down` ×6, `Right` | retain-one/delete-rest contract | none |
| `04-atomize-{wide,compact}` | Semantic / Atomize | `Tab` ×4, `Down` ×8, `Up` ×8, `Right` | proposition separation and `--evaluate` route | none |
| `05-distill-{wide,compact}` | Semantic / Distill | `Tab` ×4, `Down` ×8, `Up` ×7, `Right` | upward derivation and Distill/Atomize boundary | none |
| `06-elaborate-{wide,compact}` | Semantic / Elaborate | `Tab` ×4, `Down` ×8, `Up` ×6, `Right` | abstract condition to specific candidates | none |
| `07-translate-{wide,compact}` | Semantic / Translate | `Tab` ×4, `Down` ×8, `Up` ×5, `Right` | view, Save As, and in-place routes | none |
| `08-resolve-{wide,compact}` | Semantic / Resolve | `Tab` ×4, `Down` ×8, `Up` ×3, `Right` | bounded Context frame | none |
| `09-meld-{wide,compact}` | Semantic / Meld | `Tab` ×4, `Down` ×8, `Up`, `Right` | Result or existing Target | none |
| `10-sever-{wide,compact}` | Semantic / Sever | `Tab` ×4, `Down` ×8, `Right` | select, transform, or exclude | none |
| `11-audit-{wide,compact}` | Check/Compare/Review / Audit | `Tab` ×5, `Down` ×8, `Up` ×4, `Right` | combined saved result | none |
| `12-impact-{wide,compact}` | Check/Compare/Review / Impact | `Tab` ×5, `Down` ×8, `Up` ×3, `Right` | read-only meaning and invocation routes | none |
| `13-review-{wide,compact}` | Check/Compare/Review / Review | `Tab` ×5, `Down` ×8, `Up` ×2, `Right` | saved semantic artifact boundary | none |
| `14-fit-{wide,compact}` | Check/Compare/Review / Fit | `Tab` ×5, `Down` ×8, `Up`, `Right` | YES/MAY/NO definitions and Context examples | none |
| `15-check-conformance-{wide,compact}` | Check/Compare/Review / Check Conformance | `Tab` ×5, `Down` ×8, `Right` | condition propositions and Fit distinction | none |
| `16-ground-{wide,compact}` | Ground / Ground | `Tab` ×6, `Right` | abstract goal to jointly shaped Ground | none |
| `17-log-{wide,compact}` | History / Log | `Tab` ×7, `Down` ×7, `Up` ×7, `Right` | recorded-history route distinctions | none |
| `18-diff-{wide,compact}` | History / Diff | `Tab` ×7, `Down` ×7, `Up` ×6, `Right` | checkpoint or active Update diff | none |
| `19-undo-{wide,compact}` | History / Undo | `Tab` ×7, `Down` ×7, `Up` ×2, `Right` | latest command as one recovery unit | none |
| `20-revert-{wide,compact}` | History / Revert | `Tab` ×7, `Down` ×7, `Right` | exact, interactive, and semantic restore routes | none |
| `21-profile-{wide,compact}` | Profiles / Profile | `Tab` ×8, `Down`, `Up`, `Right` | picker and explicit rename/remove routes | none |
| `22-provider-{wide,compact}` | System / Provider | `Tab` ×10, `Down` ×5, `Up` ×4, `Right` | status, selection, and explicit probe | none |
| `23-config-{wide,compact}` | System / Config | `Tab` ×10, `Down` ×5, `Up` ×2, `Right` | legacy stored-setting interface | none |
| `24-eval-{wide,compact}` | System / Eval | `Tab` ×10, `Down` ×5, `Right` | legacy fixed-fixture evaluation scope | none |

Every numbered state has a raw `.typescript`, terminal-text `.txt`, and
full-canvas `.png` artifact beside this log. `capture.py` records and renders
the actual PTY byte stream; the images are not synthetic Help fixtures.
