# Mem Help Content Review

Status: working draft, 2026-08-15

This document freezes the current review copy before it is promoted into the
runtime Help catalog. It contains the same 61 operations in two separate
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
| Browse & Navigate | contexts | NO | Profile access → readable Context catalog | Browse local Contexts and readable cross-Profile Context views without switching. | Read-only; includes all readable names and does not switch Context. | Exploring every Context currently available to the Profile. |
| Browse & Navigate | list | NO | Context → direct-item and child-Context listing | List a Context's direct items—Memories, Memory references, query views, and embedded Contexts—and its readable child Contexts. Use `-r` to recursively include items from descendant and embedded Contexts; `ls` is the compact alias. | Read-only; one exact Context, while `-r` follows readable lexical descendants and embedded Contexts. | Inspecting the structure and direct contents of a Context. |
| Browse & Navigate | show | NO | Context or direct item → rendered content | Show a Memory, reference, embedded Context, or the direct contents of a current/explicit Context. | Read-only; accepts one exact Context or one direct item. | Reading the complete content of a known item or Context. |
| Browse & Navigate | switch | NO | Context locator → current Context pointer | Enter the interactive Context picker, or switch to an explicit Context. | Changes only the current pointer; the destination must already exist. | Moving the working position to another existing Context. |
| Browse & Navigate | checkout | NO | Context locator → current Context or new branch | Switch Contexts using Git-style syntax; with -b, create and switch to a new Context branch. | Switches Context; -b additionally creates a branch. | Using a Git-like workflow to switch or create a branch. |
| Create, Copy & Connect | init | NO | New Context name → Context | Create a new empty Context and make it the current working Context. | By default creates only the exact requested Context; `-p` creates missing parent Contexts and reuses existing parents without embedding children. | Starting a separate workspace for a new topic, task, or group of Memories. |
| Create, Copy & Connect | branch | NO | Context → new Context branch | Copy a Context or subtree into a new branch and switch to it. | Creates a copied Context or subtree and changes the current pointer. | Editing a Context or subtree independently while preserving the original. |
| Create, Copy & Connect | import | NO | External resource → local owned copy | Import a clean-baseline Profile, Context tree, or Memory by value while preserving resource identity. | **PARTIAL.** Currently limited to MemCommit-to-MemCommit transfer: Profiles from an external `.mem` store or package, and Profiles, Context trees, or Memories from another registered Profile. Arbitrary documents, Skills, and Export are not yet implemented. | Bringing externally supplied material into a locally managed store. |
| Create, Copy & Connect | embed | NO | Source Memory or Child Context → Target placement | Place a live link to one Memory or Context inside a local Target while retaining Source ownership. | Changes Target structure; Source identity and ownership remain intact. | Reusing a Memory or Context in another Context while following later Source changes. |
| Create, Copy & Connect | add | NO | Text or file → Context Memories | Add one or more Memories to the current or explicit Context. | Changes one exact target Context. | Adding one or more facts, instructions, or notes directly to a Context. |
| Create, Copy & Connect | reference | NO | Source Memory version → Target snapshot | Copy one direct Source Memory version into a Target as an immutable read-only snapshot. | Adds a self-contained snapshot to the Target; the Source stays unchanged. | Retaining one exact Memory version even if its Source later changes or disappears. |
| Deterministic Content Changes | edit | NO | Memory or Memory batch → replacement content | Directly replace the content of one or more Memories selected by UID or prefix. | Changes only the selected directly owned Memories in one exact Context. | Directly correcting or replacing the content of specific existing Memories. |
| Deterministic Content Changes | chunk | NO | Memory → ordered Memory chunks | Mechanically split one direct Memory at header, paragraph, or approximate sentence boundaries. | Changes the Source Context only after confirmation. | A Memory already has clear text boundaries that should become separate Memories. |
| Deterministic Content Changes | delete | NO | Context or direct item → removed | Select a Context or direct item to delete, or name it by locator, name, or UID. | Destructive; removes one exact Context or direct item after confirmation. | Removing a specific Context or item that is no longer needed. |
| Deterministic Content Changes | clear | NO | Context direct items → empty Context | Remove all direct items from the current or explicit Context after confirmation. | Destructive; affects all direct items in one exact Context. | Emptying a Context while retaining the Context itself. |
| Deterministic Content Changes | merge | NO | A · Source Context → B · current Target Context | Add Source-only items to the current Target, choosing Source or Target wherever stored items conflict. | This is not a three-way or semantic merge. Every collision requires an explicit deterministic Source/Target decision; Merge never synthesizes custom content or removes Target-only items. | Bringing work from a copied or branched Context back into the current Context. |
| Deterministic Content Changes | dedup | NO | Confirmed duplicate handoffs → reviewed survivors → exact Apply | Keep one unchanged existing Memory per confirmed duplicate component. | Read-only until exact Apply; Apply deletes absorbed UIDs in one checkpoint within one exact direct Context. | Collapsing confirmed equivalent Memories while preserving one existing UID and its exact wording. |
| Search & Explain | find | NO | Text pattern + Context scope → exact Memory spans | Find exact text or explicit regular-expression (regex) matches in readable Memories. | Read-only; one or more readable Context roots, with optional descendants and embedded Contexts. | Locating exact words, identifiers, or text patterns within a selected Context scope. |
| Search & Explain | search | YES · CACHE OR PROVIDER | Context set + query → ranked Memories | Semantically rank Memories relevant to a natural-language request across selected Contexts. | Results are read-only; optional reviewed Save As creates a new local Context. Lexical-descendant and embedded-Context reach are independently selectable. | Finding relevant Memories through meaning and context, including related content expressed in different words. |
| Search & Explain | query | YES · CACHE OR PROVIDER | Readable source + question → answer with references | Generate an LLM-based answer from readable Context knowledge or an authorized concealed query-only view. | Does not change Context content; a visible transcript may be retained. Uses one readable exact, descendant, or embedded Context scope, or one QUERY-authorized query-only view. QUERY-only access may answer within its granted boundary while concealing complete Source Memories and the full underlying policy. | Getting a grounded natural-language answer instead of a list of matching Memories. |
| Search & Explain | summarize | YES · CACHE OR PROVIDER | Context → summary | Show an LLM-derived overview of ordinary Memories in a readable Context scope. | Read-only; one readable Context, optionally including readable lexical descendants and embedded Contexts; ordinary Memories only. | Obtaining a concise overview of a Context or subtree. |
| History & Recovery | trace | NO | Memory → retained lineage | Trace one retained Memory through its recorded lineage. | Read-only; requires one current or historical Memory. | Determining where a Memory came from and how it changed. |
| History & Recovery | rationale | DEPENDS ON FORM | Memory provenance → rationale | Explain one Memory from recorded provenance and, when needed, inference. | Read-only; inference is used only when recorded provenance is insufficient. | Understanding why a Memory exists or reached its current form. |
| Check, Compare & Review | find-duplicates | YES · CACHE OR PROVIDER | Context Memories → duplicate report | Report duplicate direct Memories in the current or explicit Context; no Context changes. | Analyzes one exact direct Context and does not modify it. | Locating semantically redundant Memories before cleanup. |
| Check, Compare & Review | find-ambiguities | YES · CACHE OR PROVIDER | Context Memories → ambiguity report | Report ambiguous direct Memories in the current or explicit Context; no Context changes. | Analyzes one exact direct Context and does not modify it. | Finding Memories that permit unclear or multiple interpretations. |
| Check, Compare & Review | find-conflicts | YES · CACHE OR PROVIDER | Context Memories → conflict report | Report conflicting direct Memory pairs in the current or explicit Context; no Context changes. | Analyzes one exact direct Context and does not modify it. | Finding mutually incompatible claims or instructions. |
| Check, Compare & Review | audit | YES · CACHE OR PROVIDER | Context + Rules? → saved Audit report | Run Duplicate, Ambiguity, and Conflict checks plus optional Rule Conformance, then review one saved report. | Changes no Context content; analyzes one exact direct Context. | Performing a combined quality review before revising a Context. |
| Semantic Transformations | atomize | YES · CACHE OR PROVIDER | Context Memories → reviewed atomic Memories | Split composite Memories for review; --evaluate performs an issue-scoped directional meld. | Material changes occur only after explicit acceptance. | Separating a composite Memory into independently reviewable requirements. |
| Semantic Transformations | distill | YES · EXACT PREPARED OR PROVIDER | Case/Example Context + Goal? → reviewed Rules | Derive reusable Rules from Case or Example propositions in a selected Context scope, using an optional Goal to focus relevance. | Source and Ground stay unchanged; standalone Apply may create a new Result. | Extracting reusable rules from evidence-rich source material. |
| Semantic Transformations | elaborate | YES · EXACT PREPARED OR PROVIDER | Goal → suggested Rules; Rules → suggested Case propositions | Propose candidate Rules from a Goal, or concrete Case propositions from existing Rules. | Read-only; every proposal remains suggested and unverified. | An abstract Goal needs starter Rule candidates, or existing Rules need additional concrete Case propositions for review. |
| Check, Compare & Review | compare | YES · CACHE OR PROVIDER | Context ↔ Context → comparison report | Compare Memories in two Contexts and report what they share, what differs, and what appears only on one side. | Neither Context changes or serves as the authority; each may be exact or include readable descendants. | Comparing two Contexts as a whole to understand where they align and differ. |
| Check, Compare & Review | impact | DEPENDS ON FORM | Operation inputs or session → impact report | Preview or inspect operation Impact; no Context changes occur before its reviewed Apply handoff. | Impact is read-only; applying remains a separate reviewed action. | Checking expected consequences before accepting a transformation. |
| Check, Compare & Review | review | DEPENDS ON FORM | Saved analysis → review responses | Enter an interactive Review session or stage semantic review responses; never apply Memories. | Records review responses but never materializes Memory changes. | Resolving issues in a saved analysis before a later Apply. |
| Semantic Transformations | resolve | YES · CACHE OR PROVIDER | Context Memories + optional guidance → verified repair candidates → exact Apply | Propose grounded minimum changes that turn one direct-Memory frame from Fit MAY or NO to YES. | Read-only until one exact candidate is explicitly applied; Apply changes one exact direct Context. | Turning one non-fitting direct-Memory frame into a grounded, independently verified Fit-YES post-image before exact Apply. |
| Semantic Transformations | meld | YES · CACHE OR PROVIDER | PEER A + PEER B → RESULT; INCOMING → BASELINE | Semantically reconcile two Contexts into either a separate Result or an authoritative Baseline. | Symmetric mode requires a distinct empty Result; directional mode changes only the Baseline after reviewed Apply. | Combining separately developed Contexts into a shared Result, or incorporating proposed changes into an existing Baseline. |
| Semantic Transformations | update | YES · CACHE OR PROVIDER | Source Context → Target Context | Update Memories in the Target Context from Memories in the Source Context, asking the user to review and choose when needed. | Only the local Target changes after Apply. | Updating an existing Context using newly verified Memories. |
| Semantic Transformations | sever | YES · CACHE OR PROVIDER | Source Context + Criteria Context → new Result Context | Review Source against Criteria and create a derived Result while leaving Source unchanged. | Creates a new reviewed Result; Source remains unchanged. | Selecting or transforming part of a Source according to reusable criteria. |
| Semantic Transformations | translate | YES · CACHE OR PROVIDER | Context or Memory → translated view or materialization | Show and save a reusable translation view; materialize it only through an explicit route. | Source remains unchanged; materialization requires an explicit action. | Translating material while preserving the original source. |
| Semantic Transformations | forget | YES · CACHE OR PROVIDER | Context + instruction → reviewed curation batch | Review keep/edit/delete decisions for one instruction, then apply the accepted batch. | Evaluates one complete direct Source frame; Source changes only after acceptance. | Removing or rewriting Memories according to a natural-language instruction whose meaning must be interpreted. |
| History & Recovery | log | DEPENDS ON FORM | Recorded history or query → history report | Browse Context checkpoints, inspect one Memory lineage with --memory, search history, or list Profile command attempts. | Read-only; scope depends on the selected history form. | Investigating previous operations, checkpoints, or Memory history. |
| History & Recovery | diff | NO | Recorded change → diff report | Inspect recorded Context or Update changes without applying them. | Read-only; compares one exact Context history or active Update. | Verifying exactly what a recorded operation changed. |
| History & Recovery | checkpoint | NO | Context state → checkpoint | Save the current Context as a manual recovery point for Diff or Revert. | Adds history metadata without changing Context content. | Creating a recovery point before risky work. |
| History & Recovery | undo | NO | Command history → reversed Context effects | Undo the most recent recorded Context command across its affected Contexts. | Changes every Context affected by the selected command. | Reversing the latest recorded mutation as one operation. |
| History & Recovery | redo | NO | Undo history → restored command effects | Redo the most recently undone recorded Context command. | Restores the affected Context set from the most recent Undo. | Reapplying a command that was undone accidentally. |
| History & Recovery | revert | DEPENDS ON FORM | Checkpoint → restored Context state | Select a checkpoint and review restoration of one local Context. | Changes one exact local Context after restoration review. | Restoring a Context to a deliberately saved recovery point. |
| Ground Workbench | ground | YES · CACHE OR PROVIDER | Dialogue + evidence → reviewed Ground | Create or continue a reviewed Goal-Rules-Memories Ground workbench. | Changes Ground records; Context changes require separate commands. | Building a reviewed evaluation or behavior contract from evidence. |
| Check, Compare & Review | fit | YES · CACHE OR PROVIDER | Propositions + optional background → YES / MAY / NO; Ground + bound Contexts → complete Fit receipt | Judge proposition compatibility, or detect coherence issues across one saved Ground graph. | Changes no Context, Ground, Rule, Goal, or Memory; checks one complete frozen frame across Context, vertical, peer, and Rule–Example relations. | Checking whether Memories, Rules, Goals, or other propositions can coexist without contradiction. |
| Check, Compare & Review | check-conformance | YES · CACHE OR PROVIDER | Rules + Ground Memories or Context → Conformance report | Check Ground examples or one Context against explicit Rules. | Read-only; no Rule, Ground, Context, or Memory changes. | Checking a Context or saved Ground against explicit Rules. |
| System & Study Tools | init-study | NO | Study baseline → isolated Study Profiles | Copy one Study baseline into an isolated participant/authority Profile pair. | Creates isolated Profile stores and switches the active Profile. | Preparing a reproducible, isolated user-study environment. |
| System & Study Tools | eval | DEPENDS ON FORM | Evaluation fixtures → campaign results | Run and inspect staged semantic evaluation campaigns. | Changes evaluation ledgers, not Context content. | Measuring operation behavior against repeatable fixtures. |
| Profiles | profile | NO | Profile registry ↔ Profile administration | Enter the interactive Profile selector, or manage complete local MemoryStore Profiles. | May switch, create, import, rename, or remove entire Profiles. | Managing separate users, environments, or Memory stores. |
| Profiles | rename | NO | Managed Profile name → new Profile name | Rename the current or an explicit managed Profile without moving or rewriting its store; mem profile rename is the explicit equivalent. | Changes registry metadata only; store contents remain in place. | Giving an existing managed Profile a clearer name. |
| Sharing & Protection | share | NO | Owned Context → receiver endpoint | Send one ordinary Context through a grant-backed receiver endpoint. | External delivery of one exact ordinary Context; Source remains unchanged. | Delivering an owned Context to an authorized receiver. |
| Sharing & Protection | lock | NO | Resource → write-protected resource | Lock the current Context, a recursive Context set, Memory, or Profile. | Changes protection metadata for an exact resource or recursive Context set. | Preventing accidental modification of stable material. |
| Sharing & Protection | unlock | NO | Protected resource → writable resource | Unlock the current Context, a recursive set, Memory, or Profile. | Removes protection metadata from the selected resource scope. | Reopening protected material for intentional revision. |
| System & Study Tools | help | NO | Operation catalog → usage guidance | Enter the interactive command browser and open syntax help. | Read-only; does not execute the selected operation. | Discovering available operations and their invocation forms. |
| System & Study Tools | provider | NO | Provider configuration ↔ status or probe | Select and verify Codex, Ollama, or OpenRouter semantic execution. | May change configuration or send an explicit probe request. | Selecting and validating the semantic execution backend. |
| System & Study Tools | shell-init | NO | Shell name → integration script | Print opt-in shell integration for interactive command prefill. | Read-only output; installation requires explicit shell evaluation. | Enabling optional shell-specific conveniences. |
| System & Study Tools | config | NO | Configuration key ↔ value | Read and write global configuration. | May change global settings; does not directly modify Context content. | Inspecting or changing persistent MemCommit settings. |

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
| 생성·복사·연결 | reference | 없음 | Source Memory 버전 → Target snapshot | 직접 Source Memory의 현재 버전을 변경 불가능한 읽기 전용 snapshot으로 Target에 복사합니다. | Target에 self-contained snapshot을 추가하며 Source는 바뀌지 않습니다. | Source가 나중에 바뀌거나 사라져도 정확한 Memory 버전을 보존할 때. |
| 결정론적 내용 변경 | edit | 없음 | Memory 또는 Memory batch → 대체 내용 | UID 또는 prefix로 지정한 Memory 하나 이상의 내용을 직접 교체합니다. | 하나의 정확한 Context에서 선택된 직접 소유 Memory만 변경합니다. | 특정한 기존 Memory의 내용을 직접 바로잡거나 교체할 때. |
| 결정론적 내용 변경 | chunk | 없음 | Memory → 순서가 있는 Memory 조각 | 직접 Memory 하나를 제목, 문단 또는 근사적인 문장 경계에서 기계적으로 나눕니다. | 확인 후 Source Context를 변경합니다. | Memory에 이미 분명한 텍스트 경계가 있고, 그 단위들을 각각의 Memory로 만들고 싶을 때. |
| 결정론적 내용 변경 | delete | 없음 | Context 또는 직접 항목 → 제거 | Context나 직접 항목을 선택하거나 locator, 이름 또는 UID로 지정해 삭제합니다. | 파괴적 작업이며 확인 후 정확한 항목 하나를 제거합니다. | 더 이상 필요하지 않은 특정 Context나 항목을 제거할 때. |
| 결정론적 내용 변경 | clear | 없음 | Context 직접 항목 → 빈 Context | 확인 후 현재 또는 명시한 Context의 모든 직접 항목을 제거합니다. | Context 자체는 유지하지만 모든 직접 항목을 제거합니다. | Context는 남겨두고 그 안의 직접 내용만 비울 때. |
| 결정론적 내용 변경 | merge | 없음 | A · Source Context → B · 현재 Target Context | Source에만 있는 항목을 현재 Target에 추가하고, 저장된 항목이 충돌하면 Source 또는 Target을 선택합니다. | 3-way 또는 semantic merge가 아닙니다. 모든 충돌은 Source/Target 중 하나를 결정론적으로 선택해야 하며, custom 내용을 합성하거나 Target에만 있는 항목을 삭제하지 않습니다. | 복사하거나 분기한 Context에서 진행한 작업을 현재 Context로 다시 가져올 때. |
| 결정론적 내용 변경 | dedup | 없음 | 확인된 중복 handoff → 검토한 survivor → exact Apply | 확인된 각 중복 component에서 기존 Memory 하나를 변경하지 않고 유지합니다. | exact Apply 전에는 읽기 전용이며, Apply는 하나의 정확한 직접 Context에서 흡수되는 UID를 한 checkpoint로 삭제합니다. | 확인된 동등 Memory를 하나로 정리하면서 기존 UID 하나와 정확한 문구를 보존할 때. |
| 검색 및 설명 | find | 없음 | 텍스트 패턴 + Context 범위 → 정확한 Memory 일치 구간 | 읽을 수 있는 Memory에서 정확한 텍스트 또는 명시적인 정규식(regex) 일치를 찾습니다. | 읽기 전용이며 하나 이상의 읽을 수 있는 Context root를 대상으로 하고, descendant와 embedded Context 포함 여부를 선택할 수 있습니다. | 선택한 Context 범위에서 정확한 단어, identifier 또는 텍스트 패턴을 찾을 때. |
| 검색 및 설명 | search | 있음 · 캐시 또는 Provider | Context 집합 + query → 순위가 매겨진 Memory | 선택한 Context에서 자연어 요청과 의미상 관련된 Memory의 순위를 매깁니다. | 결과는 읽기 전용이며, 검토한 Save As를 선택하면 새 로컬 Context를 만듭니다. Lexical descendant와 embedded Context 범위는 독립적으로 선택합니다. | 의미와 맥락으로 관련 Memory를 찾을 때. 다른 표현으로 작성된 관련 내용도 포함합니다. |
| 검색 및 설명 | query | 있음 · 캐시 또는 Provider | 읽을 수 있는 Source + 질문 → reference가 포함된 답변 | 읽을 수 있는 Context 지식 또는 승인된 비공개 query-only view를 바탕으로 LLM 답변을 생성합니다. | Context 내용은 변경하지 않으며 보이는 대화 기록은 유지될 수 있습니다. 읽을 수 있는 정확한 Context·descendant·embedded 범위 또는 QUERY 권한이 있는 query-only view 하나를 사용합니다. QUERY-only 접근은 허용된 범위 안의 질문에는 답하면서 전체 Source Memory와 기반 정책 전체를 숨길 수 있습니다. | 일치하는 Memory 목록 대신 근거 있는 자연어 답변을 받을 때. |
| 검색 및 설명 | summarize | 있음 · 캐시 또는 Provider | Context → 요약 | 읽을 수 있는 Context 범위의 일반 Memory를 바탕으로 LLM 개요를 보여줍니다. | 읽기 전용이며 읽을 수 있는 Context 하나를 대상으로, lexical descendant와 embedded Context를 선택적으로 포함합니다. 일반 Memory만 사용합니다. | Context나 subtree의 간결한 개요를 얻을 때. |
| 기록 및 복구 | trace | 없음 | Memory → 보존된 lineage | 기록된 lineage를 따라 현재 또는 과거의 Memory 하나를 추적합니다. | 읽기 전용이며 Memory 하나만 다룹니다. | Memory의 출처와 변경 과정을 확인할 때. |
| 기록 및 복구 | rationale | 형식에 따라 다름 | Memory provenance → 근거 설명 | 기록된 provenance와 필요한 경우 추론을 사용해 Memory 하나를 설명합니다. | 읽기 전용이며 기록만으로 부족할 때만 추론합니다. | Memory가 존재하거나 현재 형태가 된 이유를 이해할 때. |
| 검사·비교·검토 | find-duplicates | 있음 · 캐시 또는 Provider | Context Memory → 중복 보고서 | 현재 또는 명시한 Context의 직접 Memory 중 중복을 보고합니다. | 정확한 직접 Context 하나를 분석하며 내용을 변경하지 않습니다. | 정리 전에 의미상 중복된 Memory를 찾을 때. |
| 검사·비교·검토 | find-ambiguities | 있음 · 캐시 또는 Provider | Context Memory → 모호성 보고서 | 현재 또는 명시한 Context에서 모호한 직접 Memory를 보고합니다. | 정확한 직접 Context 하나를 분석하며 내용을 변경하지 않습니다. | 여러 해석이 가능한 불명확한 Memory를 찾을 때. |
| 검사·비교·검토 | find-conflicts | 있음 · 캐시 또는 Provider | Context Memory → 충돌 보고서 | 현재 또는 명시한 Context에서 서로 충돌하는 직접 Memory 쌍을 보고합니다. | 정확한 직접 Context 하나를 분석하며 내용을 변경하지 않습니다. | 양립할 수 없는 주장이나 지침을 찾을 때. |
| 검사·비교·검토 | audit | 있음 · 캐시 또는 Provider | Context + 선택적 Rule → 저장된 Audit 보고서 | 중복, 모호성, 충돌 검사와 선택적 Rule Conformance를 실행한 뒤 하나의 저장된 보고서를 검토합니다. | Context 내용을 변경하지 않으며 정확한 direct Context 하나를 분석합니다. | Context를 수정하기 전에 종합적인 품질 검사를 수행할 때. |
| 의미 기반 변환 | atomize | 있음 · 캐시 또는 Provider | Context Memory → 검토 가능한 원자적 Memory | 복합 Memory를 검토 가능한 단위로 나눕니다. --evaluate는 issue 범위의 directional meld를 수행합니다. | 명시적으로 승인한 후에만 자료가 변경됩니다. | 복합 Memory의 요구사항을 독립적으로 검토할 수 있게 나눌 때. |
| 의미 기반 변환 | distill | 있음 · 정확한 준비 결과 또는 Provider | Case/Example Context + 선택적 Goal → 검토 가능한 Rule | 선택한 Context 범위의 Case 또는 Example 명제에서 재사용 가능한 Rule을 도출하며, 선택적인 Goal로 관련성의 초점을 맞춥니다. | Source와 Ground는 유지되며 독립 실행의 Apply만 새 Result를 만들 수 있습니다. | 근거가 풍부한 자료에서 재사용 가능한 규칙을 추출할 때. |
| 의미 기반 변환 | elaborate | 있음 · 정확한 준비 결과 또는 Provider | Goal → 제안된 Rule; Rule → 제안된 Case 명제 | Goal에서 후보 Rule을, 기존 Rule에서 구체적인 Case 명제를 제안합니다. | 읽기 전용이며 모든 제안은 제안 상태이자 미검증 상태로 남습니다. | 추상적인 Goal에 출발점이 될 Rule 후보가 필요하거나, 기존 Rule을 검토할 구체적인 Case 명제가 더 필요할 때. |
| 검사·비교·검토 | compare | 있음 · 캐시 또는 Provider | Context ↔ Context → 비교 보고서 | 두 Context의 Memory를 비교해 공통점, 차이점, 한쪽에만 있는 내용을 보고합니다. | 두 Context 모두 변경하지 않으며 어느 쪽도 기준으로 삼지 않습니다. 각 범위는 정확한 Context 또는 읽을 수 있는 하위 Context를 포함할 수 있습니다. | 두 Context를 전체적으로 비교해 어디가 같고 다른지 이해할 때. |
| 검사·비교·검토 | impact | 형식에 따라 다름 | Operation 입력 또는 session → 영향 보고서 | Operation의 영향을 미리 보거나 검사하며 검토된 Apply로 넘기기 전에는 Context를 변경하지 않습니다. | Impact 자체는 읽기 전용이며 Apply는 별도의 검토 작업입니다. | 변환을 승인하기 전에 예상되는 영향을 확인할 때. |
| 검사·비교·검토 | review | 형식에 따라 다름 | 저장된 분석 → 검토 응답 | 대화형 Review session에 들어가거나 의미 검토 응답을 기록하며 Memory를 적용하지 않습니다. | 응답만 기록하며 Memory 변경을 materialize하지 않습니다. | 이후 Apply 전에 저장된 분석의 문제를 해결할 때. |
| 의미 기반 변환 | resolve | 있음 · 캐시 또는 Provider | Context Memory + 선택적 guidance → 검증된 repair 후보 → exact Apply | 하나의 직접 Memory frame이 Fit MAY 또는 NO에서 YES가 되도록 근거 있는 최소 변경을 제안합니다. | 하나의 정확한 후보를 명시적으로 Apply하기 전에는 읽기 전용이며, Apply는 하나의 정확한 직접 Context를 변경합니다. | Fit이 맞지 않는 하나의 직접 Memory frame을 근거가 있고 독립적으로 검증된 Fit YES 결과로 만든 뒤 exact Apply할 때. |
| 의미 기반 변환 | meld | 있음 · 캐시 또는 Provider | PEER A + PEER B → RESULT; INCOMING → BASELINE | 두 Context를 의미적으로 조정하여 별도의 Result 또는 권위 있는 Baseline으로 만듭니다. | 대칭 모드는 서로 구별되는 빈 Result가 필요하며, 방향 모드는 검토된 Apply 후 Baseline만 변경합니다. | 따로 발전한 Context들을 공통 Result로 통합하거나, 제안된 변경을 기존 Baseline에 반영할 때. |
| 의미 기반 변환 | update | 있음 · 캐시 또는 Provider | Source Context → Target Context | Source Context의 Memory를 바탕으로 Target Context의 Memory를 업데이트하고, 필요할 때 사용자에게 검토와 선택을 요청합니다. | Apply 후 로컬 Target만 변경됩니다. | 새롭게 검증된 Memory를 바탕으로 기존 Context를 업데이트할 때. |
| 의미 기반 변환 | sever | 있음 · 캐시 또는 Provider | Source Context + Criteria Context → 새 Result Context | Source를 Criteria에 따라 검토하고 Source를 유지한 채 파생 Result를 생성합니다. | 검토된 새 Result를 만들며 Source는 변경하지 않습니다. | 재사용 가능한 기준에 따라 Source 일부를 선별하거나 변환할 때. |
| 의미 기반 변환 | translate | 있음 · 캐시 또는 Provider | Context 또는 Memory → 번역 view 또는 materialization | 재사용 가능한 번역 view를 보여주고 저장하며 명시적인 경로로만 materialize합니다. | Source는 유지되며 materialization은 별도 명시 작업이 필요합니다. | 원본을 보존하면서 자료를 번역할 때. |
| 의미 기반 변환 | forget | 있음 · 캐시 또는 Provider | Context + 지시 → 검토 가능한 선별 batch | 하나의 지시에 대한 유지·편집·삭제 결정을 검토하고 승인한 batch를 적용합니다. | 완전한 직접 Source frame을 한 번에 평가하며 승인 후에만 Source가 변경됩니다. | 의미를 해석해야 하는 자연어 지침에 따라 Memory를 제거하거나 다시 작성할 때. |
| 기록 및 복구 | log | 형식에 따라 다름 | 기록된 history 또는 query → history 보고서 | Context checkpoint, Memory lineage, history 검색 또는 Profile command 시도를 조회합니다. | 읽기 전용이며 선택한 history 형식에 따라 범위가 달라집니다. | 이전 작업, checkpoint 또는 Memory 기록을 조사할 때. |
| 기록 및 복구 | diff | 없음 | 기록된 변경 → diff 보고서 | 기록된 Context 또는 Update 변경을 적용하지 않고 검사합니다. | 읽기 전용이며 정확한 Context history 또는 활성 Update를 비교합니다. | 기록된 작업이 정확히 무엇을 변경했는지 확인할 때. |
| 기록 및 복구 | checkpoint | 없음 | Context 상태 → checkpoint | 현재 Context를 Diff 또는 Revert에 사용할 수동 복구 지점으로 저장합니다. | Context 내용은 변경하지 않고 history metadata만 추가합니다. | 위험한 작업 전에 복구 지점을 만들 때. |
| 기록 및 복구 | undo | 없음 | Command history → 되돌린 Context 효과 | 가장 최근에 기록된 Context command가 영향을 준 모든 Context에서 효과를 되돌립니다. | 해당 command의 모든 영향 Context를 변경합니다. | 최근 mutation 전체를 하나의 작업으로 되돌릴 때. |
| 기록 및 복구 | redo | 없음 | Undo history → 복구된 command 효과 | 가장 최근에 Undo한 Context command를 다시 실행합니다. | 최근 Undo가 영향을 준 Context 집합을 복구합니다. | 실수로 되돌린 작업을 다시 적용할 때. |
| 기록 및 복구 | revert | 형식에 따라 다름 | Checkpoint → 복구된 Context 상태 | checkpoint를 선택하고 로컬 Context 하나의 복구 내용을 검토합니다. | 검토 후 정확한 로컬 Context 하나를 변경합니다. | Context를 의도적으로 저장한 복구 지점으로 되돌릴 때. |
| Ground Workbench | ground | 있음 · 캐시 또는 Provider | 대화 + 근거 → 검토 가능한 Ground | 검토 가능한 Goal–Rules–Memories Ground workbench를 생성하거나 이어갑니다. | Ground record를 변경하며 Context 변경에는 별도 command가 필요합니다. | 근거를 바탕으로 검토 가능한 평가 또는 행동 계약을 만들 때. |
| 검사·비교·검토 | fit | 있음 · 캐시 또는 Provider | 명제 + 선택적 배경 → YES / MAY / NO; Ground + 연결된 Context → 완전한 Fit receipt | 명제들의 양립 가능성을 판정하거나 저장된 Ground graph 하나에서 정합성 문제를 탐지합니다. | Context, Ground, Rule, Goal, Memory를 변경하지 않으며 하나의 완전하게 고정된 frame에서 Context·vertical·peer·Rule–Example 관계를 검사합니다. | Memory, Rule, Goal 또는 기타 명제들이 모순 없이 함께 성립할 수 있는지 확인할 때. |
| 검사·비교·검토 | check-conformance | 있음 · 캐시 또는 Provider | Rule + Ground Memory 또는 Context → Conformance 보고서 | Ground example 또는 Context 하나가 명시적인 Rule을 따르는지 검사합니다. | Rule, Ground, Context 및 Memory를 변경하지 않는 읽기 전용 작업입니다. | Context 또는 저장된 Ground를 명시적인 Rule에 맞춰 검사할 때. |
| 시스템 및 Study 도구 | init-study | 없음 | Study baseline → 격리된 Study Profile | Study baseline을 격리된 participant/authority Profile 쌍으로 복사합니다. | 격리된 Profile store를 생성하고 활성 Profile을 전환합니다. | 재현 가능하고 격리된 사용자 연구 환경을 준비할 때. |
| 시스템 및 Study 도구 | eval | 형식에 따라 다름 | 평가 fixture → campaign 결과 | 단계적인 semantic evaluation campaign을 실행하고 검사합니다. | Context가 아니라 evaluation ledger를 변경합니다. | 반복 가능한 fixture로 operation 행동을 측정할 때. |
| Profile | profile | 없음 | Profile registry ↔ Profile 관리 | 대화형 Profile selector에 들어가거나 전체 로컬 MemoryStore Profile을 관리합니다. | Profile을 전환, 생성, import, rename 또는 remove할 수 있습니다. | 사용자, 환경 또는 Memory store를 분리해 관리할 때. |
| Profile | rename | 없음 | 관리되는 Profile 이름 → 새 Profile 이름 | Store를 이동하거나 다시 쓰지 않고 현재 또는 명시한 Profile의 이름을 변경합니다. | Registry metadata만 변경하며 store 내용은 유지합니다. | 기존 Profile에 더 명확한 이름을 부여할 때. |
| 공유 및 보호 | share | 없음 | 소유 Context → 수신 endpoint | Grant 기반 receiver endpoint를 통해 일반 Context 하나를 전송합니다. | 정확한 일반 Context 하나를 외부로 전달하며 Source는 유지됩니다. | 소유한 Context를 승인된 수신자에게 전달할 때. |
| 공유 및 보호 | lock | 없음 | Resource → 쓰기 보호된 resource | 현재 Context, recursive Context 집합, Memory 또는 Profile을 잠급니다. | 선택한 정확한 resource 또는 recursive 범위의 보호 metadata를 변경합니다. | 안정된 자료가 실수로 변경되는 것을 막을 때. |
| 공유 및 보호 | unlock | 없음 | 보호된 resource → 쓰기 가능한 resource | Context, recursive 집합, Memory 또는 Profile의 잠금을 해제합니다. | 선택한 범위에서 보호 metadata를 제거합니다. | 보호된 자료를 의도적으로 다시 수정할 때. |
| 시스템 및 Study 도구 | help | 없음 | Operation catalog → 사용 안내 | 대화형 command browser에 들어가 syntax help를 엽니다. | 읽기 전용이며 선택한 operation을 실행하지 않습니다. | 사용할 수 있는 operation과 호출 형식을 찾을 때. |
| 시스템 및 Study 도구 | provider | 없음 | Provider 설정 ↔ 상태 또는 probe | Codex, Ollama 또는 OpenRouter semantic execution을 선택하고 검증합니다. | 설정을 변경하거나 명시적인 probe 요청을 보낼 수 있습니다. | Semantic execution backend를 선택하고 동작을 검증할 때. |
| 시스템 및 Study 도구 | shell-init | 없음 | Shell 이름 → integration script | 대화형 command prefill을 위한 선택적 shell integration을 출력합니다. | 출력은 읽기 전용이며 설치에는 명시적인 shell 실행이 필요합니다. | 선택적인 shell 편의 기능을 활성화할 때. |
| 시스템 및 Study 도구 | config | 없음 | Configuration key ↔ 값 | 전역 configuration을 읽고 씁니다. | 전역 설정을 변경할 수 있지만 Context 내용은 직접 변경하지 않습니다. | MemCommit의 영구 설정을 확인하거나 변경할 때. |

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

