# Mem Help study reference design rationale

## Purpose

The printed Letter-size reference is a participant aid, not a second authored
source of truth for the complete Help inventory. Bare `mem help` remains the
way to explore every operation available in the running prototype.

## Study scope

The handout preserves the Help-authored Description and Use When copy for each
included operation. It deliberately excludes:

- `mem ground`, because Ground is an agent-mediated workflow with its own
  conversational onboarding rather than an ordinary catalog choice;
- `mem provider`, because provider selection is setup chrome rather than a
  participant task operation; and
- `mem import` and `mem translate`, because neither operation belongs to the
  participant task paths represented in the printed reference;
- `mem shell-init`, because shell integration setup must not appear as a
  participant task possibility; and
- `mem init-study`, because study-environment provisioning is facilitator
  setup rather than an operation participants should invoke; and
- every operation currently marked `LEGACY`, because the study should not
  direct participants toward superseded interfaces.

An operation is excluded for its role in this study reference, not merely
because it carries a `PARTIAL` annotation.

## Layout tradeoff

The exclusions let the catalog fit in Letter landscape pages without reducing
11-point body type or tightening the established spacing between operation
blocks. Category colors, exact included Help copy, compact common inputs,
selected authored command Notes, and the first-page live-Help guidance remain
unchanged.

`COMMON INPUTS` combines a compact participant-facing operand sketch with the
most task-defining flags. Endpoint, criterion, and scope flags such as
`--from`, `--to`, `--into`, `--against`, and `--context` take priority over a
pure frequency ranking. This is why `mem meld` exposes its left/right/result
operands and endpoint aliases, while `mem forget` exposes its instruction
operand rather than appearing to accept only `--context`. The line is not a
replacement for the complete authored command Forms in live Help.

The `COMMON INPUTS` label uses the same small gray sans-serif treatment as the
other explanatory labels, while its operands and flags remain black monospace
code. This separates the field name from the usable input tokens without
adding vertical space or changing the spacing between operation blocks.

The page header is offset slightly down and right while the catalog body stays
fixed. This leaves the physical top-left corner clear for a diagonal staple
without reducing the body area.

Command Notes are not paraphrased for the handout. The builder reads selected
registered CLI epilogs directly and prints them under `NOTE` only when their
omission changes participant-visible behavior: Show's target typing and
Sever's self-save versus fresh-Result behavior. Routine positional epilogs,
including Update's saved-work spelling, are omitted because Common Inputs and
the omission primer already carry that grammar.

Page-bottom `DISTINCTIONS` panels replace repeated syntax with contrasts that can
change operation choice: Reference versus Embed, Find versus Search, Chunk
versus Atomize, Merge versus Meld, Dedup versus Dedun, Distill versus Elaborate,
Audit's combined checks, Fit versus Conformance, and Trace versus Rationale.
Each page reserves the panel's full height before catalog content is placed.
One comparison occupies one row; several comparisons on the same page stack as
aligned rows in one shared panel, making cross-comparison possible without a
separate summary page. The builder verifies every comparison anchor against its
assigned catalog page so Help-copy changes cannot silently detach the panel
from the commands it explains. `SEARCH & EXPLAIN` begins on page 6 to keep its
Find/Search panel stable after the page-5 Reference/Embed panel.

The panels keep 11-point text and add no background fill. Each operation name
reuses its category color while both sides retain the same weight and size;
this makes cross-category comparisons legible without turning either candidate
into the preferred answer. Descriptions, borders, and panel headings remain
neutral. The panels are
study-facing summaries derived from the authored Help contracts, not
additional CLI Notes. Redundancy receives no separate long latency or LLM
explanation; its only added mention is Audit's compact coverage comparison.
The reserved bottom panels make the handout 12 pages while preserving 11-point
body text and established spacing.
The Dedup/Dedun box says `exact matches` rather than only `duplicates` so the
participant-facing contrast is explicit: Dedup stops at exact same-role
matching, while Dedun adds semantic redundancy review.

Update versus Meld uses the same two-sided treatment in the bottom panel of
their shared semantic page. Update is a one-way revision of an existing Target,
while Meld is closer to a semantic merge that reconciles overlap and conflicts
into an authoritative Baseline or separate equal-peer Result, with synthesis
when needed.

The limitation is intentional: the printed category index is study-scoped and
must not be described as a complete operation inventory. Participants can use
bare `mem help` when they want to inspect possibilities outside the handout.
