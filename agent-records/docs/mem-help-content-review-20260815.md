# Mem Help Content Review

> Historical snapshot: the 2026-08-20 Help revision replaced the semantic
> `find-duplicates`/Apply split with `mem dedun`; exact identity cleanup is
> `mem dedup`. The tables below preserve the 2026-08-15 reviewed catalog.

Status: working draft, 2026-08-15

This document freezes the current review copy before it is promoted into the
runtime Help catalog. It contains the same 62 operations in two separate
tables: English first and Korean second.

Field provenance:

- Flow and Explanation started from the current English Help catalog wording;
  reviewed rows may contain proposed replacements until they are promoted.
- LLM is projected from the current execution classification.
- Boundary is a review draft synthesized from the current effect and range.
- Best For is a required runtime Help field; wording that has not been
  individually reviewed remains a review draft in the canonical catalog.
- The Korean table translates the corresponding English review row; it is not
  a separate behavioral specification.

Category descriptions shown in the runtime BY KIND view:

- **Browse & Navigate — NO LLM:** Inspect the current location and available
  Contexts, then move through the Context namespace. / **탐색 및 이동 — LLM
  미사용:** 현재 위치와 이용 가능한 Context를 확인하고 Context namespace
  안에서 이동합니다.
- **Create, Copy & Connect — NO LLM:** Create Contexts or Memories, copy or
  import resources, or connect existing material. / **생성·복사·연결 — LLM
  미사용:** Context나 Memory를 생성하고 resource를 복사·가져오거나 기존
  자료를 연결합니다.
- **Search & Explain — MIXED:** Find exact text directly, or use LLM-based
  semantic retrieval, answering, and summarization within the selected
  authorized scope. / **검색 및 설명 — 형식별 상이:** 선택하여 권한을 확인한
  범위에서 정확한 텍스트는 직접 찾고, LLM 기반 의미 검색·질의응답·요약을
  사용합니다.
- **Deterministic Content Changes — NO LLM:** Apply explicit inputs and reviewed
  choices through deterministic program logic to change content. / **결정론적
  내용 변경 — LLM 미사용:** 명시한 입력과 검토된 선택을 결정론적인
  프로그램 로직으로 적용해 내용을 변경합니다.
- **Semantic Transformations — LLM-BASED:** Uses LLM semantic analysis to
  restructure, derive, translate, curate, or reconcile content. / **의미 기반
  변환 — LLM 기반:** LLM 의미 분석을 사용해 내용을 재구성·도출·번역·선별
  하거나 서로 조정합니다.
- **Check, Compare & Review — MIXED:** Check compatibility, differences,
  quality, or expected impact. Review saved analysis and decide what should
  happen next. / **검사·비교·검토 — 형식별 상이:** 양립 가능성·차이·품질·
  예상 영향을 검사합니다. 저장된 분석을 검토하고 다음에 할 일을
  결정합니다.
- **Ground Workbench — LLM-BASED:** Build a reviewable common ground for agent
  memory by developing its Goal, Rules, and example Memories together. /
  **Ground Workbench — LLM 기반:** Goal·Rule·example Memory를 함께 발전시키며
  agent memory를 위한 검토 가능한 common ground를 만들어 나갑니다.
- **History & Recovery — MIXED:** Inspect provenance and recorded changes.
  Restore an earlier state through explicit history operations. / **기록 및
  복구 — 형식별 상이:** 출처와 기록된 변경을 확인하고 명시적인 history
  operation으로 이전 상태를 복구합니다.
- **Profiles — NO LLM:** Select and administer complete local Profile stores and
  their managed names. / **Profile — LLM 미사용:** 완전한 로컬 Profile
  store를 선택·관리하고 등록된 이름을 변경합니다.
- **Sharing & Protection — NO LLM:** Deliver owned Contexts and protect Memory,
  Context, or Profile writes. / **공유 및 보호 — LLM 미사용:** 소유한 Context를
  전달하고 Memory·Context·Profile의 쓰기를 보호합니다.
- **System & Study Tools:** Configure MemCommit and prepare or run study and
  evaluation utilities. / **시스템 및 Study 도구:** MemCommit을 설정하고
  Study 및 평가 도구를 준비하거나 실행합니다.

Review invariant: revise the English row first, then keep the Korean row
semantically aligned. Approved wording should be moved into the canonical Help
catalog rather than parsed from this document.

## English review table

