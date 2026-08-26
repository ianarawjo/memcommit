# Fit application boundary matrix

## Purpose

General Fit judges whether at least two already-stated propositions can jointly
hold under materially ordinary readings of one optional frozen background.
Automatically typed literal text, direct Memories, and the direct ordinary
Memories of one or more readable Contexts all enter that same role-neutral
frame; explicit source flags remain available. It changes and saves nothing.
The Ground workflow is an explicit graph
adapter: a successful run retains the historical Rule–Example judgments and
exhaustively checks Context alignment, Goal–layer alignment, and same-layer
compatibility in one immutable derived receipt. Reopening that receipt performs
no provider call and reports whether both its Ground and bound Context inputs
are still current.

This matrix records the boundary while Fit is added to the repository-wide
operation ledger. Fit has no standalone workbench or Viewer: its terminal
contract is one compact receipt, while named Ground keeps its own embedded
AUTO-FIT projection.

## Operation ownership

`memcommit.operations.fit.application` is the canonical owner of Fit's typed
requests and results, and `memcommit.operations.fit.runtime` owns the
MemoryStore/provider adapter used by the standalone command and named Ground.
The same package also owns the supporting contracts:
`memcommit.operations.fit.judgment` owns the reusable role-neutral semantic
judgment, `memcommit.operations.fit.coherence` owns exhaustive Ground graph
checks, `memcommit.operations.fit.ground_report` owns the historical
Rule–Example report and its public compatibility exports, and
`memcommit.operations.fit.store` owns immutable receipt persistence. Resolve,
Conflict, Impact, Elaborate, Ground, API, CLI, and presentation consumers
import these operation-owned modules directly. Cross-operation reuse does not
make those consumers co-owners of Fit's YES/MAY/NO meaning.

The former `memcommit.fit`, `memcommit.fit_judgment`,
`memcommit.fit_coherence`, `memcommit.fit_store`,
`memcommit.fit_application`, and `memcommit.fit_runtime` paths are
behavior-free module-identity aliases so old imports, monkeypatch targets, and
serialized globals continue to resolve to the same objects regardless of
import order. This relocation changes no judgment polarity, provider prompt,
authority, whole-frame planning, freshness, publication, or terminal
behavior, so the recorded interactive evidence does not require regeneration.

## Boundary matrix

| Layer | Owns | Must not own |
| --- | --- | --- |
| Domain/application | Role-neutral propositions, typed stored-source requests and origins, frozen background, YES/MAY/NO, complete-coverage decoding; Ground Rule–Example plus Context/vertical/peer graph checks, report projection, digests, and revision identity | Terminal detection, ANSI styling, keybindings, clipboard state, repair policy |
| Runtime/infrastructure | Whole-frame Fit planning before provider construction; exact Memory/Context locator resolution from one current-name snapshot; direct ordinary-Memory expansion; READ/DERIVE/COMBINE authorization; exact source revalidation; Ground and direct bound-Context load/freeze, immutable receipt store, current/stale lookup | CLI receipt prose, descendant/reference widening, mutation |
| CLI receipt adapter | One `FIT · VERDICT · [TARGETS: TYPE value, value, TYPE value ...]` general summary, and a `FIT · VERDICT · [TARGETS: GROUND name] · fraction` summary plus one line for each current `MAY/NO/N/A` Rule–Example relationship; fitting details remain omitted; only typed `YES/MAY/NO` tokens use shared judgment colors | Provider calls, Ground loading, receipt freshness decisions, full receipt expansion, operation-local palette values |
| Ground shell adapter | Process-local AUTO-FIT scheduling after durable revisions and how `·`, `✓`, `?`, `!`, and `◷` project onto Goal, Contexts, Rules, and Examples | Thread/executor lifecycle, a second Fit implementation, or automatic repair |
| Shared background turn | Mutual exclusion, animation, ContextVar propagation, non-abandoning executor shutdown, deferred close | Ground refresh, Fit success text, provider selection, receipt semantics |

## Request and result contracts

The ordinary executable request is one complete proposition set and optional
background. Positional operands automatically resolve `text:` escapes,
eight-or-more-character UUID-shaped Memory selectors, qualified
`CONTEXT:UID_OR_PREFIX` selectors, and exact frozen readable Context names. A
shorter hexadecimal value selects one unique ordinary-local direct Memory only
after exact Context lookup misses; otherwise the established literal fallback
remains. Explicit repeatable Memory and Context options remain available.
Contexts expand their direct ordinary Memories in stored order. Unqualified
Memory selectors use the command-start current Context; qualified and relative
Context operands resolve against that same captured name. It creates no
receipt. The explicit Ground
request is one exact saved Ground name and either:

- no receipt selector, meaning freeze, evaluate, and atomically save a new Fit
  receipt; or
