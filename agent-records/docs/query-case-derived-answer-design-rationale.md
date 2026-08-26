# Query case-derived answer design rationale

Last updated: 2026-08-23.

## Status

Implemented on 2026-08-23 as ordinary Query provider contract version 2. The
provider returns one typed outcome and ordered semantic blocks; the strict
decoder validates each block's citation obligation and its compatibility with
the outcome before the application renders any answer.

## Motivating failure

In `practice/greetings`, the input `안녕하세요` produced:

```text
안녕 [1]

References
[1] anyeong — 06ab1d41, practice/greetings, m8
```

The Reference is relevant, but relevance alone does not establish that the
input asked a question. Treating every nonblank Query string as a request for a
direct answer makes ordinary Query drift toward general chat: a greeting is
answered as a greeting, a fragment may be completed, and an unrelated
statement may receive invented conversational continuation.

The useful behavior is narrower. Query should preserve the person's input act,
then report only what the complete frozen corpus supports. For this case the
desired answer is:

```text
질문이라기보다 인사로 보입니다. 현재 Context에는 관련 표현으로 `anyeong`이 저장되어 있습니다. [1]
```

There is no trailing instruction to ask a better question. Query reports the
interpretation and grounded observation that it can justify, then stops.

## Distilled answer rules

1. **Preserve the input act.** Distinguish a question or answer-seeking request
   from a non-question and from materially ambiguous input before composing a
   corpus answer. Semantic similarity to a Memory does not turn a greeting,
   statement, or fragment into a question.
2. **Separate answerability from relevance.** A corpus may contain material
   related to a non-question without containing an answer obligation. A
   question may be fully supported, partly supported, or unsupported.
3. **Use only frozen evidence for corpus claims.** External knowledge and
   conversational plausibility cannot fill a missing fact, relation, language
   identity, or requested part.
4. **Partition partial support visibly.** Answer every supported part and name
   each unsupported part at the selected-Context boundary. Do not let one
   relevant Memory make the whole multi-part question appear answered.
5. **Bound absence claims to the reviewed corpus.** Say that the current or
   selected Context contains no supporting information. Do not turn a
   whole-corpus review into a universal real-world negative.
6. **Cite positive evidence claims, not input classification.** A claim about
   stored content requires one or more validated Source aliases. “This appears
   to be a greeting” is an interpretation of the person's own input and does
   not acquire a fabricated Memory citation. A bounded no-evidence statement
   likewise renders no References section when it contains no positive corpus
   claim.
7. **Do not append unsolicited conversation repair.** Ordinary Query does not
   add “ask a more specific question,” “what would you like to know,” or a
   generic offer to continue unless a future explicit interactive clarification
   contract owns that turn.
8. **Match the person's language and remain concise.** The interpretation,
   supported answer, and scope limitation should normally need one or two
   sentences. Citation rows remain the separate host-owned evidence channel.

## Case matrix and model answers

The first calibration family uses one frozen greeting corpus so the answer
shape, rather than a changing Source, is the variable under review.

### Q1 — question, fully supported

Input:

```text
저장된 한 단어 인사말의 형식은?
```

Model answer:

```text
소문자 한 단어를 구두점 없이 작성하는 형식입니다. [1]

References
[1] Produce a standalone, lowercase greeting consisting of a single
    unpunctuated word... — 084b59cb, practice/greetings, mN
```

The answer directly satisfies the request and cites the rule that supports the
format claim. `mN` denotes the temporary alias assigned from the exact frozen
candidate order; an executable fixture must bind its concrete value rather than
treating this prose placeholder as a durable identity.

### Q2 — question, partly supported

Input:

```text
저장된 인사말 형식과 토론토의 내일 날씨를 알려줘.
```

Model answer:

```text
저장된 인사말 형식은 소문자 한 단어를 구두점 없이 작성하는 것입니다. [1]
토론토의 내일 날씨에 관한 정보는 현재 Context에 없습니다.

References
[1] Produce a standalone, lowercase greeting consisting of a single
    unpunctuated word... — 084b59cb, practice/greetings, mN
```

The first sentence is a sourced corpus claim. The second is a bounded scope
limitation over the complete frozen corpus, not an assertion about Toronto's
actual weather.

### Q3 — question, unsupported

Input:

```text
토론토의 내일 날씨는?
```

Model answer:

```text
현재 Context에는 토론토의 내일 날씨에 관한 정보가 없습니다.
```

No unrelated greeting rule or Reference is substituted merely because the
Context is nonempty.

### Q4 — non-question, related evidence

Input:

```text
안녕하세요
```

Model answer:

```text
질문이라기보다 인사로 보입니다. 현재 Context에는 관련 표현으로 `anyeong`이 저장되어 있습니다. [1]

References
[1] anyeong — 06ab1d41, practice/greetings, m8
```

The first clause preserves the input act. The second reports the related stored
content. It does not reply `안녕`, infer a durable translation relation, or ask
the person to reformulate the input.

### Q5 — non-question, no related evidence

Input:

```text
오늘은 기분이 묘하네.
```

Model answer:

```text
질문이라기보다 진술로 보입니다. 현재 Context에서 직접 관련된 내용을 찾지 못했습니다.
```

The response contains neither a conversational continuation nor References.

### Q6 — materially ambiguous, related evidence

Input:

```text
인사?
```

Model answer:

```text
구체적인 질문은 불분명하지만, 현재 Context에는 `bonjour`, `hi`, `ohayo`, `anyeong` 등의 인사 표현이 저장되어 있습니다. [1][2][3][4]
```

This is an observation, not a guessed answer to an unstated question. A host
may render the four validated References in first-use order. If the corpus does
not itself establish that an item is an “인사 표현,” the answer must use a
narrower description such as “관련 항목” rather than relying on external
language knowledge.

