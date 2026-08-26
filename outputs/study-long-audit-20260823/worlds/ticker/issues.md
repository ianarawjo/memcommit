# Ticker core-audit issues

Study: `study-long-audit-20260823`  
World: `ticker`  
Goal: grow and maintain synthetic ticker rules across legal suffixes, punctuation, numerals, and share classes.  
Evidence: `phase-core.json` records 105 actual attempts: five interleaved rounds for each of the 21 parallel-safe core operations. `status` is intentionally reserved for the root serialized phase.

## Confirmed defects

### TICK-CHUNK-NO-UID-HANDOFF — High — 2/2 mutating splits, plus recovery evidence

- Expected: a successful split receipt should map the old UID to every new chunk UID and state the old Memory's disposition so the next operation can consume the result.
- Actual: both mutating receipts printed only the number of added Memories. A later `list` was required to discover the new UIDs and manually associate them with fragments.
- Workaround: immediately run exact `list` or a distinctive phrase `find`, then manually reconstruct the mapping.
- User impact: every successful split interrupts the workflow and makes reliable automation or agent chaining difficult.

### TICK-QUALITY-CROSS-CONTEXT-BLIND — High — 4 recursive attempts across 2 operations

- Expected: a recursive duplicate or redundancy scan over `audit/ticker` should compare the selected child Contexts with one another, because maintenance copies deliberately span `rules`, `examples`, `tests`, and `archive`.
- Actual: two `find-duplicates --recursive` and two `find-redundancies --recursive` attempts partitioned analysis by Context and returned zero groups despite known exact and semantic copies across children.
- Workaround: gather the candidates into one temporary Context before scanning, or compare child Contexts pairwise and reconcile copies manually.
- User impact: the command shape looks workspace-wide but misses precisely the cross-area drift a maintainer is trying to control.

### TICK-CTX-OVERLOAD — Medium — 5/5 attempts

- Expected: repeated discovery should support a task-local prefix or focused subtree so `audit/ticker` remains visible without unrelated worlds and Grants.
- Actual: every `contexts` call rendered the complete six-world Profile catalog, roughly eight terminal screens.
- Workaround: terminal-search the full output and manually extract the ticker subtree.
- User impact: the same global catalog must be reread at every early, middle, and late checkpoint.

## Internally reviewed non-defects

These dispositions preserve the observed command evidence for study history but
must not be promoted into an external bug list, priority count, or repair queue.

### TICK-CHUNK-ABBREVIATION-FRAGMENTATION — NOT A DEFECT · intended Chunk behavior

- Observation retained: sentence Chunk split the ticker examples at periods in `Inc.`, `Corp.`, and `ACME.B.`, producing adjacent Context-dependent Memories.
- Contract interpretation: Chunk is allowed to create those smaller units; the resulting Memories are meant to be read with their siblings in the selected Context rather than guaranteed to be independently self-contained.
- Disposition: no product defect or workaround is recorded for the split shape itself. The separate UID-handoff finding remains actionable because it concerns reuse of the created units, not whether Chunk was allowed to create them.

### TICK-AMBIGUITY-FRAGMENT-BLIND — NOT A DEFECT · intended complete-frame judgment

- Observation retained: three post-Chunk scans returned `0/6`, `0/13`, and `0/13` while the adjacent fragments remained direct Memories.
- Contract interpretation: Find Ambiguities interprets each target against the complete selected Context and deliberately omits a non-self-contained target when sibling Memories supply one usable reading with no changed operational decision.
- Disposition: the zero-finding results are contract-conforming and do not certify independent Memory self-containment; this evidence is retained internally only and is excluded from external defect reporting.

## Single-observation candidates

These require a second independent reproduction before confirmation.

### TICK-FIT-COLON-AUTO-TYPING — High candidate — 1 attempt

- Expected: two quoted natural-language propositions beginning `Core ticker rule:` and `Legal-suffix example:` should be treated as proposition text, or the error should directly recommend the documented literal forcing form.
- Actual: Fit interpreted `Core ticker rule` as a Context name and failed with `Context 'Core ticker rule' does not exist.`
- Workaround: prefix each literal operand with `text:` or store it as a Memory and use `--memory`.

### TICK-SUMMARY-LANGUAGE-DRIFT — Medium candidate — 1/5 summaries

- Expected: an English-only corpus and English CLI workflow should produce an English summary unless another language is requested.
- Actual: the round-3 recursive summary was semantically correct but entirely in Chinese. The other four summaries were English.
- Workaround: retry with an explicit language instruction in a different semantic operation, or manually translate the result; Summarize itself exposes no language selector.

### TICK-ADD-TUI-ACTION-DISTANCE-CANDIDATE — Medium candidate — 1 TUI path

- Expected: after saving the only draft, the visible `ADD 1 MEMORY · ENTER` action should be immediately operable or the retained draft focus should make the required transition unmistakable.
- Actual: pressing Enter reopened the editor because focus remained on the draft. The user had to save again, press Tab to focus To Do, then Enter to apply, and Enter once more to close the success receipt.
- Workaround: after `Ctrl-S`, press `Tab`, verify the blue To Do focus, then press Enter; close the success view separately.
- Cost: 180×52 color PTY, six material screen states, and three avoidable/recovery key actions.

### TICK-LIST-TYPED-COUNT — Low candidate — 1 attempt

- Expected: the header should distinguish ordinary Memories, snapshot References, and embedded Contexts.
- Actual: `list audit/ticker/rules` said `5 memories` while the five rows comprised three ordinary Memories and two References; the embedded Context was shown under `1 subcontext`.
- Workaround: inspect row type labels instead of trusting the header noun.

### TICK-QUERY-EVIDENCE-DUPLICATION-CANDIDATE — Medium candidate — 1 broad query

- Expected: a final recursive Query should deduplicate semantically identical citations reached through copies, snapshots, lexical descendants, and embeds, while retaining provenance drill-down.
- Actual: the correct final answer expanded 14 References, with the same rule/example facts repeated through several routes.
- Workaround: query exact child Contexts or manually collapse citations by content and provenance.

### TICK-REDUNDANCY-ONE-TO-MANY-CANDIDATE — Medium candidate — 1 attempt

- Expected: redundancy analysis should identify when a former whole statement is collectively covered by several chunks, or explicitly state that only pairwise/one-to-one relations are considered.
- Actual: the post-chunk examples scan reported zero groups.
- Workaround: compare the intact snapshot Reference against the chunk set manually.

## Useful behavior confirmed during the audit

- Search and ordinary Query correctly derived `NORTHSTAR`, `ROUTE66`, and `ACME.B` from progressively accumulated evidence.
- Compare recovered the relationship between intact tests and fragmented examples and remained useful for cross-Context maintenance.
- Fit handled exact Memory and multi-Context stored sources once the ambiguous literal route was avoided.
- A deliberate lowercase rule conflict was detected against uppercase expected outputs; `replace` then restored the uppercase invariant, and the final Compare and Fit both passed.
- Duplicate Embed was rejected without mutation, References remained immutable after edits/chunks, and the shared current Context remained `practice` throughout worker execution.