| Category | Name | LLM | Flow | Explanation | Boundary | Best For |
|---|---|---|---|---|---|---|
| Browse & Navigate | status | NO | Current Context state + history → status report | Show the current Context's inventory, first five direct Memories, relationships, and latest checkpoints. | Read-only; current Context by default, while `-r` includes readable descendants and embedded Contexts. | Getting oriented to what the current Context contains, how it is connected, and which operations were recently applied. |
| Browse & Navigate | pwd | NO | Current Context pointer → canonical name | Print the current canonical Context name without loading its contents. | Reads only the pointer; Context content is not loaded. | Confirming the active Context in a script or terminal. |
| Browse & Navigate | contexts | NO | Profile access → readable Context catalog | List local Contexts and readable cross-Profile Context views. | Read-only static report; includes all readable names and does not switch Context. | Inspecting every Context currently available to the Profile. |
| Browse & Navigate | list | NO | Context → direct-item and child-Context listing | List a Context's direct items—Memories, Memory references, query views, and embedded Contexts—and its readable child Contexts. Use `-r` to recursively include items from descendant and embedded Contexts; `ls` is the compact alias. | Read-only; one exact Context, while `-r` follows readable lexical descendants and embedded Contexts. | Inspecting the structure and direct contents of a Context. |
| Browse & Navigate | show | NO | Context or direct item → rendered content | Show a Memory, reference, embedded Context, or the direct contents of a current/explicit Context. | Read-only; accepts one exact Context or one direct item. | Reading the complete content of a known item or Context. |
| Browse & Navigate | switch | NO | Context locator → current Context pointer | Enter the interactive Context picker, or switch to an explicit Context. | Changes only the current pointer; the destination must already exist. | Moving the working position to another existing Context. |
| Browse & Navigate | checkout | NO | Context locator → current Context or new branch | Switch Contexts using Git-style syntax; with -b, create and switch to a new Context branch. | Switches Context; -b additionally creates a branch. | Using a Git-like workflow to switch or create a branch. |
| Create, Copy & Connect | init | NO | New Context name → Context | Create a new empty Context and make it the current working Context. | By default creates only the exact requested Context; `-p` creates missing parent Contexts and reuses existing parents without embedding children. | Starting a separate workspace for a new topic, task, or group of Memories. |
| Create, Copy & Connect | branch | NO | Context → new Context branch | Copy a Context or subtree into a new branch and switch to it. | Creates a copied Context or subtree and changes the current pointer. | Editing a Context or subtree independently while preserving the original. |
| Create, Copy & Connect | import | NO | External resource → local owned copy | Import a clean-baseline Profile, Context tree, or Memory by value while preserving resource identity. | **PARTIAL.** Currently limited to MemCommit-to-MemCommit transfer: Profiles from an external `.mem` store or package, and Profiles, Context trees, or Memories from another registered Profile. Arbitrary documents, Skills, and Export are not yet implemented. | Bringing externally supplied material into a locally managed store. |
| Create, Copy & Connect | embed | NO | Source Memory or Child Context → Target placement | Place a live link to one Memory or Context inside a local Target while retaining Source ownership. | Changes Target structure; Source identity and ownership remain intact. | Reusing a Memory or Context in another Context while following later Source changes. |
| Create, Copy & Connect | add | NO | Text or file → Context Memories | Add one or more Memories to the current or explicit Context. | Changes one exact target Context. | Adding one or more facts, instructions, or notes directly to a Context. |
| Create, Copy & Connect | reference | NO | Source Memory or Context scope → Target snapshot | Copy one direct Source Memory version or direct/recursive Context scope into a Target as an immutable read-only snapshot. | Adds a self-contained snapshot to the Target; `-r` includes lexical descendants and local embedded Contexts, while the Source stays unchanged. | Retaining exact Memory or Context evidence even if its Source later changes or disappears. |
| Deterministic Content Changes | edit | NO | Memory or Memory batch → replacement content | Directly replace the content of one or more Memories selected by UID or prefix. | Changes only the selected directly owned Memories in one exact Context. | Directly correcting or replacing the content of specific existing Memories. |
| Deterministic Content Changes | replace | NO | Text pattern + replacement + local Context scope → reviewed exact changes → atomic Apply | Preview and replace every literal or explicit regular-expression match in ordinary local Memories. | Preview is read-only; Apply changes matched local Memories in one Undo/Redo command unit. Lexical-descendant and embedded-owner reach are independent. | Correcting, renaming, or redacting exact text throughout a known local Context scope. |
| Deterministic Content Changes | chunk | NO | Context direct Memories or one direct Memory → ordered Memory chunks | Mechanically split all splittable direct Memories in one Context, or one selected Memory, at configured sentence, clause, structural, literal, or size boundaries. | Immediately changes one Source Context; Undo can restore the checkpointed split. | One or more direct Memories already have clear sentence or structural boundaries that should become separate Memories. |
| Deterministic Content Changes | delete | NO | Context or direct item → removed | Select a Context or direct item to delete, or name it by locator, name, or UID. | Destructive; removes one exact Context or direct item after confirmation. | Removing a specific Context or item that is no longer needed. |
| Deterministic Content Changes | clear | NO | Context or local lexical subtree direct items → empty retained Contexts | Immediately remove all direct items from one Context or, with `--recursive`, its local lexical subtree and record the complete command for Undo/Redo. | Destructive but checkpointed; exact by default, while recursive scope is one exception-atomic command unit and does not follow embeds or cross Grant boundaries. | Emptying a Context or local lexical subtree while retaining every Context. |
| Deterministic Content Changes | merge | NO | A · Source Context → B · selected Target Context | Add Source-only items to a selected Target, leave exact matches unchanged, and choose Source or Target for stored-item conflicts. | This is not a three-way or semantic merge. Source-only items are added, exact identity-and-value matches remain unchanged, conflicts require an explicit deterministic Source/Target decision, Target-only items remain, and recursive Merge aligns descendants by complete relative path. | Appending Source-only items or bringing a copied or branched Context into a selected Target Context without semantic synthesis. |
| Deterministic Content Changes | dedup | NO | Confirmed duplicate handoffs → reviewed survivors → exact Apply | Review confirmed duplicate groups, retain one existing Memory in each group, and delete the rest on Apply. | Read-only until exact Apply; Apply deletes absorbed UIDs in one checkpoint within one exact direct Context. | Removing confirmed semantic duplicates while preserving one exact existing Memory and its UID. |
| Search & Explain | find | NO | Text pattern + Context scope → exact Memory spans | Find exact text or explicit regular-expression (regex) matches in readable Memories. | Read-only; one or more readable Context roots, with optional descendants and embedded Contexts. | Locating exact words, identifiers, or text patterns within a selected Context scope. |
| Search & Explain | search | YES · CACHE OR PROVIDER | Context set + query → ranked Memories | Semantically rank Memories relevant to a natural-language request across selected Contexts. | Results are read-only; optional reviewed Save As creates a new local Context. Lexical-descendant and embedded-Context reach are independently selectable. | Finding relevant Memories through meaning and context, including related content without obvious keyword overlap. |
| Search & Explain | query | YES · CACHE OR PROVIDER | Readable source + question → answer with references | Generate an LLM-based answer from readable Context knowledge or an authorized concealed query-only view. | Does not change Context content; a visible transcript may be retained. Uses one readable exact, descendant, or embedded Context scope, or one QUERY-authorized query-only view. QUERY-only access may answer within its granted boundary while concealing complete Source Memories and the full underlying policy. | Getting a grounded natural-language answer instead of a list of matching Memories. |
| Search & Explain | summarize | YES · CACHE OR PROVIDER | Context → summary | Show an LLM-derived overview of ordinary Memories in a readable Context scope. | Read-only; one readable Context, optionally including readable lexical descendants and embedded Contexts; ordinary Memories only. | Obtaining a concise overview of a Context or subtree. |
| History & Recovery | trace | NO | Memory → retained lineage | Trace one retained Memory through its recorded lineage. | Read-only; requires one current or historical Memory. | Determining where a Memory came from and how it changed. |
| History & Recovery | rationale | YES | Retained Trace + calibrated examples → natural provenance receipt | Explain where one Memory came from and how it changed over time. | Read-only; one whole-Trace semantic turn, skipped when history is absent or hidden. | Understanding the source context and lifecycle of one Memory. |
| Check, Compare & Review | find-duplicates | YES · CACHE OR PROVIDER | Context Memories → duplicate report | Report duplicate direct Memories in the current or explicit Context; no Context changes. | Analyzes one exact direct Context and does not modify it. | Locating semantically redundant Memories before cleanup. |
| Check, Compare & Review | find-ambiguities | YES · CACHE OR PROVIDER | Context Memories → ambiguity report | Report ambiguous direct Memories in the current or explicit Context; no Context changes. | Analyzes one exact direct Context and does not modify it. | Finding Memories that permit unclear or multiple interpretations. |
| Check, Compare & Review | find-conflicts | YES · CACHE OR PROVIDER | Context Memories → conflict report | Report conflicting direct Memory pairs in the current or explicit Context; no Context changes. | Analyzes one exact direct Context and does not modify it. | Finding mutually incompatible claims or instructions. |
| Check, Compare & Review | audit | YES · CACHE OR PROVIDER | Context + Rules? → saved Audit report | Run Duplicate, Ambiguity, and Conflict checks plus optional Rule Conformance, then review the combined saved result. | Changes no Context content; analyzes one exact direct Context. | Performing a combined quality review before revising a Context. |
| Semantic Transformations | atomize | YES · CACHE OR PROVIDER | Context Memories → reviewed atomic Memories | Analyze composite Memories and separate their distinct propositions into independently reviewable Memories. | Material changes occur only after explicit acceptance. Ordinary Atomize separates propositions; `--evaluate` instead performs an issue-scoped directional Meld. | Untangling requirements or claims that were written together so each can be reviewed and revised independently. |
| Semantic Transformations | distill | YES · EXACT PREPARED OR PROVIDER | Case/Example Context + Goal? → reviewed Rules | Derive higher-level Rules or condition propositions from Case or Example propositions in a bounded Context, optionally guided by a Goal. | Source and Ground stay unchanged; standalone Apply may create a new Result. The bounded Source supplies support, while the optional Goal focuses the direction. | Inferring more general Rules or condition propositions from several concrete cases or examples. |
| Semantic Transformations | elaborate | YES · EXACT PREPARED OR PROVIDER | Goal → suggested Rules; Rules → suggested Case propositions | Expand an abstract Goal, Rule, or condition into multiple more specific candidate propositions. | Read-only; every proposal remains suggested and unverified. | Generating several more concrete candidate Rules or Cases from an abstract concept or condition. |
| Check, Compare & Review | compare | YES · CACHE OR PROVIDER | Context ↔ Context → comparison report | Compare Memories in two Contexts and report what they share, what differs, and what appears only on one side. | Neither Context changes or serves as the authority; each may be exact or include readable descendants. | Comparing two Contexts as a whole to understand where they align and differ. |
| Check, Compare & Review | impact | DEPENDS ON FORM | Operation inputs or session → impact report | Preview or inspect an operation's expected Context effects without applying them. | Impact is read-only; Apply remains a separate reviewed action. Operation-specific Impact uses `mem impact OPERATION`; omitting `OPERATION` selects directional Update preview and requires `--from` or `--to`. | Verifying an operation's proposed effects before its separate Apply action. |
| Check, Compare & Review | review | DEPENDS ON FORM | Saved semantic artifact → report and optional review responses | Open a saved semantic artifact to inspect its analysis, proposal, or result state and, when supported, record review responses. Review never applies Memories. | Records supported review responses but never materializes Memory changes. | Revisiting a saved analysis, proposal, or result state. |
| Semantic Transformations | resolve | YES · CACHE OR PROVIDER | Bounded Context frame + optional guidance → verified repair candidates → exact Apply | Propose and verify minimum changes that make one bounded direct-Memory Context frame Fit YES. | Read-only until one exact candidate is explicitly applied; Apply changes one bounded direct Context frame, while explicit Memory UID prefixes limit mutation targets. | Deciding how to repair semantic conflicts or ambiguities within a bounded Context frame. |
| Semantic Transformations | meld | YES · CACHE OR PROVIDER | PEER A + PEER B → RESULT; INCOMING → EXISTING TARGET | Semantically reconcile two Contexts, either into a separate Result or by incorporating proposed changes into an existing Target Context. | Symmetric mode requires a distinct empty Result; directional mode changes only the existing Target after reviewed Apply. | Combining two bodies of work when overlap, conflicts, and newly synthesized content must be reviewed semantically. |
| Semantic Transformations | update | YES · CACHE OR PROVIDER | Source Context → Target Context | Update Memories in the Target Context from Memories in the Source Context, asking the user to review and choose when needed. | Only the local Target changes after Apply. | Updating an existing Context using newly verified Memories. |
| Semantic Transformations | sever | YES · CACHE OR PROVIDER | Source Context + Criteria Context → self-save Source or other-save Result | Save a Result by selecting, transforming, or excluding Source Memories according to a Criteria Context. | Updates Source by default, or creates an explicit new Result; records a receipt. | Selecting or transforming Source content according to defined criteria. |
| Semantic Transformations | translate | YES · CACHE OR PROVIDER | Context or Memory → translated view or materialization | Generate and save a reusable translated view of one Context or Memory while preserving the original content. | Source remains unchanged; `--save-as` creates a translated Context and `--in-place` adds translated sibling Memories. | Reading or reusing Memory content in another language without replacing the original. |
| Semantic Transformations | forget | YES · CACHE OR PROVIDER | Context + instruction → reviewed curation batch | Review keep/edit/delete decisions for one instruction, then apply the accepted batch. | Evaluates one complete direct Source frame; Source changes only after acceptance. | Removing or rewriting Memories according to a natural-language instruction whose meaning must be interpreted. |
| History & Recovery | log | DEPENDS ON FORM | Recorded history or query → history report | Print or search recorded Context, Memory, and Profile history. | Read-only static report; scope is one Context, one Memory lineage, or Profile attempts. | Investigating previous operations, checkpoints, or Memory history. |
| History & Recovery | diff | NO | Context checkpoint or active Update → diff report | Show the differences recorded by a Context checkpoint or the active Update. | Read-only; compares one exact Context history or active Update. | Verifying exactly what a recorded operation changed. |
| History & Recovery | checkpoint | NO | Context state → checkpoint | Save the current Context as a manual recovery point for Diff or Revert. | Adds history metadata without changing Context content. | Creating a recovery point before risky work. |
| History & Recovery | undo | NO | Command history → reversed Context effects | Undo the most recent recorded command as one unit. | Restores every Context and Memory change recorded by that command. | Reversing the latest recorded mutation as one operation. |
| History & Recovery | redo | NO | Undo history → restored command effects | Redo the most recently undone recorded Context command. | Restores the affected Context set from the most recent Undo. | Reapplying a command that was undone accidentally. |
| History & Recovery | revert | DEPENDS ON FORM | Checkpoint → restored Context state | Restore the current or an explicit local Context to a selected checkpoint after reviewing that revision's complete result. | Restores one Context; interactive or semantic selection requires reviewed confirmation. | Restoring a Context to a deliberately saved recovery point. |
| Ground Workbench | ground | YES · CACHE OR PROVIDER | Dialogue + evidence → reviewed Ground | Develop an abstract idea into a reviewable Ground by shaping its Goal, Rules, and example Memories together. | Creates or changes only Ground workspace Contexts; external Context changes require separate operations. | Working out how an abstract goal should operate in practice through jointly revised Rules and concrete Examples. |
| Check, Compare & Review | fit | YES · CACHE OR PROVIDER | Propositions + optional background → YES / MAY / NO; Ground + bound Contexts → complete Fit receipt | Judge whether a defined set of Memories or other propositions is jointly compatible under ordinary interpretation, returning YES, MAY, or NO. | Changes no Context, Ground, Rule, Goal, or Memory. YES means compatible across materially ordinary readings, MAY means ordinary readings split, and NO means incompatible across them; Fit does not establish truth or evidential support. | Checking whether a defined set of Memories, Rules, Goals, Examples, or other propositions can jointly hold. |
| Check, Compare & Review | check-conformance | YES · CACHE OR PROVIDER | Rules or condition propositions + Ground Examples or Context → Conformance report | Check one Context or saved Ground Examples against explicit Rules or condition propositions and report conformance issues. | Read-only; Fit asks whether propositions coexist, while Conformance asks whether selected subjects satisfy stated Rules or condition propositions. | Verifying whether existing Memories or Examples satisfy stated Rules or condition propositions. |
| System & Study Tools | init-study | NO | Study baseline → isolated Study Profiles | Copy one Study baseline into an isolated participant/authority Profile pair. | Creates isolated Profile stores and switches the active Profile. | Preparing a reproducible, isolated user-study environment. |
| System & Study Tools | eval | DEPENDS ON FORM | Fixed evaluation fixtures → retained campaign results | Run and inspect the existing semantic evaluation campaigns. | Changes evaluation ledgers, not Context content. | Using the existing research evaluation harness while the general evaluation interface is redesigned. |
| Profiles | profile | NO | Profile registry ↔ Profile administration | Select and manage complete local MemoryStore Profiles. Profiles can also be renamed or permanently removed through the picker or with `mem profile rename` and `mem profile remove`. | May switch, import, rename, or permanently remove Profiles; Grant subcommands manage cross-Profile views. | Managing separate users, environments, or Memory stores. |
| Profiles | rename | NO | Managed Profile name → new Profile name | Rename the current or an explicit managed Profile without moving or rewriting its store; mem profile rename is the explicit equivalent. | Changes registry metadata only; store contents remain in place. | Giving an existing managed Profile a clearer name. |
| Sharing & Protection | share | NO | Owned Context scope → receiver endpoint | Send one exact Context or lexical Context subtree through a grant-backed receiver endpoint. | `-d` sends the exact Source and `-r` sends the Source plus all lexical descendants as one reviewed bundle; Source remains unchanged. | Delivering one owned Context or a related Context bundle to an authorized receiver. |
| Sharing & Protection | lock | NO | Resource → write-protected resource | Lock the current Context, a recursive Context set, Memory, or Profile. | Changes protection metadata for an exact resource or recursive Context set. | Preventing accidental modification of stable material. |
| Sharing & Protection | unlock | NO | Protected resource → writable resource | Unlock the current Context, a recursive set, Memory, or Profile. | Removes protection metadata from the selected resource scope. | Reopening protected material for intentional revision. |
| System & Study Tools | help | NO | Operation catalog → usage guidance | Enter the interactive command browser and open syntax help. | Read-only; does not execute the selected operation. | Discovering available operations and their invocation forms. |
| System & Study Tools | provider | NO | Provider configuration ↔ status or probe | Select and verify Codex, Ollama, or OpenRouter semantic execution. | May change provider configuration or make a probe request. | Choosing which backend semantic operations should use, or checking that it is ready before durable work. |
| System & Study Tools | shell-init | NO | Shell name → integration script | Print opt-in shell integration for interactive command prefill. | Read-only output; installation requires explicit shell evaluation. | Enabling optional shell-specific conveniences. |
| System & Study Tools | config | NO | Configuration key ↔ value | Read or write stored global configuration values. | May change global configuration. | Inspecting or changing stored global settings through the legacy low-level interface. |

