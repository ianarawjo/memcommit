# Compact whole-frame Forget output rationale

## Motivation

The Task 3 Forget baseline sends one complete 300-Memory Source and one
instruction to the provider. The provider historically returned one complete
candidate object per Source Memory, including the Source alias, action, exact
retained content or replacement, rationale, and criterion reference. Recent
valid runs returned 62,311 to 78,115 characters and took 255 to 295 seconds.
Luna low also failed after a long turn because one `KEEP` candidate did not
repeat the exact Source text.

The experiment asks whether the output obligation, rather than complete Source
visibility, is the removable bottleneck. It is evaluation-only and does not
change production `mem forget` behavior.

## Contract

The provider still receives the complete frozen Source and the one instruction
in a single turn. It returns only:

```json
{
  "actions": ["K", "E", "D"],
  "edits": [{"i": 2, "c": "standalone retained remainder"}]
}
```

`actions` has exactly one position per Source Memory in the supplied order.
`K` means KEEP, `E` means EDIT, and `D` means DELETE. `edits` has exactly one
one-based row for every `E` position and no row for a `K` or `D` position.

The host reconstructs exact KEEP text from the frozen Source and empty DELETE
content. It uses provider text only for EDIT replacements. Therefore the
provider cannot corrupt a KEEP by copying it incorrectly, and it does not emit
per-Memory Source IDs, original text, rationales, criterion references, or an
overview. Host-generated rationale text is explicitly reconstruction
provenance and must not be represented as provider explanation.

## Invariants

- One provider turn sees all 300 Source Memories and the instruction.
- Forget remains `WHOLE_FRAME_ONLY`; no per-Memory or staged hidden calls are
  introduced.
- The action vector covers every frozen Source position exactly once.
- Empty or malformed replacement rows still fail closed. A missing, duplicate,
  or exact no-op replacement for an `E` position is conservatively
  canonicalized to KEEP, while an edit row attached to `K` or `D` is ignored.
  Every repaired or ignored one-based position is retained in the benchmark
  ledger, and none can publish as a false mutation.
- KEEP copies exact frozen Source text deterministically; DELETE supplies empty
  content deterministically.
- The reconstructed result passes the ordinary selective-curation decoder
  before it is considered valid.
- The benchmark never applies its analysis or mutates a MemoryStore.
- Raw prompt, schema, response, latency, validation, and agreement evidence are
  retained in a separate evaluation ledger.

## Evaluation boundary

The first controlled run uses the exact historical Task 3 300-Memory
checkpoint and first Forget instruction. It compares compact Terra-low output
with both the historical applied result and the retained Terra-low exhaustive
output. These are agreement measures, not accuracy, because neither prior LLM
run is reviewed ground truth.

Changing the output topology may change semantic decisions even though host
reconstruction is lossless. A shorter response is useful only if the compact
result remains structurally valid and preserves acceptable KEEP, EDIT, and
DELETE behavior. One run is a feasibility diagnostic, not authorization to
replace production Forget.

The evaluation CLI may also receive an explicit criterion ID and instruction
override for the frozen pilot corpus. When that instruction differs from the
historical applied instruction, the ledger sets historical agreement to
`null`; it must not reuse labels from a semantically different Forget request
as if they were ground truth. A baseline ledger is likewise rejected for a
different instruction.

## Eight-by-eight corpus result — 2026-08-10

The follow-up crossed eight Task 3 utterance families with eight model and
reasoning conditions, producing 64 final ledgers. Each criterion round started
its eight conditions concurrently. The complete matrix and exact manifest are
retained under
[`agent-records/outputs/forget-latency/compact-corpus-matrix-v1/`](../outputs/forget-latency/compact-corpus-matrix-v1/README.md).

Thirty-five of 64 provider calls completed within 30 seconds. Luna none met the
latency threshold in all eight cells, Terra none and Sol none in seven each,
and neither Sol low nor Sol medium met it in any cell. This does not make Luna
none the preferred semantic condition: it kept all 300 Memories for
`SENSITIVE`, while Terra none deleted all 300 for the same request. Sol none
avoided those all-or-nothing extremes and missed the latency target only for
the transformation-heavy `THIRD_PARTY` request at 33.6 seconds, but there is
still no human ground truth with which to call it accurate.

The compact topology was most reliable for pure keep/delete classifications.
Twenty-five cells required 324 conservative cross-field repairs: 138 vector
`E` positions lacked usable sparse text, 183 sparse rows targeted positions
whose vector code was not `E`, and three edits exactly repeated Source text.
`THIRD_PARTY` alone accounted for 268 repair events. Its proposed remainder
text was often locally plausible, but the action and edit arrays disagreed on
position. The current decoder deliberately converts unresolved `E` positions
to KEEP and ignores extra rows. This preserves the no-false-mutation boundary
at the cost of transformation recall.

The matrix therefore supports output compression as a latency technique for
many complete 300-Memory turns, but rejects a single universal
model/reasoning setting and the current two-field sparse-edit encoding as
ready production policy. A future contract may make self-contained sparse
decision rows authoritative and derive the dense vector locally. That change
must receive a separate structural and semantic evaluation rather than being
silently inferred as a repair here.

## Provisional Forget-only provider policy

For the current research prototype, the interactive and explicit `mem forget`
entry paths pin `gpt-5.6-sol` with reasoning `none`. This is a deliberately
operation-local policy rather than a new global semantic-provider default.
The 64-cell compact corpus gave Sol none a 19.9-second median and seven of eight
cells within 30 seconds while avoiding the keep-all Luna-none and delete-all
Terra-none outcomes observed for `SENSITIVE`. `THIRD_PARTY` still took 33.6
seconds, and the corpus has no human-reviewed action ground truth, so the
selection is a provisional latency/behavior compromise rather than an
accuracy claim.

Forget retains the configured semantic timeout and the subscription-backed
Codex authentication boundary. Other operations retain their own configured
provider, model, and reasoning policy. Forget also retains explicit review
before mutation. The model pin does not authorize automatic deletion or make
the compact evaluation contract a production contract; production Forget's
output topology remains unchanged until that separate migration is explicitly
implemented and evaluated.

## Alternatives and limitations

Three alternatives were rejected for this experiment. Independent `1:1`
provider calls would violate whole-Context interpretation and multiply work.
Returning only positive deletion candidates would make complete disposition an
implicit default and would not distinguish EDIT from DELETE safely. Keeping
per-Memory rationales would retain most of the observed output obligation.

The complete input still must be read, so compact output does not guarantee the
30-second target. Positional vectors also depend on a frozen order and exact
Source revision. Add, remove, reorder, instruction change, model change, prompt
version change, or semantic-ruleset change invalidates a cached artifact.
