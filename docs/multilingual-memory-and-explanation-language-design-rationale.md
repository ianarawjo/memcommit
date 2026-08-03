# Multilingual Memory and explanation-language design rationale

## Status: deferred research TODO

The current demo keeps the shared result-workbench reports, explanations,
questions, options, headings, and most ordinary CLI guidance in English. Some
operation-specific dialogue paths may instead respond in or derive wording
from the person's language. Those local behaviors do not constitute a global
language policy. There is no global language setting or per-command language
override.

This is an intentional scope boundary, not a claim that English is neutral,
that translations are semantically exact, or that an analysis performed in
one language is invariant when performed in another. The broader language
policy is deferred because it is closer to a research program than to UI
localization.

The motivating environment is multilingual Quebec. English and French may be
used for the same project, while participants or source material may also use
Korean, Chinese, or another language. In that setting the first unresolved
question is not how to translate a heading. It is which language a Memory
should be authored in, what is lost or changed when it is translated, and
which language should govern later semantic analysis.

## Separate language roles

One `language` value would otherwise collapse several materially different
roles:

| Role | What it governs | Current demo behavior |
| --- | --- | --- |
| Source or authoring language | The exact text stored in a Memory | Preserved verbatim; not normalized |
| Analysis language | The language in which a provider is instructed to classify, compare, or reason about source material | Many shared-workbench prompts explicitly request English; other behavior remains operation-specific |
| Explanation language | Provider-authored overviews, reasons, questions, and options | English on shared result-workbench surfaces; operation-specific elsewhere |
| Interface language | Host-authored headings, labels, help, warnings, and confirmation text | Predominantly English |
| Interaction language | A person's free-form answers or grounding dialogue | Preserved or handled according to the operation-specific contract |
| Translation target | The requested representation produced by `mem translate` | Explicit semantic target supplied to Translate |
| Control vocabulary | Commands, flags, schema keys, enums, and durable machine values | Stable canonical tokens; not natural-language prose |

A future preference may coordinate several of these roles, but it must not
pretend they are the same datum. In particular, changing an explanation
language must not silently rewrite source Memories or durable control values.

## Why this is not ordinary localization

Fixed interface text such as `WHAT MEM UNDERSTOOD`, `WHY`, and `ASK` can be
translated from a local catalog. The prose beneath those headings is different:
it is produced as part of the semantic operation and is saved in artifacts
that may later support review, grounding, or application.

Changing the requested analysis or explanation language can affect:

- which ambiguity appears salient;
- how scope, negation, modality, and uncertainty are expressed;
- whether two statements appear equivalent, compatible, scoped, or
  conflicting;
- the specificity and tone of a clarification question;
- the options proposed for resolving an issue;
- terminology tied to a legal, institutional, professional, or regional
  context; and
- the amount of information that fits within a short report budget.

The magnitude and direction of those effects remain empirical questions for
this prototype. They are nevertheless sufficient to reject an assumption of
automatic cross-language equivalence.

Translation can also remove or introduce distinctions. Register, politeness,
evidentiality, grammatical modality, pronoun omission, polysemy, and local
institutional terminology do not always have one exact counterpart. A fluent
translation is therefore not proof that the translated Memory supports every
inference supported by its source, or vice versa.

This makes the language in which a Memory was authored part of the available
evidence. It is not merely a display encoding that Mem can normalize away.

## Current demo decision

For the current demo:

1. Shared result-workbench explanations and their host-rendered headings
   remain in English.
2. Source Memories and quoted evidence remain verbatim in their original
   language.
3. Free-form user material is not translated merely to make a screen
   monolingual.
4. Semantic operations do not silently translate their inputs before analysis.
5. `mem translate` remains an explicit, persisted translation view with a
   person-supplied semantic target. It does not set the language of Mem as a
   whole.
6. No saved English artifact is relabeled as though it had been generated in
   another language.
7. Existing operation-specific conversational language behavior remains
   local to that operation; it is not generalized into an implicit setting.

English provides one consistent comparison surface for the shared workbench
demo and keeps the current implementation and evaluation scope bounded. It
does not establish an eventual product default or a preferred language for
authoring Memories.

## Deferred interface direction

If this work resumes, the leading interface candidate is:

```text
per-command --language
→ global language preference
→ demo fallback English
```

For example:

