"""Audited public operation meanings used by every Help projection."""

from __future__ import annotations

from memcommit.help_catalog.best_for import BEST_FOR_BY_OPERATION
from memcommit.help_catalog.details import DETAILS_BY_OPERATION
from memcommit.help_catalog.model import ExecutionKind, OperationHelp


def _operation(
    name: str,
    summary: str,
    flow: str,
    execution: ExecutionKind,
    effect: str,
    range: str | None = None,
    *,
    maturity: str | None = None,
) -> OperationHelp:
    try:
        best_for = BEST_FOR_BY_OPERATION[name]
    except KeyError as error:  # pragma: no cover - import-time catalog invariant
        raise RuntimeError(
            f"Operation Help BEST FOR is missing for {name!r}."
        ) from error
    return OperationHelp(
        name=name,
        summary=summary,
        flow=flow,
        execution=execution,
        effect=effect,
        best_for=best_for,
        range=range,
        maturity=maturity,
        details=DETAILS_BY_OPERATION.get(name, ()),
    )


_OPERATIONS = (
    _operation(
        "add",
        "Add one or more Memories to the current or explicit Context.",
        "Text or file -> Context Memories",
        ExecutionKind.DETERMINISTIC,
        "Changes the selected Context",
        "One exact target Context",
    ),
    _operation(
        "atomize",
        "Immediately atomize the current Context into independently reviewable "
        "Memories and save the full analysis for Review.",
        "Current Context Memories -> one atomized checkpoint + saved Review",
        ExecutionKind.SEMANTIC,
        "Changes the current Context in one checkpoint; Undo can restore it",
        "The complete current direct-Context frame",
    ),
    _operation(
        "audit",
        "Run Duplicate, Ambiguity, and Conflict checks plus optional Rule "
        "Conformance, save the result, and print its Review receipt.",
        "Context + Rules? -> saved Audit report",
        ExecutionKind.SEMANTIC,
        "No Context content changes",
        "One exact direct Context",
    ),
    _operation(
        "branch",
        "Copy a Context or subtree into a new branch and switch to it.",
        "Context -> new Context branch",
        ExecutionKind.DETERMINISTIC,
        "Creates a Context and switches to it",
        "Source exact or lexical descendants",
    ),
    _operation(
        "checkout",
        "Switch Contexts using Git-style syntax; with -b, create and switch to a new Context branch.",
        "Context locator -> current Context or new branch",
        ExecutionKind.DETERMINISTIC,
        "Switches Context; -b also creates one",
        "Branch Source exact or lexical descendants",
    ),
    _operation(
        "checkpoint",
        "Save the current Context as a manual recovery point for Diff or Revert.",
        "Context state -> checkpoint",
        ExecutionKind.DETERMINISTIC,
        "Adds recoverable history; content is unchanged",
    ),
    _operation(
        "check-conformance",
        "Check one Context or saved Ground Examples against explicit Rules or "
        "condition propositions and report conformance issues.",
        "Rules or condition propositions + Ground Examples or Context -> Conformance report",
        ExecutionKind.SEMANTIC,
        "Creates a conformance report without editing the selected data",
        "One saved Ground, or one exact local Target and Rules Context",
    ),
    _operation(
        "chunk",
        "Mechanically split all splittable direct Memories in one Context, or one selected Memory, at configured sentence, clause, structural, literal, or size boundaries.",
        "Context direct Memories or one direct Memory -> ordered Memory chunks",
        ExecutionKind.DETERMINISTIC,
        "Immediately changes one Source Context; Undo can restore the checkpointed split",
        "One exact Context; optional direct Memory selector",
    ),
    _operation(
        "clear",
        "Immediately remove all direct items from the current or explicit Context; Undo can restore them.",
        "Context direct items -> empty Context",
        ExecutionKind.DETERMINISTIC,
        "Checkpointed Context change with command-unit Undo/Redo",
        "One exact Context",
    ),
    _operation(
        "compare",
        "Compare Memories in two Contexts and report what they share, what "
        "differs, and what appears only on one side.",
        "Context <-> Context -> comparison report",
        ExecutionKind.SEMANTIC,
        (
            "Default summary is transient and read-only; --ledger saves the "
            "exhaustive relation basis used by Meld"
        ),
        "Each side exact or readable descendants",
    ),
    _operation(
        "config",
        "Read or write stored global configuration values.",
        "Configuration key <-> value",
        ExecutionKind.DETERMINISTIC,
        "May change global configuration",
    ),
    _operation(
        "contexts",
        "List local Contexts and readable cross-Profile Context views.",
        "Profile access -> readable Context catalog",
        ExecutionKind.DETERMINISTIC,
        "Read-only; current Context is unchanged",
        "All readable Context names",
    ),
    _operation(
        "delete",
        "Select a Context or direct item to delete, or name it by locator, name, or UID.",
        "Context or direct item -> removed",
        ExecutionKind.DETERMINISTIC,
        "Destructive change after confirmation",
        "One exact Context or direct item",
    ),
    _operation(
        "diff",
        "Show the differences recorded by a Context checkpoint or the active Update.",
        "Context checkpoint or active Update -> diff report",
        ExecutionKind.DETERMINISTIC,
        "Read-only",
        "One exact Context or active Update",
    ),
    _operation(
        "distill",
        "Derive higher-level Rules or condition propositions from Case or Example "
        "propositions in a bounded Context, optionally guided by a Goal.",
        "Case/Example Context + Goal? -> decisions -> added Rules -> receipt",
        ExecutionKind.SEMANTIC,
        "Standalone adds to one existing Target; Impact previews without changing endpoints",
        "One exact local Source, its readable descendants, or one bound Ground candidate frame",
    ),
    _operation(
        "elaborate",
        "Expand an abstract Goal, Rule, or condition into multiple more specific "
        "candidate propositions.",
        "Goal -> added Rules; Rules -> added Case propositions -> receipt",
        ExecutionKind.SEMANTIC,
        "Standalone atomically adds unverified results to one existing Target; Impact previews the result",
        "One Goal or Rule set, inline or from one exact Ground revision",
    ),
    _operation(
        "edit",
        "Directly replace the content of one or more Memories selected by UID or prefix.",
        "Memory or Memory batch -> replacement content",
        ExecutionKind.DETERMINISTIC,
        "Changes only the selected directly owned Memories",
        "One or more direct Memories in one exact Context",
    ),
    _operation(
        "replace",
        "Preview and replace every literal or explicit regular-expression match in ordinary local Memories.",
        "Text pattern + replacement + local Context scope -> reviewed exact changes -> atomic Apply",
        ExecutionKind.DETERMINISTIC,
        "Read-only preview; Apply changes matched local Memories in one Undo/Redo command unit",
        "One or more local roots; lexical descendants and embedded owners are independent",
    ),
    _operation(
        "embed",
        "Place a live link to one Memory or Context inside a local Target while retaining Source ownership.",
        "Source Memory or Child Context -> Target placement",
        ExecutionKind.DETERMINISTIC,
        "Changes Target structure; Source identity and ownership are retained",
        "One direct local Memory or one readable Child Context, and one exact local Target",
    ),
    _operation(
        "eval",
        "Run and inspect the existing semantic evaluation campaigns.",
        "Fixed evaluation fixtures -> retained campaign results",
        ExecutionKind.MIXED,
        "Changes evaluation ledgers, not Context content",
    ),
    _operation(
        "find",
        "Find exact text or explicit regular-expression (regex) matches in readable Memories.",
        "Text pattern + Context scope -> exact Memory spans",
        ExecutionKind.DETERMINISTIC,
        "Returns exact matching spans without editing the selected Contexts",
        "One or more readable Context roots; descendants and embedded Contexts are optional",
    ),
    _operation(
        "search",
        "Semantically rank Memories relevant to a natural-language request across selected Contexts.",
        "Context set + query -> ranked Memories",
        ExecutionKind.SEMANTIC,
        (
            "Returns ranked results; optional reviewed Save As creates a "
            "new local Context"
        ),
        (
            "One or more readable roots; lexical descendants and embedded "
            "Context reach are independently selectable"
        ),
    ),
    _operation(
        "fit",
        "Judge whether a defined set of Memories or other propositions is jointly "
        "compatible under ordinary interpretation, returning YES, MAY, or NO.",
        "Auto-typed text, Memory UID, or readable Context operands + optional background -> YES / MAY / NO; Ground + bound Contexts -> complete Fit receipt",
        ExecutionKind.SEMANTIC,
        "Returns a YES, MAY, or NO judgment without editing its inputs",
        "One complete bounded proposition frame from auto-typed or explicit literals, direct Memory selectors, or readable direct Contexts; Ground checks Context, vertical, peer, and Rule–Example relations",
    ),
    _operation(
        "resolve",
        "Automatically interpret incompatibility Issues in one complete direct-Memory "
        "Context frame and verify one small Fit-YES plan.",
        "Complete Context frame + optional guidance -> one grounded automatic Apply or one temporary assumed interpretation",
        ExecutionKind.SEMANTIC,
        "An assumed plan is temporary; a grounded plan applies as one checkpoint",
        "One complete bounded direct Context frame; explicit Memory UID prefixes limit edits, not semantic reading",
    ),
    _operation(
        "dedup",
        "Remove byte-identical duplicates (dup) immediately, retaining the "
        "first existing UID for each exact-content group.",
        "Direct Context Memories -> exact-content groups -> atomic removal",
        ExecutionKind.DETERMINISTIC,
        "Deletes later exact copies in one checkpoint; no provider or TUI",
        "One exact direct Context; inbound references block removal",
    ),
    _operation(
        "dedun",
        "Immediately resolve exact plus semantic redundancies (dun), retaining "
        "the first existing Memory in each complete DUN group.",
        "Direct Context Memories -> exact and semantic groups -> deterministic survivor -> atomic Apply -> receipt",
        ExecutionKind.SEMANTIC,
        "The invocation expresses Apply intent and publishes at most one checkpoint",
        "One exact direct Context; inbound references block version 1 Apply",
    ),
    _operation(
        "find-ambiguities",
        "Report ambiguous direct Memories in the current or explicit Context.",
        "Context Memories -> ambiguity report",
        ExecutionKind.SEMANTIC,
        "Creates an ambiguity report without editing the Source",
        "One exact direct Context",
    ),
    _operation(
        "find-conflicts",
        "Report conflicting direct Memory pairs in the current or explicit Context.",
        "Context Memories -> conflict report",
        ExecutionKind.SEMANTIC,
        "Creates a conflict report without editing the Source",
        "One exact direct Context",
    ),
    _operation(
        "find-duplicates",
        "Report byte-identical duplicate direct Memories.",
        "Direct Context Memories -> exact DUP groups",
        ExecutionKind.DETERMINISTIC,
        "Creates an exact-duplicate report without editing the Source",
        "One exact direct Context",
    ),
    _operation(
        "find-redundancies",
        "Report exact and semantically redundant direct Memories.",
        "Direct Context Memories -> DUP + semantic DUN evidence report",
        ExecutionKind.SEMANTIC,
        "Creates a redundancy report; --select can review multiple readable targets",
        "One exact direct Context by default; explicit --select enables readable multi-target scope",
    ),
    _operation(
        "forget",
        "Apply one complete keep/edit/delete decision batch for an instruction.",
        "Context + instruction -> decisions -> atomic curation -> receipt",
        ExecutionKind.SEMANTIC,
        "An explicit invocation expresses Apply intent; Source changes only after complete decisions",
        "One exact direct Source frame",
    ),
    _operation(
        "ground",
        "Develop an abstract idea into a reviewable Ground by shaping its Goal, "
        "Rules, and example Memories together.",
        "Dialogue + evidence -> reviewed Ground",
        ExecutionKind.SEMANTIC,
        "Creates or changes only Ground workspace Contexts; external Context "
        "changes require separate operations",
        "One named Ground workspace and its owned lanes",
        maturity="PARTIAL",
    ),
    _operation(
        "help",
        "Enter the interactive command browser and open syntax help.",
        "Operation catalog + optional natural-language request -> usage guidance",
        ExecutionKind.MIXED,
        "Browses command guidance",
    ),
    _operation(
        "impact",
        "Preview or inspect an operation's expected Context effects without "
        "applying them.",
        "Operation inputs or session -> impact report",
        ExecutionKind.MIXED,
        "Shows expected effects; execution remains a separate operation invocation",
        "Operation-owned Source and Target ranges",
    ),
    _operation(
        "import",
        "Import a clean-baseline Profile, Context tree, or Memory by value while preserving resource identity.",
        "External resource -> local owned copy",
        ExecutionKind.DETERMINISTIC,
        "Creates or changes local owned resources",
        "Profile, exact Context, subtree, or one Memory",
        maturity="PARTIAL",
    ),
    _operation(
        "init",
        "Create a new empty Context and make it the current working Context.",
        "New Context name -> Context",
        ExecutionKind.DETERMINISTIC,
        "Creates a Context and switches to it",
        "One fresh exact portable non-UID-shaped name; optional lexical parents",
    ),
    _operation(
        "init-study",
        "Copy one Study baseline into an isolated participant/authority Profile pair.",
        "Study baseline -> isolated Study Profiles",
        ExecutionKind.DETERMINISTIC,
        "Creates isolated Profile stores and switches Profile",
    ),
    _operation(
        "list",
        (
            "List a Context's direct items—Memories, Memory references, query "
            "views, and embedded Contexts—and its readable child Contexts. "
            "Use -r to recursively include items from descendant and embedded "
            "Contexts; ls is the compact alias."
        ),
        "Context -> direct-item and child-Context listing",
        ExecutionKind.DETERMINISTIC,
        "Read-only",
        (
            "One exact Context; -r follows readable lexical descendants and "
            "embedded Contexts"
        ),
    ),
    _operation(
        "lock",
        "Lock the current Context, a recursive Context set, Memory, or Profile.",
        "Resource -> write-protected resource",
        ExecutionKind.DETERMINISTIC,
        "Changes protection metadata",
        "Exact resource or recursive Context set",
    ),
    _operation(
        "log",
        "Print or search recorded Context, Memory, and Profile history.",
        "Recorded history or query -> history report",
        ExecutionKind.MIXED,
        "Read-only",
        "One Context, one Memory lineage, or Profile attempts",
    ),
    _operation(
        "meld",
        "Semantically incorporate an incoming Context into an authoritative "
        "baseline, or derive a separate Result from two equal peers.",
        "INCOMING -> BASELINE; PEER A + PEER B -> RESULT",
        ExecutionKind.SEMANTIC,
        "Symmetric mode requires a distinct empty Result; directional mode "
        "changes only the existing Target after required execution decisions",
        "Each side exact or readable descendants",
    ),
    _operation(
        "merge",
        "Add Source-only items to a selected Target, leave exact matches "
        "unchanged, and choose Source or Target for stored-item conflicts.",
        "Source Context -> selected Target Context",
        ExecutionKind.DETERMINISTIC,
        "Changes Target only after every required conflict has KEEP TARGET or TAKE SOURCE; Source stays unchanged",
        "Exact roots or matching descendants by the same relative path",
    ),
    _operation(
        "profile",
        "Create, select, and manage local MemoryStore Profiles. Profiles "
        "can be renamed or permanently removed, and Study headings can be renamed "
        "through the picker or explicit profile subcommands.",
        "Profile registry <-> Profile administration",
        ExecutionKind.DETERMINISTIC,
        "May create, switch, import, rename, or permanently remove Profiles, rename "
        "Study headings, or manage cross-Profile views through Grant subcommands",
    ),
    _operation(
        "provider",
        "Select and verify Codex, Ollama, or OpenRouter semantic execution.",
        "Provider configuration <-> status or probe",
        ExecutionKind.DETERMINISTIC,
        "May change provider configuration or make a probe request",
    ),
    _operation(
        "pwd",
        "Print the current canonical Context name without loading its contents.",
        "Current Context pointer -> canonical name",
        ExecutionKind.DETERMINISTIC,
        "Prints the name without loading Context content",
    ),
    _operation(
        "query",
        (
            "Generate an LLM-based answer from readable Context knowledge or an "
            "authorized concealed query-only view."
        ),
        "Readable source + question -> answer with references",
        ExecutionKind.SEMANTIC,
        "Returns an answer; the visible transcript may be retained",
        (
            "Readable exact, descendant, or embedded Context scope; or one "
            "QUERY-authorized query-only view"
        ),
    ),
    _operation(
        "rationale",
        "Explain where one Memory came from and how it changed over time.",
        "Retained Trace + calibrated examples -> natural provenance receipt",
        ExecutionKind.SEMANTIC,
        "Read-only",
        "One current or historical Memory",
    ),
    _operation(
        "redo",
        "Redo the most recently undone recorded Context command.",
        "Undo history -> restored command effects",
        ExecutionKind.DETERMINISTIC,
        "Changes the affected Context set",
    ),
    _operation(
        "reference",
        "Copy one Source Memory version or direct/recursive Context scope into a Target as an immutable read-only snapshot.",
        "Source Memory or Context scope -> Target snapshot",
        ExecutionKind.DETERMINISTIC,
        "Adds a self-contained snapshot to the Target; the Source stays unchanged",
        "One direct local Source Memory or local Context scope and one exact local Target",
    ),
    _operation(
        "rename",
        "Rename the current or an explicit managed Profile without moving or rewriting its store; mem profile rename is the explicit equivalent.",
        "Managed Profile name -> new Profile name",
        ExecutionKind.DETERMINISTIC,
        "Changes registry metadata; store contents stay in place",
    ),
    _operation(
        "revert",
        "Restore the current or an explicit local Context to a selected "
        "checkpoint after reviewing that revision's complete result.",
        "Checkpoint -> restored Context state",
        ExecutionKind.MIXED,
        "Restores one Context; interactive or semantic selection requires "
        "reviewed confirmation",
        "One exact local Context",
    ),
    _operation(
        "review",
        "Inspect terminal execution evidence or a saved report and, "
        "where supported, record report responses. Review never applies Memories.",
        "Applied receipt or saved report artifact -> evidence/report",
        ExecutionKind.MIXED,
        "No Context content changes",
        "One saved operation artifact",
    ),
    _operation(
        "sever",
        "Save a Result by selecting, transforming, or excluding Source Memories "
        "according to a Criteria Context.",
        "Source Context + Criteria Context -> self-save Source or other-save Result",
        ExecutionKind.SEMANTIC,
        "Updates Source by default, or creates an explicit new Result; records a receipt",
        "Source exact for self-save or exact/descendants for other-save; Criteria scoped frame",
    ),
    _operation(
        "share",
        "Send one ordinary Context through a grant-backed receiver endpoint.",
        "Owned Context -> receiver endpoint",
        ExecutionKind.DETERMINISTIC,
        "External delivery; Source remains unchanged",
        "One exact ordinary Source Context",
    ),
    _operation(
        "shell-init",
        "Print opt-in shell integration for interactive command prefill.",
        "Shell name -> integration script",
        ExecutionKind.DETERMINISTIC,
        "Read-only; installation requires explicit shell evaluation",
    ),
    _operation(
        "show",
        "Show a Memory, reference, embedded Context, or the direct contents of a current/explicit Context.",
        "Context or direct item -> rendered content",
        ExecutionKind.DETERMINISTIC,
        "Returns retained lineage",
        "One exact Context or direct item",
    ),
    _operation(
        "status",
        (
            "Show the current Context's inventory, first five direct Memories, "
            "relationships, and latest checkpoints."
        ),
        "Current Context state + history -> status report",
        ExecutionKind.DETERMINISTIC,
        "Read-only",
        (
            "Current Context by default; -r includes readable descendants and "
            "embedded Contexts"
        ),
    ),
    _operation(
        "summarize",
        (
            "Show an LLM-derived overview of ordinary Memories in a readable "
            "Context scope."
        ),
        "Context -> summary",
        ExecutionKind.SEMANTIC,
        "Read-only",
        (
            "One readable Context; optionally includes readable lexical "
            "descendants and embedded Contexts; ordinary Memories only"
        ),
    ),
    _operation(
        "switch",
        "Enter the interactive Context picker, or switch to an explicit Context.",
        "Context locator -> current Context pointer",
        ExecutionKind.DETERMINISTIC,
        "Changes only the current Context pointer",
        "One exact existing Context",
    ),
    _operation(
        "trace",
        "Trace one retained Memory through its recorded lineage.",
        "Memory -> retained lineage",
        ExecutionKind.DETERMINISTIC,
        "Read-only",
        "One current or historical Memory",
    ),
    _operation(
        "translate",
        "Generate and save a reusable translated view of one Context or Memory "
        "while preserving the original content.",
        "Context or Memory -> translated view or materialization",
        ExecutionKind.SEMANTIC,
        "Explicit materialization routes create or add translated material",
        "One exact Context or one direct Memory",
    ),
    _operation(
        "undo",
        "Undo the most recent recorded command as one unit.",
        "Command history -> reversed Context effects",
        ExecutionKind.DETERMINISTIC,
        "Restores every Context and Memory change recorded by that command",
        "One most-recent recoverable command unit across all affected Contexts",
    ),
    _operation(
        "unlock",
        "Unlock the current Context, a recursive set, Memory, or Profile.",
        "Protected resource -> writable resource",
        ExecutionKind.DETERMINISTIC,
        "Changes protection metadata",
        "Exact resource or recursive Context set",
    ),
    _operation(
        "update",
        "Update a Target Context from a Source Context, resolving required execution "
        "decisions before atomic Apply.",
        "Source Context -> decisions -> Target Apply -> receipt",
        ExecutionKind.SEMANTIC,
        "Changes only the local Target after Apply",
        "Each endpoint exact or readable descendants",
    ),
)