- Keep the existing `A · SOURCE` selector and frozen `B · CURRENT TARGET`.
  Source remains the only editable endpoint, and direct versus recursive reach
  remains one coupled setup choice.
- Build the complete deterministic plan before rendering decisions. `NEW` and
  `UNCHANGED` counts belong in the report; only actionable deterministic
  `CONFLICT` items belong in the Items list.
- When no required divergence exists, do not construct empty `ITEMS` or
  `RESPONSES` frames. Continue to the existing exact frozen-plan review.
- When divergence exists, start on the complete Viewer report. Before opening
  an item the visible Tab order is `VIEWER → ITEMS → TO DO → VIEWER`. After an
  item is opened it is `VIEWER → RESPONSES → ITEMS → TO DO → VIEWER`.
- Show `RESPONSES` only for the currently opened conflict. All conflicts are
  `REQUIRED`; To Do opens the first unanswered item and must not expose Apply
  while any required choice is open.
- Render `KEEP TARGET` and `TAKE SOURCE` through the common flat selection
  state: a check mark is the staged choice, blue is keyboard focus, and moving
  between frames restores the cursor to the staged choice. Selecting the
  staged choice again may clear it and must make the item unresolved again.
- Do not fabricate an `Other` choice. If the shared Response box remains
  visible, its text is an optional retained comment and never satisfies the
  required exact choice or invents replacement Memory content.