## Korean review table

| 범주 | 이름 | LLM | 흐름 | 설명 | 경계 | 적합한 상황 |
|---|---|---|---|---|---|---|
| 탐색 및 이동 | status | 없음 | 현재 Context 상태 + 이력 → 상태 보고서 | 현재 Context의 항목별 개수, 처음 다섯 개의 직접 Memory, 연결 관계와 최근 checkpoint를 보여줍니다. | 읽기 전용이며 기본적으로 현재 Context를 다루고, `-r`은 읽을 수 있는 하위 및 embedded Context를 포함합니다. | 현재 Context에 무엇이 있고, 어떻게 연결되어 있으며, 최근 어떤 작업이 적용되었는지 빠르게 파악할 때. |
| 탐색 및 이동 | pwd | 없음 | 현재 Context 포인터 → 정규 이름 | 내용을 불러오지 않고 현재 Context의 정규 이름을 출력합니다. | 포인터만 읽으며 Context 내용은 불러오지 않습니다. | 스크립트나 터미널에서 현재 Context를 확인할 때. |
| 탐색 및 이동 | contexts | 없음 | Profile 접근 권한 → 읽을 수 있는 Context 목록 | 전환하지 않고 로컬 Context와 다른 Profile에서 읽을 수 있는 Context를 탐색합니다. | 읽기 전용이며 현재 Context를 변경하지 않습니다. | 현재 Profile에서 접근 가능한 모든 Context를 살펴볼 때. |
| 탐색 및 이동 | list | 없음 | Context → 하위 Context 및 직접 항목 목록 | 하위 Context와 직접 항목을 탐색합니다. ls는 동일한 축약형입니다. | 읽기 전용이며 정확한 Context 하나 또는 그 하위 범위를 다룹니다. | Context의 구조와 직접 포함된 항목을 확인할 때. |
| 탐색 및 이동 | show | 없음 | Context 또는 직접 항목 → 렌더링된 내용 | Memory, reference, embedded Context 또는 Context의 직접 내용을 보여줍니다. | 정확한 Context 하나 또는 직접 항목 하나를 읽기만 합니다. | 알고 있는 항목이나 Context의 전체 내용을 읽을 때. |
| 탐색 및 이동 | switch | 없음 | Context locator → 현재 Context 포인터 | Context picker를 열거나 명시한 Context로 전환합니다. | 기존 Context로 현재 포인터만 변경합니다. | 작업 위치를 다른 기존 Context로 옮길 때. |
| 탐색 및 이동 | checkout | 없음 | Context locator → 현재 Context 또는 새 branch | Git과 유사한 문법으로 Context를 전환하며 -b 사용 시 branch를 만들고 전환합니다. | Context를 전환하며 -b는 새 branch도 생성합니다. | Git과 비슷한 방식으로 전환하거나 branch를 만들 때. |
| 생성·복사·연결 | init | 없음 | 새 Context 이름 → Context | 새로운 빈 Context를 만들고 현재 작업 Context로 전환합니다. | 기본적으로 요청한 Context만 만들며, `-p`는 누락된 상위 Context를 만들고 기존 상위 Context를 재사용하지만 Child를 embed하지는 않습니다. | 새로운 주제, 작업 또는 Memory 묶음을 위한 별도의 작업 공간을 시작할 때. |
| 생성·복사·연결 | branch | 없음 | Context → 새 Context branch | Context 또는 subtree를 새 branch로 복사하고 그곳으로 전환합니다. | 복사본을 만들고 현재 Context도 변경합니다. | 원본을 유지하면서 Context 또는 subtree를 독립적으로 수정할 때. |
| 생성·복사·연결 | import | 없음 | 외부 리소스 → 로컬 소유 복사본 | Profile, Context tree 또는 Memory를 identity를 보존하며 값으로 가져옵니다. | **부분 구현.** 현재 MemCommit 간 전송만 지원합니다. 외부 `.mem` store/package의 Profile과 다른 등록 Profile의 Profile·Context tree·Memory를 가져올 수 있지만, 임의 문서·Skill 변환과 Export는 아직 구현되지 않았습니다. | 외부 자료를 로컬에서 관리할 수 있는 형태로 가져올 때. |
| 생성·복사·연결 | embed | 없음 | Source Memory 또는 Child Context → Target 배치 | Source ownership을 유지한 채 Memory 또는 Context의 live link를 local Target 안에 배치합니다. | Target 구조만 변경되며 Source identity와 ownership은 유지됩니다. | 이후 Source 변경을 계속 반영하면서 Memory나 Context를 다른 Context에서 재사용할 때. |
| 생성·복사·연결 | add | 없음 | 텍스트 또는 파일 → Context Memory | 현재 또는 명시한 Context에 하나 이상의 Memory를 추가합니다. | 정확한 Target Context 하나를 변경합니다. | 사실, 지침 또는 노트를 하나 이상 Context에 직접 추가할 때. |
| 생성·복사·연결 | reference | 없음 | Source Memory 또는 Context 범위 → Target snapshot | 직접 Source Memory 버전이나 직접/재귀 Context 범위를 변경 불가능한 읽기 전용 snapshot으로 Target에 복사합니다. | Target에 self-contained snapshot을 추가합니다. `-r`은 lexical descendant와 로컬 embedded Context를 포함하며 Source는 바뀌지 않습니다. | Source가 나중에 바뀌거나 사라져도 정확한 Memory 또는 Context 근거를 보존할 때. |
| 결정론적 내용 변경 | edit | 없음 | Memory 또는 Memory batch → 대체 내용 | UID 또는 prefix로 지정한 Memory 하나 이상의 내용을 직접 교체합니다. | 하나의 정확한 Context에서 선택된 직접 소유 Memory만 변경합니다. | 특정한 기존 Memory의 내용을 직접 바로잡거나 교체할 때. |
| 결정론적 내용 변경 | replace | 없음 | 텍스트 패턴 + 대체 문자열 + 로컬 Context 범위 → 검토된 정확 일치 변경 → 원자적 Apply | 일반 로컬 Memory에서 모든 literal 또는 명시적 regular-expression 일치를 미리 확인하고 교체합니다. | Preview는 읽기 전용이며 Apply는 일치한 로컬 Memory를 하나의 Undo/Redo command 단위로 변경합니다. lexical descendant와 embedded owner 범위는 서로 독립적입니다. | 알고 있는 로컬 Context 범위 전체에서 정확한 텍스트를 수정·이름 변경·가림 처리할 때. |
| 결정론적 내용 변경 | chunk | 없음 | Context 직접 Memory 또는 직접 Memory 하나 → 순서가 있는 Memory 조각 | 한 Context에서 나눌 수 있는 모든 직접 Memory 또는 선택한 Memory 하나를 설정한 문장·절·구조·리터럴·크기 경계에서 기계적으로 나눕니다. | Source Context 하나를 즉시 변경하며 Undo로 checkpointed split을 복원할 수 있습니다. | 하나 이상의 직접 Memory에 이미 분명한 문장 또는 구조 경계가 있고 이를 별도 Memory로 만들 때. |
| 결정론적 내용 변경 | delete | 없음 | Context 또는 직접 항목 → 제거 | Context나 직접 항목을 선택하거나 locator, 이름 또는 UID로 지정해 삭제합니다. | 파괴적 작업이며 확인 후 정확한 항목 하나를 제거합니다. | 더 이상 필요하지 않은 특정 Context나 항목을 제거할 때. |
| 결정론적 내용 변경 | clear | 없음 | Context 직접 항목 → 빈 Context | 현재 또는 명시한 Context의 모든 직접 항목을 즉시 제거하고 Undo/Redo용 명령 기록을 남깁니다. | 파괴적이지만 체크포인트로 기록되며, 하나의 정확한 Context에 있는 모든 직접 항목에 영향을 줍니다. | Context는 남겨두고 그 안의 직접 내용만 비울 때. |
| 결정론적 내용 변경 | merge | 없음 | A · Source Context → B · 선택한 Target Context | Source에만 있는 항목을 선택한 Target에 추가하고, 정확히 같은 항목은 유지하며, 저장 항목이 충돌하면 Source 또는 Target을 선택합니다. | 3-way 또는 semantic merge가 아닙니다. Source-only 항목은 추가하고, identity와 값이 정확히 같은 항목은 유지하며, 충돌은 Source/Target 중 하나를 결정론적으로 선택합니다. Target-only 항목은 남고 recursive Merge는 완전한 상대 경로로 descendant를 정렬합니다. | Source에만 있는 항목을 덧붙이거나 복사·분기한 Context의 작업을 의미적 합성 없이 선택한 Target Context로 가져올 때. |
| 결정론적 내용 변경 | dedup | 없음 | 확인된 중복 handoff → 검토한 survivor → exact Apply | 확인된 중복 묶음을 검토하고, 각 묶음에서 기존 Memory 하나를 남긴 뒤 Apply 시 나머지를 삭제합니다. | exact Apply 전에는 읽기 전용이며, Apply는 하나의 정확한 직접 Context에서 흡수되는 UID를 한 checkpoint로 삭제합니다. | 의미상 중복임이 확인된 Memory를 정리하면서 기존 Memory 하나와 그 UID를 보존할 때. |
| 검색 및 설명 | find | 없음 | 텍스트 패턴 + Context 범위 → 정확한 Memory 일치 구간 | 읽을 수 있는 Memory에서 정확한 텍스트 또는 명시적인 정규식(regex) 일치를 찾습니다. | 읽기 전용이며 하나 이상의 읽을 수 있는 Context root를 대상으로 하고, descendant와 embedded Context 포함 여부를 선택할 수 있습니다. | 선택한 Context 범위에서 정확한 단어, identifier 또는 텍스트 패턴을 찾을 때. |
| 검색 및 설명 | search | 있음 · 캐시 또는 Provider | Context 집합 + query → 순위가 매겨진 Memory | 선택한 Context에서 자연어 요청과 의미상 관련된 Memory의 순위를 매깁니다. | 결과는 읽기 전용이며, 검토한 Save As를 선택하면 새 로컬 Context를 만듭니다. Lexical descendant와 embedded Context 범위는 독립적으로 선택합니다. | 의미와 맥락으로 관련 Memory를 찾을 때. 눈에 띄는 키워드가 겹치지 않는 관련 내용도 포함합니다. |
| 검색 및 설명 | query | 있음 · 캐시 또는 Provider | 읽을 수 있는 Source + 질문 → reference가 포함된 답변 | 읽을 수 있는 Context 지식 또는 승인된 비공개 query-only view를 바탕으로 LLM 답변을 생성합니다. | Context 내용은 변경하지 않으며 보이는 대화 기록은 유지될 수 있습니다. 읽을 수 있는 정확한 Context·descendant·embedded 범위 또는 QUERY 권한이 있는 query-only view 하나를 사용합니다. QUERY-only 접근은 허용된 범위 안의 질문에는 답하면서 전체 Source Memory와 기반 정책 전체를 숨길 수 있습니다. | 일치하는 Memory 목록 대신 근거 있는 자연어 답변을 받을 때. |
| 검색 및 설명 | summarize | 있음 · 캐시 또는 Provider | Context → 요약 | 읽을 수 있는 Context 범위의 일반 Memory를 바탕으로 LLM 개요를 보여줍니다. | 읽기 전용이며 읽을 수 있는 Context 하나를 대상으로, lexical descendant와 embedded Context를 선택적으로 포함합니다. 일반 Memory만 사용합니다. | Context나 subtree의 간결한 개요를 얻을 때. |
| 기록 및 복구 | trace | 없음 | Memory → 보존된 lineage | 기록된 lineage를 따라 현재 또는 과거의 Memory 하나를 추적합니다. | 읽기 전용이며 Memory 하나만 다룹니다. | Memory의 출처와 변경 과정을 확인할 때. |
| 기록 및 복구 | rationale | 있음 | 보존된 Trace + 교정 사례 → 자연어 provenance receipt | Memory 하나가 어디서 나왔고 시간에 따라 어떻게 바뀌었는지 설명합니다. | 읽기 전용이며 전체 Trace를 한 번에 해석합니다. history가 없거나 숨겨졌으면 provider를 연결하지 않습니다. | Memory 하나의 원래 맥락과 lifecycle을 이해할 때. |
| 검사·비교·검토 | find-duplicates | 있음 · 캐시 또는 Provider | Context Memory → 중복 보고서 | 현재 또는 명시한 Context의 직접 Memory 중 중복을 보고합니다. | 정확한 직접 Context 하나를 분석하며 내용을 변경하지 않습니다. | 정리 전에 의미상 중복된 Memory를 찾을 때. |
| 검사·비교·검토 | find-ambiguities | 있음 · 캐시 또는 Provider | Context Memory → 모호성 보고서 | 현재 또는 명시한 Context에서 모호한 직접 Memory를 보고합니다. | 정확한 직접 Context 하나를 분석하며 내용을 변경하지 않습니다. | 여러 해석이 가능한 불명확한 Memory를 찾을 때. |
| 검사·비교·검토 | find-conflicts | 있음 · 캐시 또는 Provider | Context Memory → 충돌 보고서 | 현재 또는 명시한 Context에서 서로 충돌하는 직접 Memory 쌍을 보고합니다. | 정확한 직접 Context 하나를 분석하며 내용을 변경하지 않습니다. | 양립할 수 없는 주장이나 지침을 찾을 때. |
| 검사·비교·검토 | audit | 있음 · 캐시 또는 Provider | Context + 선택적 Rule → 저장된 Audit 보고서 | 중복·모호성·충돌 검사와 선택적 Rule Conformance를 실행한 뒤, 합쳐서 저장된 결과를 검토합니다. | Context 내용을 변경하지 않으며 정확한 direct Context 하나를 분석합니다. | Context를 수정하기 전에 종합적인 품질 검사를 수행할 때. |
| 의미 기반 변환 | atomize | 있음 · 캐시 또는 Provider | Context Memory → 검토 가능한 원자적 Memory | 여러 내용이 얽힌 복합 Memory를 분석하고, 서로 다른 명제를 독립적으로 검토 가능한 Memory로 분리합니다. | 명시적으로 승인한 후에만 자료가 변경됩니다. 일반 Atomize는 명제를 분리하고 `--evaluate`는 issue 범위의 directional Meld를 수행합니다. | 뒤섞여 작성된 요구사항이나 주장을 각각 독립적으로 검토하고 수정할 수 있게 풀어낼 때. |
| 의미 기반 변환 | distill | 있음 · 정확한 준비 결과 또는 Provider | Case/Example Context + 선택적 Goal → 검토 가능한 Rule | bounded Context의 Case 또는 Example 명제에서 상위 Rule이나 조건 명제를 도출하며, 선택적인 Goal로 방향을 제시할 수 있습니다. | Source와 Ground는 유지되며 독립 실행의 Apply만 새 Result를 만들 수 있습니다. bounded Source는 근거 명제를 제공하고 선택적 Goal은 도출 방향에 초점을 맞춥니다. | 여러 구체적인 사례나 예시에서 더 일반적인 Rule이나 조건 명제를 도출할 때. |
| 의미 기반 변환 | elaborate | 있음 · 정확한 준비 결과 또는 Provider | Goal → 제안된 Rule; Rule → 제안된 Case 명제 | 추상적인 Goal·Rule 또는 조건을 여러 개의 더 구체적인 후보 명제로 확장합니다. | 읽기 전용이며 모든 제안은 제안 상태이자 미검증 상태로 남습니다. | 추상적인 개념이나 조건에서 더 구체적인 Rule 또는 Case 후보를 여러 개 만들 때. |
| 검사·비교·검토 | compare | 있음 · 캐시 또는 Provider | Context ↔ Context → 비교 보고서 | 두 Context의 Memory를 비교해 공통점, 차이점, 한쪽에만 있는 내용을 보고합니다. | 두 Context 모두 변경하지 않으며 어느 쪽도 기준으로 삼지 않습니다. 각 범위는 정확한 Context 또는 읽을 수 있는 하위 Context를 포함할 수 있습니다. | 두 Context를 전체적으로 비교해 어디가 같고 다른지 이해할 때. |
| 검사·비교·검토 | impact | 형식에 따라 다름 | Operation 입력 또는 session → 영향 보고서 | operation이 Context에 미칠 예상 효과를 적용하지 않고 미리 보거나 검사합니다. | Impact 자체는 읽기 전용이며 Apply는 별도의 검토 작업입니다. operation별 Impact는 `mem impact OPERATION`으로 실행하고, `OPERATION`을 생략하면 `--from` 또는 `--to`가 필요한 directional Update preview가 됩니다. | 별도의 Apply 전에 operation이 제안한 효과를 확인할 때. |
| 검사·비교·검토 | review | 형식에 따라 다름 | 저장된 semantic artifact → 보고서와 선택적 검토 응답 | 저장된 semantic artifact를 열어 분석·제안·결과 상태를 확인하고, 지원되는 경우 검토 응답을 기록합니다. Review 자체는 Memory를 적용하지 않습니다. | 지원되는 검토 응답만 기록하며 Memory 변경을 materialize하지 않습니다. | 저장된 분석·제안·결과 상태를 다시 확인할 때. |
| 의미 기반 변환 | resolve | 있음 · 캐시 또는 Provider | bounded Context frame + 선택적 guidance → 검증된 repair 후보 → exact Apply | 하나의 bounded direct-Memory Context frame이 Fit YES가 되도록 최소 변경안을 제안하고 검증합니다. | 하나의 정확한 후보를 명시적으로 Apply하기 전에는 읽기 전용이며, Apply는 bounded direct Context frame 하나를 변경합니다. 명시한 Memory UID prefix는 mutation target만 제한합니다. | bounded Context frame 안의 의미적 충돌이나 모호성을 어떻게 해결할지 판단할 때. |
| 의미 기반 변환 | meld | 있음 · 캐시 또는 Provider | PEER A + PEER B → RESULT; INCOMING → EXISTING TARGET | 두 Context를 의미적으로 조정하여 별도의 Result를 만들거나, 제안된 변경을 기존 Target Context에 반영합니다. | 대칭 모드는 서로 구별되는 빈 Result가 필요하며, 방향 모드는 검토된 Apply 후 기존 Target만 변경합니다. | 두 작업 묶음의 중복·충돌과 새로 합성된 내용을 의미적으로 검토하며 통합해야 할 때. |
| 의미 기반 변환 | update | 있음 · 캐시 또는 Provider | Source Context → Target Context | Source Context의 Memory를 바탕으로 Target Context의 Memory를 업데이트하고, 필요할 때 사용자에게 검토와 선택을 요청합니다. | Apply 후 로컬 Target만 변경됩니다. | 새롭게 검증된 Memory를 바탕으로 기존 Context를 업데이트할 때. |
| 의미 기반 변환 | sever | 있음 · 캐시 또는 Provider | Source Context + Criteria Context → 새 Result Context | Criteria Context에 따라 Source Memory를 선별·변환하거나 제외한 Result를 생성합니다. | 검토된 새 Result를 만들며 Source는 변경하지 않습니다. | 정해진 기준에 따라 Source 내용을 선별하거나 변환하고 싶을 때. |
| 의미 기반 변환 | translate | 있음 · 캐시 또는 Provider | Context 또는 Memory → 번역 view 또는 materialization | 원본 내용을 보존하면서 Context 또는 Memory 하나의 재사용 가능한 번역 view를 생성하고 저장합니다. | Source는 유지되며 `--save-as`는 번역 Context를 만들고 `--in-place`는 번역 sibling Memory를 추가합니다. | 원본을 교체하지 않고 Memory 내용을 다른 언어로 읽거나 재사용할 때. |
| 의미 기반 변환 | forget | 있음 · 캐시 또는 Provider | Context + 지시 → 검토 가능한 선별 batch | 하나의 지시에 대한 유지·편집·삭제 결정을 검토하고 승인한 batch를 적용합니다. | 완전한 직접 Source frame을 한 번에 평가하며 승인 후에만 Source가 변경됩니다. | 의미를 해석해야 하는 자연어 지침에 따라 Memory를 제거하거나 다시 작성할 때. |
| 기록 및 복구 | log | 형식에 따라 다름 | 기록된 history 또는 query → history 보고서 | 기록된 Context, Memory 및 Profile history를 탐색하거나 검색합니다. | 읽기 전용이며 범위는 Context 하나, Memory lineage 하나 또는 Profile 시도 기록입니다. | 이전 작업, checkpoint 또는 Memory 기록을 조사할 때. |
| 기록 및 복구 | diff | 없음 | Context checkpoint 또는 활성 Update → diff 보고서 | Context checkpoint 또는 활성 Update에 기록된 차이를 보여줍니다. | 읽기 전용이며 정확한 Context history 또는 활성 Update를 비교합니다. | 기록된 작업이 정확히 무엇을 변경했는지 확인할 때. |
| 기록 및 복구 | checkpoint | 없음 | Context 상태 → checkpoint | 현재 Context를 Diff 또는 Revert에 사용할 수동 복구 지점으로 저장합니다. | Context 내용은 변경하지 않고 history metadata만 추가합니다. | 위험한 작업 전에 복구 지점을 만들 때. |
| 기록 및 복구 | undo | 없음 | Command history → 되돌린 Context 효과 | 가장 최근에 기록된 command를 하나의 단위로 Undo합니다. | 그 command에 기록된 모든 Context 및 Memory 변경을 복구합니다. | 최근 mutation 전체를 하나의 작업으로 되돌릴 때. |
| 기록 및 복구 | redo | 없음 | Undo history → 복구된 command 효과 | 가장 최근에 Undo한 Context command를 다시 실행합니다. | 최근 Undo가 영향을 준 Context 집합을 복구합니다. | 실수로 되돌린 작업을 다시 적용할 때. |
| 기록 및 복구 | revert | 형식에 따라 다름 | Checkpoint → 복구된 Context 상태 | 현재 또는 명시한 로컬 Context를 선택한 checkpoint로 복원하기 전에 해당 revision의 완전한 결과 상태를 검토합니다. | Context 하나를 복구하며 대화형 또는 semantic 선택에는 검토된 확인이 필요합니다. | Context를 의도적으로 저장한 복구 지점으로 되돌릴 때. |
| Ground Workbench | ground | 있음 · 캐시 또는 Provider | 대화 + 근거 → 검토 가능한 Ground | 추상적인 아이디어를 Goal, Rule 및 Example Memory와 함께 다듬어 검토 가능한 Ground로 발전시킵니다. | Ground workspace Context만 생성하거나 변경하며 외부 Context 변경에는 별도 operation이 필요합니다. | 추상적인 Goal이 실제로 어떻게 작동해야 하는지 Rule과 구체적인 Example을 함께 고쳐가며 정리할 때. |
| 검사·비교·검토 | fit | 있음 · 캐시 또는 Provider | 명제 + 선택적 배경 → YES / MAY / NO; Ground + 연결된 Context → 완전한 Fit receipt | 정해진 Memory 또는 다른 명제 집합 전체가 통상적인 해석에서 서로 양립 가능한지 판단하고 YES, MAY 또는 NO를 반환합니다. | Context·Ground·Rule·Goal·Memory를 변경하지 않습니다. YES는 중요한 통상적 해석에서 양립, MAY는 통상적 해석에 따른 분기, NO는 그러한 해석에서 비양립을 뜻하며 진실성이나 근거 충분성을 입증하지 않습니다. | 정해진 Memory·Rule·Goal·Example 또는 다른 명제들이 함께 성립할 수 있는지 확인할 때. |
| 검사·비교·검토 | check-conformance | 있음 · 캐시 또는 Provider | Rule이나 조건 명제 + Ground Example 또는 Context → Conformance 보고서 | 하나의 Context 또는 저장된 Ground Example을 명시적인 Rule이나 조건 명제와 대조하고 준수 문제를 보고합니다. | 읽기 전용입니다. Fit은 명제들이 공존하는지를 묻고 Conformance는 선택한 subject가 명시된 Rule이나 조건 명제를 충족하는지 묻습니다. | 기존 Memory나 Example이 명시된 Rule이나 조건 명제를 충족하는지 확인할 때. |
| 시스템 및 Study 도구 | init-study | 없음 | Study baseline → 격리된 Study Profile | Study baseline을 격리된 participant/authority Profile 쌍으로 복사합니다. | 격리된 Profile store를 생성하고 활성 Profile을 전환합니다. | 재현 가능하고 격리된 사용자 연구 환경을 준비할 때. |
| 시스템 및 Study 도구 | eval | 형식에 따라 다름 | 고정 evaluation fixture → 보존된 campaign 결과 | 기존 semantic evaluation campaign을 실행하고 검사합니다. | Context가 아니라 evaluation ledger를 변경합니다. | 일반 evaluation interface를 다시 설계하는 동안 기존 연구용 evaluation harness를 사용할 때. |
| Profile | profile | 없음 | Profile registry ↔ Profile 관리 | 전체 로컬 MemoryStore Profile을 선택하고 관리합니다. Picker 또는 `mem profile rename`과 `mem profile remove`로 이름을 바꾸거나 영구 제거할 수도 있습니다. | Profile을 전환, import, rename 또는 영구 remove할 수 있으며 Grant subcommand는 Profile 간 view를 관리합니다. | 사용자, 환경 또는 Memory store를 분리해 관리할 때. |
| Profile | rename | 없음 | 관리되는 Profile 이름 → 새 Profile 이름 | Store를 이동하거나 다시 쓰지 않고 현재 또는 명시한 Profile의 이름을 변경합니다. | Registry metadata만 변경하며 store 내용은 유지합니다. | 기존 Profile에 더 명확한 이름을 부여할 때. |
| 공유 및 보호 | share | 없음 | 소유 Context 범위 → 수신 endpoint | Grant 기반 receiver endpoint를 통해 정확한 Context 하나 또는 lexical Context subtree를 전송합니다. | `-d`는 정확한 Source를, `-r`은 Source와 모든 lexical descendant를 검토된 묶음 하나로 전송하며 Source는 유지됩니다. | 소유한 Context 하나 또는 관련 Context 묶음을 승인된 수신자에게 전달할 때. |
| 공유 및 보호 | lock | 없음 | Resource → 쓰기 보호된 resource | 현재 Context, recursive Context 집합, Memory 또는 Profile을 잠급니다. | 선택한 정확한 resource 또는 recursive 범위의 보호 metadata를 변경합니다. | 안정된 자료가 실수로 변경되는 것을 막을 때. |
| 공유 및 보호 | unlock | 없음 | 보호된 resource → 쓰기 가능한 resource | Context, recursive 집합, Memory 또는 Profile의 잠금을 해제합니다. | 선택한 범위에서 보호 metadata를 제거합니다. | 보호된 자료를 의도적으로 다시 수정할 때. |
| 시스템 및 Study 도구 | help | 없음 | Operation catalog → 사용 안내 | 대화형 command browser에 들어가 syntax help를 엽니다. | 읽기 전용이며 선택한 operation을 실행하지 않습니다. | 사용할 수 있는 operation과 호출 형식을 찾을 때. |
| 시스템 및 Study 도구 | provider | 없음 | Provider 설정 ↔ 상태 또는 probe | Codex, Ollama 또는 OpenRouter semantic execution을 선택하고 검증합니다. | Provider 설정을 변경하거나 probe 요청을 보낼 수 있습니다. | Semantic operation이 사용할 backend를 선택하거나 지속적인 작업 전에 준비 상태를 확인할 때. |
| 시스템 및 Study 도구 | shell-init | 없음 | Shell 이름 → integration script | 대화형 command prefill을 위한 선택적 shell integration을 출력합니다. | 출력은 읽기 전용이며 설치에는 명시적인 shell 실행이 필요합니다. | 선택적인 shell 편의 기능을 활성화할 때. |
| 시스템 및 Study 도구 | config | 없음 | Configuration key ↔ 값 | 저장된 전역 configuration 값을 읽거나 씁니다. | 전역 configuration을 변경할 수 있습니다. | 기존의 low-level legacy interface를 통해 저장된 전역 설정을 확인하거나 변경할 때. |