OPERATION_HELP_BY_NAME = {operation.name: operation for operation in _OPERATIONS}

if len(OPERATION_HELP_BY_NAME) != len(_OPERATIONS):  # pragma: no cover
    raise RuntimeError("Operation Help names must be unique.")

if set(BEST_FOR_BY_OPERATION) != set(OPERATION_HELP_BY_NAME):  # pragma: no cover
    missing = sorted(set(OPERATION_HELP_BY_NAME) - set(BEST_FOR_BY_OPERATION))
    stale = sorted(set(BEST_FOR_BY_OPERATION) - set(OPERATION_HELP_BY_NAME))
    raise RuntimeError(
        "Operation Help BEST FOR coverage mismatch: "
        f"missing={missing!r}, stale={stale!r}."
    )

stale_details = sorted(set(DETAILS_BY_OPERATION) - set(OPERATION_HELP_BY_NAME))
if stale_details:  # pragma: no cover
    raise RuntimeError(
        f"Operation Help details reference unknown operations: {stale_details!r}."
    )


def operation_help(name: str) -> OperationHelp:
    """Return one audited operation contract or fail on an unknown name."""

    try:
        return OPERATION_HELP_BY_NAME[name]
    except KeyError as error:
        raise KeyError(f"No Operation Help is registered for {name!r}.") from error


def operation_summary(name: str) -> str:
    """Return the canonical one-line description used by interface adapters."""

    return operation_help(name).summary
