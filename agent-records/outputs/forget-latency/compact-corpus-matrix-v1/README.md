# Compact Forget corpus matrix v1

## Outcome

This screening campaign crossed eight pilot-derived Task 3 Forget criteria
with eight Codex model/reasoning conditions. All 64 final cells produced a
structurally valid 300-decision ledger. Thirty-five cells completed within the
30-second provider-time target.

The result does **not** identify an accurate winner. The eight requests do not
have human-reviewed per-Memory ground truth. Counts, cross-model agreement, and
complement consistency are diagnostic observations only.

## Frozen method

- Source: the same frozen 300-Memory Task 3 checkpoint in every cell.
- Contract: one whole-frame provider call with a 300-entry `K/E/D` vector and
  sparse replacement content for `E` positions.
- Schedule: one criterion per round, with all eight model/reasoning conditions
  started concurrently inside that round.
- Mutation: none. The evaluation reconstructed analyses but never applied one.
- Historical scoring: intentionally absent. The retained historical Forget
  result used a different instruction and therefore cannot score these cells.
- Retries: `Luna low × THIRD_PARTY` and
  `Luna low × SECURITY_AND_ACCESS` failed during their eight-way rounds and
  succeeded in a later two-way retry. Their latency is not under the same load
  as the other cells.

The exact corpus, conditions, wording, and scheduling rule are frozen in
[`compact-corpus-matrix-v1-manifest.json`](../compact-corpus-matrix-v1-manifest.json).

## Complete result matrix

Each cell is `provider seconds · reconstructed K/E/D`. `K/E/D` means exact
keep, edited remainder, and delete after conservative host normalization.

| Criterion | Luna none | Luna low | Terra none | Terra low | Terra medium | Sol none | Sol low | Sol medium |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SENSITIVE | 19.8 · 300/0/0 | 26.5 · 242/0/58 | 18.3 · 0/0/300 | 20.9 · 8/0/292 | 24.1 · 9/0/291 | 26.7 · 225/1/74 | 38.2 · 192/0/108 | 102.4 · 206/4/90 |
| DESCRIPTION_MATCH | 17.4 · 280/0/20 | 24.2 · 268/0/32 | 14.7 · 244/0/56 | 18.7 · 259/0/41 | 23.9 · 262/1/37 | 16.0 · 244/0/56 | 66.2 · 216/0/84 | 50.5 · 241/0/59 |
| HEALTH | 22.6 · 270/0/30 | 27.4 · 261/0/39 | 15.0 · 228/0/72 | 19.3 · 257/0/43 | 44.1 · 256/4/40 | 16.4 · 252/1/47 | 48.1 · 230/4/66 | 113.6 · 236/9/55 |
| HEALTH_EXCEPT | 17.7 · 21/0/279 | 24.2 · 39/0/261 | 14.9 · 42/0/258 | 24.3 · 39/0/261 | 25.8 · 44/1/255 | 21.8 · 75/0/225 | 47.8 · 51/0/249 | 76.9 · 71/1/228 |
| THIRD_PARTY | 17.1 · 269/1/30 | 61.2 · 275/14/11 | 37.6 · 254/15/31 | 67.7 · 259/18/23 | 79.3 · 256/22/22 | 33.6 · 243/19/38 | 88.1 · 213/21/66 | 128.5 · 208/20/72 |
| SECURITY_AND_ACCESS | 17.0 · 280/0/20 | 34.2 · 291/0/9 | 14.5 · 283/0/17 | 31.2 · 284/0/16 | 34.9 · 278/0/22 | 17.9 · 260/0/40 | 54.2 · 274/0/26 | 113.1 · 267/1/32 |
| FINANCIAL_AND_ADMIN | 15.6 · 279/0/21 | 28.7 · 270/0/30 | 14.6 · 259/0/41 | 30.8 · 278/0/22 | 40.9 · 263/4/33 | 15.1 · 268/1/31 | 45.5 · 255/1/44 | 82.4 · 270/4/26 |
| COMPLETED_EVENT | 18.3 · 88/0/212 | 27.1 · 270/0/30 | 14.6 · 128/0/172 | 36.7 · 246/0/54 | 50.5 · 241/0/59 | 24.2 · 115/1/184 | 46.2 · 215/0/85 | 107.0 · 209/0/91 |

