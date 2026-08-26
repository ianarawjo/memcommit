# `mem distill` and `mem elaborate` Help discovery

These read-only captures verify that Distill and Elaborate are discoverable
through both projections of the canonical `mem help` catalog and remain
readable in a compact viewport.
They use the installed `mem help` entry point in a color-capable `180x52` PTY
with `TERM=xterm-256color`, `COLORTERM=truecolor`, and `NO_COLOR` removed.
Help opens no Context content and performs no durable mutation.

1. `01-by-kind-distill-focused` — `mem help`; `Tab` three times reaches
   `ANALYZE & TRANSFORM`, then `Down` twice focuses Distill.
2. `02-by-kind-distill-expanded` — `Right` exposes the shared semantic
   contract and focuses its first Form.
3. `03-a-z-distill-focused` — a fresh `mem help`; `Shift-Tab`, `Right`, `Tab`,
   and `Home` select A–Z, then thirteen `Down` keys focus Distill.
4. `04-a-z-distill-expanded` — `Right` exposes the same contract and Forms in
   the A–Z projection.
5. `05`–`08` repeat BY KIND and A–Z discovery/expansion for Elaborate.
6. `09`–`12` capture collapsed and expanded Distill/Elaborate at `100×30`;
   summaries and `USE WHEN:` stack while the expanded contract remains
   scrollable.

The Elaborate captures use the final reviewed wording: candidate Rules come
from a Goal, concrete Case propositions come from existing Rules, and the use
case does not imply that Elaborate itself refines or verifies a Rule.

Each step has a native-size PNG, extracted terminal text, and the original
color-preserving PTY byte stream. The two projections consume one Help record;
the captures do not define duplicate wording.