## Merge implementation target

Status: implemented in the working tree; automated verification complete,
ordered real-terminal evidence pending.

Merge keeps one conditional review boundary across its Python, CLI, and TUI
adapters:

1. Freeze and classify the complete direct or recursive plan before mutation.
2. Classify Source-only identities as `NEW`, equivalent shared items as
   `UNCHANGED`, and actionable collisions as `CONTENT_DIVERGENCE`,
   `TYPE_COLLISION`, `REFERENCE_COLLISION`, or `PLACEMENT_COLLISION` under one
   deterministic `CONFLICT` obligation.
3. When there are no `CONFLICT` items, skip the Resolution workbench. A
   bare TTY invocation continues directly to the existing exact frozen-plan
   review; a complete non-interactive invocation applies through its ordinary
   CLI path.
4. Show `ITEMS` and `RESPONSES` only when at least one `CONFLICT` exists. Every
   conflict requires an explicit, valid deterministic Source/Target decision
   before Apply becomes available.
5. A non-interactive invocation with a complete typed decision set also skips
   the TUI. An absent or incomplete decision set fails before persistence and
   reports the unresolved Memory UIDs.
6. Recursive Merge aggregates divergence across every frozen Context mapping.
   One unresolved item prevents every addition and resolution from being
   published; Apply remains atomic.