- one exact receipt UID, meaning reopen that immutable report and compare it
  with the current Ground-derived receipt state.

General receipt projection consumes one typed `FitPropositionsResult`. Ground
receipt projection consumes one typed `FitReport` and explicit `current: bool`;
neither infers freshness from rendered text. Stored-source results additionally
carry exact process-local input origins for authorization and revalidation
without altering the provider proposition. General Fit is not a workbench
session and has no durable result. The Ground
adapter's version-2 immutable receipt retains the provider overviews, exact
statuses, reasons, observations, identities, Ground digest, and every bound
Context digest even when ordinary presentation omits them. Version-1 receipts
remain readable as historical Rule–Example-only reports and are incomplete for
AUTO-FIT currency.

Standalone whole-operation output spells `FIT · YES|MAY|NO|STALE`; marks are
reserved for local Ground checks and the embedded compatibility projection:

- `·`: no judgment has been run for the Ground Memory;
- `✓`: the current receipt judges the Example `FIT`;
- `?`: the current receipt reports `UNDERDETERMINED`;
- `!`: the current receipt reports `CONTRADICTS`;
- `◷`: a receipt exists but no longer describes the current Ground revision.

The ANSI-free output contract is terminal-independent. Every general result
prints exactly one logical line:
`FIT · VERDICT · [TARGETS: TYPE value, value, TYPE value ...]`. Context names,
direct Memory UID prefixes, and literal aliases are grouped in stable type
order. Context-expanded Memory identities, exact bodies, source associations,
original interleaving, reasons, material ids, and split `MAY` readings remain
in the typed result rather than repeating in the compact summary. Ground Fit
prints
`FIT · VERDICT · [TARGETS: GROUND <name>] · <fitted>/<total>` as its whole-operation
summary; each current `MAY`, `NO`, or legacy `N/A` Rule–Example check adds
exactly one line: `[RULE alias] [MEMORY <uid-prefix>] <content> ↔ [EXAMPLE alias] [MEMORY <uid-prefix>] <content>`.
There are no blank separators or expanded reasons; the immutable receipt
retains the reason. Coherence blocks show all frozen relation participants
even when provider material evidence names only one side. Fitting Examples and
graph findings are counted but never expanded. A stale receipt prints only its
stale summary, because its old issue details no longer describe the current
Ground. In a color-capable TTY only typed `YES`, `MAY`, and `NO` tokens use the
shared judgment palette. ANSI-free text, `--plain`, pipes, and `NO_COLOR`
retain the exact labels, order, and punctuation; there is no `--tui` route.

## Invariants

1. Standalone Fit never branches on TTY state or opens a Viewer.
2. General Fit validates and budgets one complete set before provider
   construction, acknowledges every frozen input exactly once in order, and
   never creates a receipt. Stored sources resolve and authorize before that
   boundary and retain the exact direct content supplied to it.
3. A receipt reopen never connects to a provider or writes another receipt.
4. A new Ground run publishes no receipt unless every active Example receives
   exactly one Rule–Example judgment and every planned Context, vertical, and
   peer check receives exactly one finding in frozen order.
5. Publication fails if the Ground revision/digest or any bound Context
   UID/digest changed after freezing.
6. General output is exactly one grouped target line for every verdict. Ground
   output is one operation-wide `FIT` summary plus one line per current
   Rule–Example issue; `--plain` suppresses color without changing that layout.
7. Ground's embedded run and standalone Fit use the same application/runtime
   execution, even though their presentations differ.
8. Compact presentation never removes evidence from the persisted receipt or
   weakens complete-frame validation.
9. Coherence detection never proposes, approves, or applies a repair. The
    user-decision grammar for a detected issue is a separate later design.
10. Named-Ground AUTO-FIT is process-local. It runs only when the Ground is
    bound and has active Rules and included Examples, waits for an in-flight
    frozen turn before fitting a newer revision once, and leaves the prior
    receipt stale after failure.
11. Stored Context sources include direct ordinary Memories only. Lexical
    descendants, embedded Contexts, Memory references, and QUERY-only routes
    never enter by implication.
12. Empty Context frames and missing or ambiguous Memory selectors fail before
    provider construction. Repeated Contexts, repeated Memory selectors, and
    direct-Memory/Context overlap remain distinct ordered operands while their
    identical source coordinates share exact revalidation state. At least two
    effective operand occurrences remain mandatory.
13. Granted stored inputs require READ and DERIVE, plus COMBINE across ownership
    domains or with caller-supplied literal/background propositions. Exact
    Grant identity and selected content are revalidated before result exposure;
    no SAVE permission is required because ordinary Fit is process-local.
