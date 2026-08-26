# Semantic bare-entry routing PTY trace

The actual CLI callback is exercised for every session-enabled semantic
creation operation in scope. Bare invocation enters new-operation setup;
saved-work browsing is reachable only with `--sessions`.

- PTY: `180` columns × `52` rows, set by `pexpect` and reported by every child.
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, and
  `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT`, with `NO_COLOR` removed. Every raw
  typescript is checked for the expected ANSI foreground or focus-background
  styles.
- Profile: an isolated explicit Store that does not match the host Profile;
  host Grants are therefore excluded by the production catalog boundary.
- Current Context: `capture/reference`.
- Catalog: four local Contexts and no saved Compare, Meld, Sever, or Update
  artifact. An empty saved catalog still shows its pinned New action.
- Provider: every operation connector is replaced with a fail-closed counter;
  all eight routes report zero calls.

| Image | Exact command | Keys before capture | Visible state | Durable mutation |
| --- | --- | --- | --- | --- |
| `01-compare-bare-new-setup.png` | `mem compare` | none | Compare A/B endpoint setup | none |
| `02-compare-sessions-launcher.png` | `mem compare --sessions` | none | saved-analysis launcher with New pinned | none |
| `03-meld-bare-new-setup.png` | `mem meld` | none | Meld mode and endpoint setup | none |
| `04-meld-sessions-launcher.png` | `mem meld --sessions` | none | saved-Meld launcher with New pinned | none |
| `05-sever-bare-new-setup.png` | `mem sever` | none | Sever Source/Criteria/Output setup | none |
| `06-sever-sessions-launcher.png` | `mem sever --sessions` | none | saved-Sever launcher with New pinned | none |
| `07-update-bare-new-setup.png` | `mem update` | none | Update Source/Target endpoint setup | none |
| `08-update-sessions-launcher.png` | `mem update --sessions` | none | singleton saved-Update launcher with New pinned | none |
| `09-read-only-route-verification.png` | all eight commands above | `Escape` from every preceding screen | aggregate cancellation and read-only receipt | none |

For images 01–08, Escape was sent immediately after the capture. Each child
then verified an unchanged complete Store digest, unchanged checkpoint count,
unchanged current Context, and zero provider calls. Image 09 renders those
collected receipts. The path deliberately ends at cancellation because this
change owns entry routing; endpoint selection, semantic execution, review,
Apply, and read-only result viewing retain their existing focused capture sets
and regression suites.

Ground is excluded from this trace by design. Bare Review is also unchanged:
it is a read-only saved-evidence aggregate with no new-operation setup. Atomize
and Query already had the intended bare-work versus `--sessions` split.