7. Revalidate the frozen Source/Target identities, digests, subtree membership,
   and complete decision set before writing.

This first target is deterministic and provider-free. It does not infer a
common ancestor or label every two-way content difference as a three-way
conflict. A later ancestry-aware contract may automate Source-only or
Target-only edits only when a common Base is explicitly provable.

### Merge TUI parity checklist

The conflict-aware Merge flow should preserve the interaction contracts already
used by the shared Resolution Session and the migrated Merge setup.

Required shared behavior:

- Keep the existing `A · SOURCE` selector and make `B · TARGET` selectable from
  the separately frozen CREATE-authorized catalog, initially checked at the
  command-start current Context.
  Both endpoint controls remain editable, and direct versus recursive reach
  remains one coupled setup choice.
- Build the complete deterministic plan before rendering decisions. `NEW` and
  `UNCHANGED` counts belong in the report; only actionable deterministic
  `CONFLICT` items become inline decision rows.
- When no required divergence exists, do not construct empty `ITEMS` or
  `RESPONSES` frames. Continue to the existing exact frozen-plan review.
- When divergence exists, render one inline `MERGE REVIEW` list in frozen
  conflict order. Every row shows the short item UID and complete Source and
  Target values; no Viewer, hidden item-opening step, or separate Responses
  frame is required.
