# User-grounded memory operations: research rationale

## Status and research boundary

This note records the current HCI research framing for MemLab. It does not
claim that memory update, consolidation, deletion, retrieval, or compaction
are new computational ideas. It also does not claim that the present provider
implementation is the definitive NLP method for any operation.

The research contribution under study is an **interaction layer**: memory
management actions that are usually hidden inside an agent are externalized as
named, context-scoped requests that a person and an agent can jointly inspect,
ground, revise, and approve.

The current qualitative study asks which operations people need and how those
operations should expose intent, scope, evidence, consequences, and control.
Operation-specific NLP optimization and a comprehensive benchmark suite are
follow-on research opportunities unless a particular evaluation is explicitly
included in the present study.

## Motivating problem

Contemporary memory-enabled agents increasingly perform internal actions such
as summarizing a long history, extracting a fact, updating an existing memory,
linking related memories, consolidating duplicates, deleting stale material,
or retrieving older evidence. These capabilities can improve automatically
without giving the person an equally precise way to request or inspect them.

That asymmetry produces an interaction problem even when the underlying model
is accurate:

- a natural-language request may leave the intended memory action ambiguous;
- the system may choose a source or target scope that the person did not mean;
- an automatic update or consolidation may hide which evidence it changed or
  discarded;
- the person may not know which Context the agent currently treats as relevant;
- the agent may not know which Context the person intends to discuss; and
- a technically plausible result may still depart from the person's purpose.

The starting point of this research is therefore not that users know nothing
about memory management. It is that the system often performs memory
management invisibly, so users cannot reliably see, name, negotiate, or
correct the action that occurred.

## Internal operators are not a user action repertoire

An implementation may already contain functions named `ADD`, `UPDATE`,
`MERGE`, `DELETE`, `RETRIEVE`, or `CONSOLIDATE`. That does not establish that a
person can intentionally perform the corresponding action. In many memory
systems, the agent or memory controller chooses whether, when, and where to
run those functions. The person supplies ordinary conversation, while the
system privately decides that the conversation implies a write, revision,
merge, deletion, or no operation.

This distinction is central to the study:

```text
internal operator availability
!= user-visible action possibility
```

A user-visible action requires more than an exposed function name. The person
must be able to express the desired action, identify or negotiate its scope,
understand how the system interpreted it, inspect the proposed transition, and
correct or withhold it where appropriate. An automatically selected operator
may be technically sophisticated while still leaving the person's intended
action unavailable.

The research unit is therefore not the backend function. It is the
**intentional action available to a person in interaction**. The prototype's
command vocabulary is one candidate representation of that action space, not
an assumption that system-authored names already match users' concepts. The
qualitative study should observe how participants describe desired actions
before, during, and after encountering the current vocabulary, including
actions that do not fit it.

## Research proposition

MemLab treats an internal memory transition as a **grounded operation
request**. A command name is not merely shorthand for a hidden algorithm. It
opens a reviewable interaction in which the person and agent establish what
action is being requested, which Contexts define its frame, what evidence and
criteria govern it, what result is proposed, and what may be changed.

A complete user-grounded operation therefore has the following conceptual
shape:

```text
named operation
+ explicit source Context or Contexts
+ explicit target or destination when applicable
+ user purpose and operation-specific criteria
+ visible interpretation of the request
+ evidence-linked proposed result
+ consequences, uncertainty, and provenance
+ correction, deferral, rejection, or approval boundary
```

This makes the operation a grounding protocol rather than a one-line synonym
for a prompt. The user may begin with an incomplete request. The system may
propose an interpretation, but it must expose enough of that interpretation
for the user to identify divergence before a consequential memory change.

## Context as an explicit common-ground object

Many systems have context in an implementation sense while leaving it
interactionally implicit. Files, messages, retrieved chunks, system
instructions, and memories may all enter the model's context window without
the person and agent sharing a stable answer to questions such as:

- Which Context are we looking at now?
- Which Context did this evidence come from?
- Are we considering the exact Context or its descendants?
- Which Context is authoritative, editable, or only queryable?
- Where will a proposed result be saved?
- Did the Context change after the analysis was produced?

MemLab makes Context a named and inspectable common-ground object. Explicit
Context selection does more than route data. It gives both parties a shared
referent for interpreting the operation and its consequences. The same user
utterance can mean different things when grounded in a different source,
target, task description, authority frame, or Context revision.

This is why the paper premise that the **same Context is interpreted together**
is an interaction claim as well as a semantic execution invariant. The person
must be able to know which whole frame the system claims to have interpreted.

## Operation vocabulary

The prototype explores a coherent family of user-facing memory operations.
Their novelty is not that no related internal algorithm has existed. Their
role is to make distinct intents and consequences separately requestable and
reviewable.

| Operation | Internal tendency in memory systems | User-grounded question |
| --- | --- | --- |
| `Atomize` | extract or chunk memory | What separable claims are already grounded in this source? |
| `Compare` | detect similarity, conflict, or relevance | How do these two complete Contexts relate without changing either? |
| `Meld` | consolidate, merge, or rewrite memories | What may be integrated while preserving conflicts, provenance, and unrelated material? |
| `Refine` | rewrite a stored representation | What bounded improvement preserves the original meaning and authority? |
| `Update` | replace or supersede stored knowledge | What new evidence changes which existing material, and what must remain untouched? |
| `Forget` | delete, decay, or suppress memories | What should be removed under this criterion, and what collateral loss would result? |
| `Sever` | filter, partition, or project a memory store | What derived subset serves this purpose while leaving the Source unchanged? |

This vocabulary remains open to revision by the study. The study is not only
evaluating whether participants can operate a fixed command set; it also asks
which actions people actually need, which distinctions they understand, and
where their language or expectations do not fit the current operation model.

