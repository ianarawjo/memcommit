# Direct-Memory locator CLI capture log

This ordered evidence set records the implemented direct-Memory locator rules
for Embed and Reference: an unqualified UID searches every ordinary local
direct Context and succeeds only when unique; `CONTEXT:UID` fixes the owner;
relative owner locators use the command-start current Context; omitted
`--into` uses that current Context; ambiguity fails before publication and
shows every canonical owner candidate.

## Reproduction frame

- Capture command:
  `python docs/screenshots/direct-memory-locator-cli-20260821/capture.py`
- Working directory: `/Users/KimMunyeong/Github/memcommit`
- Executable under observation: the installed `mem` executable resolved from
  `PATH`; every displayed command is run as a real child process
- Stores: two isolated disposable Profiles created beneath temporary `HOME`
  directories; no personal Profile, current pointer, Context, or checkpoint is
  read or changed
- Success fixture: Source `practice/3` directly owns four fixed Memories;
  Target/current Context `practice/4` starts empty
- Ambiguity fixture: `practice/3` and current `practice/4` each directly own
  the exact UID `aaaaaaaa-0000-0000-0000-000000000000`
- PTY: `180` columns × `52` rows, verified live by every capture child
- Color: `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` removed;
  raw streams are checked for green success and red failure ANSI sequences
- Renderer: actual color-preserving PTY bytes are replayed through `pyte` and
  drawn on the full `1832×1124` Menlo terminal canvas. The raw `.typescript`
  and extracted `.txt` evidence remain beside every PNG.
- Input: these are non-interactive CLI commands, so there are no intervening
  keys. Every image starts a new PTY process against the retained isolated
  fixture state described by the preceding row.

## Ordered evidence

| Image | Exact command / state since preceding image | Visible result | Durable mutation |
| --- | --- | --- | --- |
| `01-precondition-source-and-current-target.png` | `mem pwd`; `mem list practice/3`; `mem list practice/4` | Current is `practice/4`; Source has four direct Memories; Target is empty | None |
| `02-bare-uid-embed-default-current-target.png` | `mem embed ca562047` | Bare UID resolves uniquely to `practice/3`; omitted `--into` publishes the live Embed in current `practice/4` | One Memory Embed in the disposable Target |
| `03-bare-uid-reference-default-current-target.png` | `mem reference dbdb4436` | Reference performs the same unique global owner lookup and defaults its Target to current `practice/4` | One immutable Memory Reference |
| `04-qualified-context-uid-embed.png` | `mem embed practice/3:11111111` | Canonical `CONTEXT:UID` selects only the explicit direct owner | One Memory Embed |
| `05-relative-qualified-reference.png` | `mem reference ../3:22222222` | Relative owner resolves from captured current `practice/4` to `practice/3` | One immutable Memory Reference |
| `06-read-only-target-verification.png` | `mem list` | Current Target contains exactly two live Embeds and two immutable References, all retaining `practice/3` Source identity | None |
| `07-duplicate-uid-blocked-with-all-owners.png` | Separate ambiguity fixture; `mem embed aaaaaaaa` | Command exits `1`, displays both full `practice/3:UID` and `practice/4:UID` candidates, and requests a qualified locator | None; Target record digest and checkpoint count are verified unchanged |

The capture script asserts every command exit status and durable postcondition.
The final ambiguity check deliberately includes a match in the current Context,
proving that current has no hidden priority over another local owner.