- Stage `KEEP TARGET` for every row at entry. The check mark is the real staged
  choice, not only keyboard focus, so `APPLY · READY` remains visible and valid
  from the first frame. `Left`/`Right` changes the focused row immediately;
  `Up`/`Down` traverses within and across the separate Conflicts and Controls
  surfaces, while one `Tab` moves directly from any conflict row to Apply.
- Keep report labels and chrome neutral. Individual Memory contents use the
  shared light-lavender Memory style; the checked or active control uses the
  shared blue treatment. Sanitize terminal controls and retain the complete
  content in a cursor-backed wrapped pane; `PageUp`/`PageDown` must reach the
  final Target byte when one comparison is taller than the viewport.
- Do not fabricate `Other`, clear a staged row, or accept custom replacement
  text. A protected Target still shows complete Source evidence with an
  unavailable marker while removing `TAKE SOURCE` from the selectable and
  bulk vocabularies.
- Enter on Apply opens one separate exact whole-set review. Its argv represents
  the frozen per-item decisions or selected bulk strategy; a second Enter is
  the mutation approval. Escape or Backspace returns from review to the same
  staged list, and cancel at either layer publishes no partial addition or
  decision.
- After Apply, keep a visible durable receipt with Source, Target, reach,
  `NEW`, `ALREADY PRESENT`, `KEPT TARGET`, `TOOK SOURCE`, whether Target
  changed, and checkpoint count.
  A stale Source, Target, subtree, or decision binding fails without partial
  publication and requires a freshly frozen plan.