## Latency by model and reasoning

| Condition | ≤30 s | Median | Mean | Range |
| --- | ---: | ---: | ---: | ---: |
| Luna none | 8/8 | 17.6 s | 18.2 s | 15.6–22.6 s |
| Luna low | 6/8 | 27.2 s | 31.7 s | 24.2–61.2 s |
| Terra none | 7/8 | 14.8 s | 18.0 s | 14.5–37.6 s |
| Terra low | 4/8 | 27.5 s | 31.2 s | 18.7–67.7 s |
| Terra medium | 3/8 | 37.9 s | 40.4 s | 23.9–79.3 s |
| Sol none | 7/8 | 19.9 s | 21.5 s | 15.1–33.6 s |
| Sol low | 0/8 | 47.9 s | 54.3 s | 38.2–88.1 s |
| Sol medium | 0/8 | 104.7 s | 96.8 s | 50.5–128.5 s |

Luna none is the only condition whose eight recorded provider times are all
under 30 seconds, but its outputs include two semantic extremes: `SENSITIVE`
kept all 300 Memories and `COMPLETED_EVENT` changed 212. Terra none is faster
at the median but deleted every Memory for `SENSITIVE`. Sol none avoided those
particular all-or-nothing extremes and met the target in seven cells, missing
only `THIRD_PARTY` at 33.6 seconds. These observations do not establish Sol
none as accurate; they make it the least obviously collapsed latency/behavior
tradeoff in this unlabelled matrix.

## Cross-condition semantic diagnostics

Pairwise exact raw-vector agreement was stable for explicit categories and
unstable for broad or transformation-heavy requests:

| Criterion | Median pairwise exact action agreement | Median changed-set Jaccard |
| --- | ---: | ---: |
| SENSITIVE | 0.382 | 0.322 |
| DESCRIPTION_MATCH | 0.913 | 0.569 |
| HEALTH | 0.893 | 0.573 |
| HEALTH_EXCEPT | 0.910 | 0.910 |
| THIRD_PARTY | 0.757 | 0.303 |
| SECURITY_AND_ACCESS | 0.930 | 0.427 |
| FINANCIAL_AND_ADMIN | 0.903 | 0.406 |
| COMPLETED_EVENT | 0.602 | 0.285 |

`HEALTH` and `HEALTH_EXCEPT` provide an internal polarity check: the Memories
changed by `HEALTH` should approximately equal those retained by
`HEALTH_EXCEPT`. Per-item membership agreement was 0.970 Luna none, 0.987 Luna
low, 0.863 Terra none, 0.967 Terra low, 0.967 Terra medium, 0.883 Sol none,
0.880 Sol low, and 0.860 Sol medium. This is consistency, not correctness.

## Sparse-edit failure shape

The response JSON was schema-valid in every retained cell, but the conditional
relationship between the fixed action vector and sparse edit rows was often
invalid. Twenty-five cells required conservative normalization:

- 3 exact no-op edits were converted to `K`;
- 138 `E` positions lacked a usable edit row and were converted to `K`;
- 183 edit rows appeared at positions marked `K` or `D` and were ignored;
- no duplicate-position edit survived validation.

The `THIRD_PARTY` cells account for 268 of these 324 repair events. Their edit
prose was often locally plausible, but the two output fields disagreed about
which position it belonged to. The current decoder therefore prefers safety
and loses some potentially useful transformations. A future compact contract
should remove this cross-field synchronization problem, for example by making
the sparse decision rows authoritative and deriving the action vector on the
host. That is a new contract and requires its own benchmark; it must not be
silently inferred from these results.

## Interpretation boundary

This matrix supports three narrow claims:

1. Removing repeated per-Memory explanation can bring many complete
   300-Memory Forget turns below 30 seconds.
2. Lower reasoning effort does not preserve semantic behavior uniformly.
3. Broad selectors and mixed-Memory transformation remain the hard cases,
   even when the response is compact and structurally recoverable.

It does not support an accuracy claim, automatic durable deletion, or replacing
the ordinary Forget review boundary. The study owner subsequently selected Sol
none as a provisional Forget-only research-prototype policy because it offered
the least obviously collapsed latency/behavior compromise in this matrix. A
human-labelled corpus is still required before treating that choice as a
validated production-quality policy.