- Present classification before evidence. One detail shows the exact Context
  mapping, shared Memory UID, Target content, Source content, and a
  deterministic line/word diff. Reuse the presentation-neutral Memory diff
  records rather than reconstructing differences from rendered terminal text.
- Keep report labels and chrome neutral. Individual Memory contents use the
  shared light-lavender Memory style; only the active control uses the shared
  blue focus treatment. Sanitize terminal control text and retain full content
  in the scrollable detail even when list labels are shortened.
- Stage every choice without mutation. On the per-item path, after all required
  choices are staged, To Do opens a separate final review summarizing `NEW`,
  `UNCHANGED`, every conflict class, `KEEP TARGET`, `TAKE SOURCE`, Contexts to
  create, and checkpoints. A whole-set bulk card may fuse this review with its
  Apply action, but both paths confirm the exact frozen plan and complete
  decision set once.
- Escape and Backspace unwind one read-only layer at a time: final review to
  report, opened detail to report, then root close. Backspace remains ordinary
  deletion in a writable optional comment. Cancel at every layer publishes no
  partial additions or decisions.
- After Apply, keep a visible durable receipt with Source, Target, reach,
  per-disposition counts, changed Context count, and checkpoint identities.
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
  freezes and revalidates the complete boundary and records an explicit
  `NO TARGET CHANGE` session/receipt. It must distinguish the verified no-op
  from an operation that never ran. Its zero-delta command-unit behavior must
  not conceal or partially consume an earlier undoable mutation.
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
- **Decision retention (intentional limitation).** Current Merge review is process-local. Decide whether
  many staged divergence choices should survive closing and reopening. Any
  retained decision receipt must be bound to the exact Source/Target digests
  and become unusable when either side changes.