- A bare TTY invocation may enter this conditional workbench. An explicit CLI
  invocation stays non-interactive: a complete typed decision set applies,
  while an absent or incomplete set reports stable unresolved locators and
  exits before persistence.
- Keep Merge provider-free. No loading indicator, provider status, semantic
  cache label, free-form incorporation turn, or hidden semantic retry belongs
  in this deterministic flow.

Merge-specific decisions and boundaries:

- **No-op persistence.** A Merge with no effective Target content change still
  freezes and revalidates the complete boundary. Its receipt explains the
  zero delta through typed counts such as `KEPT TARGET 1` and
  `TARGET CHANGED NO`, and its checkpoint retains the reviewed decisions. It
  must distinguish the verified no-op from an operation that never ran and
  must not conceal or partially consume an earlier undoable mutation.
- **Operation-level recovery.** Direct and recursive Merge, including Contexts
  created by recursive reach and edits selected through divergence resolution,
  require one complete command unit. Undo atomically restores every updated
  Context and removes every Context created by that Merge; Redo recreates and
  reapplies the same complete unit. Partial recursive Undo is not acceptable.
- **Decision identity.** A bare Memory UID is insufficient when recursive
  mappings or repeated placements can expose the same UID more than once. Each
  decision needs a stable mapping-qualified identity, while the screen may show
  a short UID for readability.