## Relationship to compaction and agent-memory research

`/compact` is a useful interaction precedent. It turns a recurring, formerly
prompt-like request into a recognizable operation, while later implementations
may improve the method through structured summarization, selective retention,
indexing, or retrieval. The stable interaction concept does not require one
permanent compaction algorithm.

The same separation motivates MemLab. `Compare`, `Meld`, `Forget`, or `Sever`
can remain meaningful user operations even if their backends later change from
one-shot LLM inference to compact decision representations, task-local graphs,
hierarchical indexes, deterministic projection, learned consolidation, or
hybrid methods.

Related work already establishes important neighboring ideas:

- [MemGPT](https://arxiv.org/abs/2310.08560) treats context management as
  movement among memory tiers.
- [A-MEM](https://papers.nips.cc/paper_files/paper/2025/hash/19909c36f51abc4856b4560aff3d36d6-Abstract-Conference.html)
  dynamically indexes, links, and updates agent memory.
- [LongMemEval](https://arxiv.org/abs/2410.10813) evaluates knowledge updates
  as one long-term memory capability.
- [MemoryAgentBench](https://openreview.net/pdf?id=DT7JyQC3MR) includes conflict
  resolution and fact consolidation.
- [RECALLbot](https://doi.org/10.1145/3772318.3790714) provides user controls
  such as viewing, editing, deleting, and pinning conversational memories.

These precedents narrow rather than erase the contribution. MemLab must not
claim to invent memory updating, forgetting, consolidation, or user control.
The proposed gap is a coherent, Context-scoped operation layer in which
multiple semantic transformations become explicit requests with shared
grounding, evidence, provenance, and review boundaries.

## Study questions

The present study can be organized around the following questions:

1. Which semantic memory-management actions do people attempt to perform in
   realistic tasks?
2. How do people describe the intended source, target, purpose, and scope of
   those actions before they know the system's vocabulary?
3. When do explicit Contexts help a person and agent establish common ground
   about what is currently being interpreted?
4. What interpretations, evidence, provenance, and consequences must be
   visible for a person to detect that an operation diverges from their intent?
5. Which decisions should remain automatic, which should be suggested, and
   which require explicit review or approval?
6. Where does the current operation vocabulary fail to represent an action
   participants need?

These questions separate the HCI contribution from provider accuracy. A
semantically imperfect backend can still reveal whether an operation is
needed, whether its scope is understandable, and what correction and approval
mechanisms people require. Conversely, a highly accurate automatic backend
does not establish that its hidden memory transition matches user intent.

## Benchmark direction

The operation vocabulary also creates a future evaluation surface. Existing
long-term-memory benchmarks often score downstream recall or question
answering. An operation-centered benchmark can instead evaluate the transition
itself:

- `Atomize`: coverage, atomicity, and source fidelity;
- `Compare`: exhaustive disposition, relation type, and N:M grouping;
- `Meld`: coverage, duplication, conflict preservation, and provenance;
- `Refine`: bounded change and meaning preservation;
- `Update`: correct incorporation, stale-state handling, and unrelated-memory
  preservation;
- `Forget`: intended removal and collateral loss;
- `Sever`: target relevance, coverage, and Source immutability; and
- every operation: latency, cost, review burden, correction effort, and trust.

Such benchmarks can compare multiple implementations of the same stable
operation contract. They need not freeze the present provider prompt as the
definition of the operation. The current qualitative study may identify the
contracts and failure cases that a later benchmark should encode; producing a
comprehensive NLP leaderboard is not required for the HCI contribution.

## Invariants and non-claims

- The system does not infer user intent merely because an automatic memory
  action is technically possible.
- Context selection is part of the operation's meaning, not only a retrieval
  optimization.
- A proposed interpretation is revisable and is not user approval.
- An operation result must preserve its source, scope, provenance, and
  revision boundary sufficiently for later review.
- Provider quality, latency, and cost matter for feasibility but do not define
  the research contribution.
- The work does not claim the first memory update, merge, consolidation,
  deletion, retrieval, compaction, or user-edit control.
- The existence of an internal memory operator does not count as evidence that
  the corresponding action is available or understandable to users.
- The work does not claim that the current command vocabulary is complete;
  discovering missing or misunderstood actions is part of the study.
- Future NLP methods may replace each backend without silently changing the
  user-visible meaning of the operation.

## Candidate contribution statement

> We study semantic memory operations as a user-grounded interaction layer for
> persistent AI memory. Rather than leaving memory updates, consolidation,
> filtering, and removal as hidden agent behaviors, MemLab externalizes them as
> named requests over explicit Contexts. This lets people and agents establish
> common ground about what evidence is in scope, how a request was interpreted,
> what consequences are proposed, and where correction or approval is needed.
> The work identifies and instantiates an operation vocabulary through a
> qualitative HCI study; operation-specific NLP optimization and benchmarks
> remain replaceable and extensible implementation layers.

## Related repository rationale

- [`cross-operation-grounding-design-rationale.md`](cross-operation-grounding-design-rationale.md)
  records how Goal, Rules, and Memories support repeated grounding across
  operation-specific evidence and mutation contracts.
- [`semantic-operation-criteria-original-and-en.md`](semantic-operation-criteria-original-and-en.md)
  preserves the original `/compact`-inspired operation criteria and English
  translation.
- [`semantic-under-30-latency-design-rationale.md`](semantic-under-30-latency-design-rationale.md)
  separates interaction meaning from current provider latency and compact
  execution experiments.
- [`mem-ground-design-rationale.md`](mem-ground-design-rationale.md) records the
  named common-grounding workbench and its current implementation boundary.
