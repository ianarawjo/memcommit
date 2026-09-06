# Native JSON import and Study source data

Agent-authored implementation rationale, 2026-09-06. This records an agent
implementation and verification; it does not certify human review of the data.

## Motivation

A large campus Markdown file contained 300 independent Memories across six
Context categories. Its line count reflected the authoring container rather
than the runtime data structure. The user requested native MemCommit document
input in `mem import`, with Study initialization consuming that same facility.

Native Context JSON is now the source of Memory content in both packaged
scenarios, including Practice. Files follow the actual Context hierarchy.
A Context document contains its UID, name, ordered Memory records and ordinary
references. A standalone Memory document contains `type`, `uid`, and `content`.
There is no Study-specific JSON wrapper around those ordinary records.

## Command and application contract

```text
mem import context --from FILE.json [--as NEW_NAME]
mem import context SOURCE_NAME --from DIRECTORY [-r] [--as NEW_ROOT]
mem import context --from DIRECTORY -r
mem import memory --from FILE.json [--into EXISTING_CONTEXT]
```

The existing Profile/store and registered-Profile forms remain available.
An optional Memory selector must match the sole document UID. A Context file
uses its stored canonical name by default. Directory input discovers only
`context.json` files; a named selection is exact unless `-r` is present.
Importing every document in a directory requires explicit `-r` and cannot use
`--as`, since that set may have several unrelated roots. File source names are
serialized names, not relative Context operands. Memory destinations use the
existing Context operand resolver and one captured current-Context identity.

The `resource_import.documents` package owns the file decoder, application
entry points and shared publication boundary. CLI file import and Study
composition both use `import_context_records`. `context_data.py` owns the
Context remapping/reference-closure rules shared with registered-Profile input.
File intake does not shell out to the CLI or register a source Profile.

A file is read once into a value and byte digest. Publication uses that frozen
value; it does not reopen external references. The local import checkpoint
records source kind, digest and resource identity, without a filesystem path.
The source, active Profile, and current Context are unchanged by file import.
Study owns its explicit destination store and selected starting Context.

## Invariants and boundaries

- Preserve UID, text (including whitespace), and item order. Do not infer new
  facts or allocate replacement Memory identities during import.
- Reject duplicate JSON keys, malformed order, mismatched UID keys, unknown
  fields and unsupported item kinds instead of dropping content during decode.
- Ordinary Context and live Memory references must resolve within the selected
  import set with matching identities. Root renaming updates internal names.
  Memory snapshot references retain their self-contained content/provenance.
- Live Grant and query-only bindings are not file-importable authority. Native
  input currently excludes Context snapshot records as well. These limits are
  explicit errors, not silent conversion to ordinary Memories.
- Context destinations must all be new. The shared command lock covers the
  destination UID scan and require-new creation. Ordinary persistence owns
  graph/name locks, write protection and exception rollback. Memory insertion
  retains target identity and ordinary Context CAS.
- Study assembles translations, participant/authority ownership, Grants and
  run-local identities after native input validation. JSON content alone does
  not create a Grant. New Study runs inherit no operational history.

This change extends explicit CLI input. The existing interactive import setup
continues to select registered Profiles; a filesystem picker is not added.
Ordinary JSON imports do not infer sibling translation catalogs or read Study
sidecars. A Korean native file can be imported as literal Korean content; only
Study composition pairs languages into the existing same-UID translation view.

## Scenario migration and provenance

Legacy's 1,309 Memories remain paired English/Korean records. Its 129 Contexts
per language are stored under `legacy/data/native/task-N/PROFILE/LANGUAGE/`.
The three legacy Practice Contexts have their own native directory. Coffee's
20 Contexts per language are stored under `coffee/data/task-N/ROLE/LANGUAGE/`.
Coffee composition metadata retains Context ordering, purposes and Grant specs.

Existing Legacy Markdown paths remain short contract/index documents linking
to the JSON source. Existing purpose and operation sidecars remain separate
from Memory text. Native metadata TSV files retain fixture IDs, authoring
locators, audiences, verification flags and campus impact annotations. Stable
UIDs still correspond to the prior runtime identities, including the personal
Memory year/month normalization. The authoring sheet reads the JSON-backed
projection; historical Markdown parsing remains only for an explicitly supplied
external authoring root without a native corpus.

The pre-migration working-checkout hashes are recorded in
[`baseline-equivalence.json`](../outputs/native-json-import-20260906/baseline-equivalence.json).
Regression tests compare every bilingual body and authoring identity, all 129
Legacy Context records, the Practice records, and Coffee's full Context and
translation-catalog values. That evidence is agent-produced, not an assertion
that individual fixture translations were approved.

The Coffee fingerprint remains unchanged. Legacy manifest source links now
identify the actual native files and include a complete Context-record digest
covering UID, order and reference topology, so its package-derived fingerprint changes
from `781fd7bc77f3b9d5f1b931177ecddacce6aeefe61382f89699c65e495f49b77e`
to `7c6a595a5bd5dadb5729dd6c0751afaf7b2924b5b9a839375e10af8d94a91ba7`.
This is a representation/provenance change, not a change to installed Context
or Memory content. Existing runs and their recorded digests are not rewritten.

## Alternatives and limitations

Keeping Markdown as the canonical source would retain a separate Study parser
on the runtime path. Storing a mutable live Profile would also introduce
history, registry and cache state into research input. Native Context files
reuse the existing data model and remain independently importable.

One file per Memory is supported for external intake but is not required for
Study source storage: Context files already match the actual persisted unit.
The change does not implement arbitrary document extraction, file export,
merge/overwrite semantics, or a crash-recovery journal. Multi-Context writes
retain the prototype's existing exception-atomic rollback boundary.

## Verification

Focused tests cover native file/CLI imports, reference remapping, duplicate and
malformed data, identity collisions, exact text, canonical target confirmation,
rollback after a later write fails, and both Study initialization paths.
The migration parity tests compare to the captured pre-change values rather
than merely reserializing the new input. Wheel verification checks that native
JSON and sidecars are included in the installed distribution.