- **Authority.** Existing Merge requires Target `CREATE` because it only adds.
  `TAKE SOURCE` edits an existing Target Memory and therefore also needs the
  operation's reviewed `UPDATE`/accept-derived authority and write-protection
  checks before the decision UI promises that action.
- **Structural and reference conflicts.** Same-UID unlike durable item types,
  duplicate logical references under different stored identities, and
  incompatible Context-like placements are required deterministic conflict
  classes rather than silent skips. Each exposes only resolutions that can be
  validated and applied without breaking pointer, authority, or placement
  invariants.
- **Decision retention (intentional limitation).** Staged review choices remain
  process-local. An applied checkpoint durably records the exact conflict IDs
  and decisions for explanation and recovery, but it is not a resumable draft.
  Any future resumable choice set must bind the exact Source/Target digests and
  become unusable when either side changes.
- **Bulk choices (implemented).** Explicit `KEEP ALL TARGET` and `TAKE ALL SOURCE`
  strategies share one `BULK DECISION` row in a fixed Controls frame below the
  independently scrollable conflict list; Apply remains a distinct control.
  `Left`/`Right` chooses a strategy and Enter visibly stages it across every
  row before moving to Apply. Its checked side is also derived automatically
  when every individual row agrees, and both sides remain unchecked for a
  mixed set. The same separate exact whole-set review used by individual
  choices remains the final approval boundary; no shortcut key mutates an
  unreviewed set.
- **No custom content (implemented).** Merge offers only typed deterministic
  Source/Target choices. It never synthesizes or accepts a combined
  replacement; semantic or custom reconciliation remains Meld's
  responsibility. The current Merge shell does not expose a free-form comment;
  if one is added later, it may retain rationale only and must never become
  replacement content.
- **Shared clipboard (implemented).** The inline shared Resolution workbench has the
  `y` focused conflict row / `Y` complete conflict-set plain-text clipboard
  contract used by other read-only surfaces. It returns a visible copy or
  failure receipt, and is not implemented as a Merge-only variant.
- **Verification evidence (implemented).** Ordered 180×52 color PTY evidence
  under `agent-records/docs/screenshots/mem-merge-compact-conflict-resolution-20260820/`
  covers default Target staging, individual and multiple-conflict arrow
  choices, bulk staging, exact approval, durable receipts, cancellation,
  stale-plan failure without partial Target publication, protected evidence,
  complete 60-line-per-side scrolling, and an explanatory zero-delta
  checkpoint/receipt. The 2026-08-15 set retains the former topology for
  historical comparison.