```bash
mem config set language ko
mem compare --to task2/advisor2
mem compare --to task2/advisor2 --language en
```

An initial study might examine English, French, Korean, and Chinese. That list
is not yet a committed product contract. Locale and writing-system choices
such as Canadian or Quebec French, Canadian English, Simplified Chinese, and
Traditional Chinese must be explicit rather than hidden behind broad labels
when they matter to the task.

A command would freeze its resolved language profile at the beginning of an
invocation or interactive session. Host-rendered headings and provider-authored
prose would use the same profile so the screen does not become accidentally
half-localized. Source evidence, names, UIDs, commands, flags, schema keys, and
canonical enum values would remain stable.

The setting must apply to Mem-authored language, not to the language of stored
Memory content. It must also remain independent from `mem translate --to`,
which requests a translation representation rather than selecting the
explanation language for every semantic operation.

## Persistence, identity, and reuse remain open

Language cannot be added only to a prompt. Saved comparison, Meld, atomize,
Ground, and other semantic artifacts currently contain explanatory prose. A
future implementation must record the exact language profile used and must
not reuse an artifact under a different language contract merely because its
source Context is unchanged.

Two approaches require study:

1. **Language as a semantic-operation input.** Each language-specific run is a
   distinct analysis artifact because the relation judgments, issue framing,
   or proposed questions may differ.
2. **Language as a presentation view.** One analysis remains authoritative and
   UID-less language views present its explanations in other languages.

The second approach avoids multiplying semantic identity for presentation,
but it assumes that the translated view faithfully preserves the analysis.
That assumption is precisely one of the unresolved research questions. The
first approach is more honest about possible semantic divergence, but it can
produce several analyses of the same source and needs an explicit comparison
and selection policy.

Whichever approach is selected, language must participate in reuse,
staleness, provenance, and migration rules. Switching a preference must never
silently relabel an English artifact as Korean or French. Switching back
should not spend provider allowance again when an exact compatible
language-specific result is already durable.

## Memory-authoring questions

The future work begins before output localization:

- Should a person author a Memory in the language in which the thought or
  source was originally expressed?
- Should a shared Context adopt one working language for accessibility, even
  when doing so loses nuance?
- Should parallel-language texts be distinct Memories, linked
  representations, or UID-less views of one source occurrence?
- Is explicit language metadata needed on a Memory, Context, or artifact, and
  who is authoritative for that declaration?
- How should a mixed-language Context be analyzed when one provider call must
  relate all of its Memories?
- When direct analysis in the source language and analysis of a translation
  disagree, which evidence and decision procedure should govern?

Automatic language detection may be a convenience signal, but it cannot be
the authority for these choices. Short text, names, code-switching, borrowed
terms, and closely related language varieties make detection uncertain.

## Candidate research comparisons

The same source-linked fixture should be evaluated under at least these
conditions:

1. analyze the original text directly and explain in the source language;
2. analyze the original text directly and explain in another language;
3. translate first, then analyze the translation;
4. analyze source and translation together while preserving their distinct
   evidence roles; and
5. repeat the operation across language profiles and compare relation kinds,
   unresolved issues, questions, options, omissions, and confidence claims.

Human review should include people competent in the relevant languages and,
where applicable, the regional or institutional domain. String similarity,
back-translation, or agreement between two model calls is not sufficient
proof of semantic equivalence.

The study should pay particular attention to cases involving negation,
exceptions, obligations, permissions, uncertainty, formal versus informal
register, local terminology, and wording that is intentionally ambiguous.

## Conditions before implementation

The TODO should not be considered ready merely because four heading
translations are available. Before implementing the global setting, decide
and test:

- the supported language and locale profiles and their fallback behavior;
- whether the preference governs analysis, explanation, interface text, or a
  documented subset;
- the artifact-identity and language-view model;
- locale-aware persistence, reuse, staleness, and legacy-English migration;
- language-appropriate report-length guidance rather than assuming English
  word segmentation;
- consistent coverage across the major semantic commands;
- behavior for interactive sessions and mid-session configuration changes;
- preservation of source evidence and canonical machine vocabulary; and
- a multilingual evaluation method capable of detecting semantic drift.

Until those decisions are supported by evidence, retaining one explicit
English demo contract is preferable to a partial setting that changes labels
while leaving analysis, persistence, and provenance language-blind.