14. Shell quotes group argv but do not type an operand. `text:` is the exact
    literal escape; UUID-shaped operands are strict Memory intent, while other
    operands become Contexts only through frozen readable-catalog membership.
    New UUID-selector-shaped root Context identities are rejected at their
    shared creation boundary; legacy roots require explicit Context selection.

## Shared components and intentional limits

Standalone Fit reuses only the narrow CLI text-safety adapter. Named Ground
continues to reuse `components.background_turn` for process-local AUTO-FIT.
Fit-specific labels and issue reasons stay in the receipt adapter; full
observations and immutable receipt evidence stay below the presentation
boundary.

The named Ground keeps its saved-Memory list and Enter detail in the Ground
adapter; a later presentation pass removed its redundant `V` table without
moving Fit meaning into shared UI. The blank first-turn draft flow still owns a
separate table projection and remains a separately characterized migration.
Fit also does not join hidden Study prewarming in this slice: an immutable Fit
receipt is an explicit derived artifact tied to a Ground revision, not evidence
that the operation satisfies the prepared-analysis cache contract.

## Verification gate

The slice is complete only when tests cover application execution without a
terminal, the same receipt in TTY and non-TTY hosts, issue-only Ground detail,
current and stale Ground/Context reopening, AUTO-FIT entry/refresh behavior,
duplicate embedded runs, close during a running turn, and ordered terminal
evidence.

## Verification evidence

Completed 2026-08-15:

- the configured live provider returned `YES`, `NO`, and `MAY` for the
  controlled entrance contrast, including both ordinary readings for `MAY`;
- `agent-records/screenshots/mem-general-fit-20260815` retains seven ordered `180 x 52`
  true-color states from provider progress through zero-write verification;
- application/runtime and CLI tests preserve new-run and receipt-reopen
  behavior, stable non-TTY output, `--plain`, and pre-storage `--tui` failure;
- typed adapter tests cover compact section identities, all-fit/issue/stale
  marks, focused Example copy, complete compact copy, and one-line plain text;
- shared Viewer interaction tests exercise lowercase `y` and uppercase `Y` in
  a real prompt-toolkit pipe;
- named-Ground tests cover all four marks, prove one executor call during
  repeated `F`, and require a requested close to wait for the receipt callback;
- `agent-records/screenshots/mem-fit-shared-viewer-20260815` retains the ordered
  `180 × 52` true-color PTY stream, native PNGs, plain canvases, exact inputs,
  and read-only verification.

Extended 2026-08-16:

- a configured live semantic-provider run over a real-company ticker Goal and
  Context plus one unsupported synthetic Example returned `CONTEXT 1`,
  `VERTICAL 2`, and `PEER 0`; it identified the absent company/ticker source and
  two insufficient Goal-layer connections without changing the Ground;
- `agent-records/screenshots/ground-unified-fit-20260816` retains eight ordered
  `180 × 52` true-color states for the one-line CLI result, typed Viewer,
  named-Ground AUTO-FIT, and read-only close verification; and
- targeted Ground/Fit/Help/catalog regression tests pass, including initial
  AUTO-FIT, exactly one refit after a durable revision, Context-stale rejection
  before provider connection, Context-stale receipt projection, exhaustive
  provider decoding, and version-1 receipt compatibility.

Extended 2026-08-20:

- stored-source tests cover literal/Memory/Context union ordering, repeatable
  current and qualified Memory selectors, multiple Contexts, relative locator
  resolution, empty-source rejection, repeated/overlapping operand
  preservation, selected-Memory versus whole-Context freshness, and the
  two-effective-proposition minimum;
- Grant tests require DERIVE, require COMBINE with caller-supplied literals,
  and reject an exact Grant revision change after provider inference;
- positional-source tests cover ordered automatic Memory, Context, qualified
  relative Memory, literal fallback, `text:` collision escape, and strict
  missing-UID rejection; the shared new-identity tests reserve UUID-selector
  roots while proving nested and existing legacy names remain available; and
- `agent-records/screenshots/fit-stored-sources-20260820` retains historical Viewer-era
  evidence; its former overlap-failure state is superseded by the current
  repeated-operand receipt evidence.

Revised 2026-08-21:

- the standalone semantic Viewer, clipboard projections, and `--tui` route were
  removed because Fit is detection, not a review session;
- receipt tests prove one operation-wide `FIT` verdict, grouped literal,
  Memory, and Context target summaries, both visible sides for Ground issues, and
  stale suppression of old details;
- `agent-records/screenshots/fit-compact-receipt-20260821` records provider progress,
  compact success, grouped general and Ground targets, stale, and repeated stored
  operands in real `180 × 52` PTYs; and
- the earlier Viewer screenshot sets remain historical evidence of the
  superseded interface rather than the current terminal contract.