## Method for deriving rules from cases

This section instantiates the shared case-to-rule method in
`agent-records/docs/operation-example-contract-design-rationale.md`. It follows the
repository's Distill/Elaborate calibration practice without invoking either
command or treating generated text as evidence.

### 1. Hold the corpus constant

Begin with one small, coherent frozen corpus. Varying both the Source and the
input at once makes it unclear whether a changed answer came from evidence or
from answer policy. Add a second unrelated corpus only after the first matrix
is stable enough to test transfer.

### 2. Identify independent semantic axes

For ordinary Query the first axes are:

| Axis | Values |
| --- | --- |
| Input act | question/request, non-question, materially ambiguous |
| Evidence coverage | full, partial, none |
| Evidence relation | directly supporting, merely related, unrelated |
| Claim role | supported corpus claim, input interpretation, bounded scope limitation |
| Reference obligation | required, forbidden |

Do not begin with a full Cartesian product. Add a case when an interaction
changes behavior: partial coverage matters for questions, while merely related
evidence matters for non-questions and ambiguity.

### 3. Write the smallest acceptable answer first

For every case, author the shortest complete human answer before writing prompt
instructions or schemas. Mark each clause by claim role and identify the exact
Source aliases that support it. If a clause has no legitimate support and is
not an input interpretation or bounded scope statement, remove it.

### 4. Contrast each happy path with its nearest failure

Change one property at a time:

- fully supported question → add one unsupported requested part;
- partly supported question → remove the final supporting part;
- related non-question → replace it with an unrelated statement;
- explicit question → shorten it until the requested act becomes ambiguous.

The changed output reveals the actual rule. A case that changes several axes
at once is useful later as an integration check, not as the first source of a
rule.

### 5. Generalize only across observed obligations

The derived rule describes why outputs differ, not the literal vocabulary of
one answer. `안녕하세요` demonstrates preservation of a non-question speech
act; it does not establish a special Korean-greeting branch. A majority output
shape is not universal, and an example cannot authorize external knowledge.

### 6. Separate calibration, prompt examples, and holdouts

Q1–Q6 are executable `HOST_ONLY` structural examples in
`tests/test_ordinary_query_answer.py` and configured-provider `CALIBRATION`
cases. Their exact greeting corpus and answers do not enter the provider
prompt. Contract version 2 instead includes a separate `PROVIDER_VISIBLE`
North Gate family covering the same full, partial, absent, non-question, and
ambiguous distinctions. That family is consumed method instruction and cannot
be reported as independent evaluation evidence. A future semantic holdout must
remain textually and topically independent from both families.

### 7. Promote prose rules into enforceable contracts

After the case family survives review, update the following in one change:

1. provider instruction and contract version;
2. output schema and strict decoder;
3. typed application result and host citation assembly;
4. CLI, TUI, Python, and agent projections; and
5. deterministic case tests plus configured-provider calibration.

A prompt-only edit is insufficient when the host cannot distinguish a direct
answer from a related observation or partial answer.

## Implemented typed consequence

Provider contract version 2 replaces the former `answer_blocks`/`no_answer`
union with one explicit outcome kind:

- `ANSWER`;
- `PARTIAL_ANSWER`;
- `NO_ANSWER`;
- `RELATED_OBSERVATION`;
- `NO_RELATED_OBSERVATION`; or
- `AMBIGUOUS_OBSERVATION`.

Each output block should also distinguish:

- `SUPPORTED_CLAIM`, which requires at least one validated Source alias;
- `INPUT_INTERPRETATION`, which forbids Source aliases; and
- `SCOPE_LIMITATION`, which forbids aliases unless a separate typed artifact
  directly supports a narrower positive claim.

The host remains responsible for numeric citation assignment and References
rendering. The provider must not write citation numbers. Local validation must
reject an outcome whose required block roles or alias obligations do not match
its kind.

These names and their ordered role combinations are part of provider contract
version 2. The public Query result remains the rendered answer, grounded flag,
and typed citations; provider-only classification is not reconstructed by the
CLI, TUI, Python, or agent presentation adapters.

## Configured-provider observation

A configured-provider run used a temporary Store with the frozen five-Memory
greeting corpus (`bonjour`, `hi`, `ohayo`, the lowercase one-word format Rule,
and `anyeong`). All six cases completed in one provider turn each:

- Q1 returned a sourced full answer;
- Q2 returned a sourced greeting-format claim followed by an unsourced Context
  limitation for Toronto weather;
- Q3 returned only the bounded no-answer;
- Q4 classified the input as a greeting rather than replying socially, then
  reported related stored expressions with References;
- Q5 classified the input as a statement and reported no related Context
  information without References; and
- Q6 preserved the ambiguous question and reported related greeting evidence.

The person's live `practice/greetings` Context changed during validation, so it
was not used as the quality oracle. A later live run over its then-current
contents still preserved Q4–Q6's input acts and completed Q2 without the former
`invalid answer sources` failure. Exact prose and Reference count may vary;
outcome kind, role order, alias obligations, and corpus-bounded meaning are the
contract.

## Boundaries and non-goals

- This design applies to ordinary evidence-bound Query, not granted Query View
  routing or legacy `QueryContextRef` authentication.
- Input-act classification does not authorize general conversation, web use,
  or external factual completion.
- Query remains read-only and process-local; the classification and answer do
  not create a transcript or Memory.
- The host does not cite the complete corpus merely to decorate a no-answer.
- The design does not require a follow-up clarification turn. It preserves an
  ambiguous input honestly in the one-shot answer.
- These six cases are the first calibration family, not proof of broad language
  or domain generalization.