- **Bulk choices (implemented).** Explicit `KEEP ALL TARGET` and `TAKE ALL SOURCE`
  strategies over the complete unresolved set. A bulk action retains per-item
  accounting and shows the exact count, mappings, permissions, creations, and
  replacements it will commit. Confirming that complete bulk card is the final
  approval boundary, so it may Apply directly without a second duplicate Final
  Review screen. It must never mutate from an unreviewed shortcut key.
- **No custom content (implemented).** Merge offers only typed deterministic Source/Target
choices. It never synthesizes or accepts a combined replacement; semantic or
custom reconciliation remains Meld's responsibility. The current Merge shell
does not expose a free-form comment; if one is added later, it may retain
rationale only and must never become replacement content.
- **Shared clipboard (implemented).** The migrated shared Resolution workbench has the
  `y` focused / `Y` complete plain-text clipboard contract used by Summarize and
  Query. The binding is inactive in writable input, returns a visible copy or
  failure receipt, and is not implemented as a Merge-only variant.
- **Verification evidence (implemented).** Ordered 180×52 color PTY evidence under
  `docs/screenshots/mem-merge-conflict-resolution-20260815/` covers divergent
  direct and recursive paths, choice selection and clearing, individual and
  bulk final approval, durable receipts, operation-unit Undo/Redo,
  cancellation, stale-plan failure without partial Target publication, and an
  explicit no-op checkpoint/receipt with read-only verification.
