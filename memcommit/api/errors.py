"""Stable exception hierarchy for the public MemCommit Python API."""


class MemCommitError(RuntimeError):
    """Base class for failures exposed by the public Python API."""


class AddError(MemCommitError):
    """Base class for public Add failures."""


class AddInputError(AddError):
    """The caller supplied an invalid ordered Memory batch."""


class AddContextError(AddError):
    """The requested Add target Context is unavailable."""


class AddAuthorityError(AddError):
    """The active Profile or Grant does not authorize Add."""


class AddConflictError(AddError):
    """The Add target changed before its single checkpoint could commit."""


class AddStorageError(AddError):
    """Add could not safely read or publish local durable state."""


class AddExecutionError(AddError):
    """An authorized Add failed without publishing a complete receipt."""


class QueryError(MemCommitError):
    """Base class for public Query failures."""


class QueryInputError(QueryError):
    """The caller supplied an invalid Query request."""


class QueryConfigurationError(QueryError):
    """The client or provider configuration is invalid."""


class QueryContextError(QueryError):
    """A requested Context or query reference is unavailable."""


class QueryAuthorityError(QueryError):
    """The requested operation is not authorized by the active Profile."""


class QueryProviderFailure(QueryError):
    """The configured semantic provider could not complete the request."""


class QueryExecutionError(QueryError):
    """Authorized Query execution failed before a durable publication."""


class QueryPublicationError(QueryError):
    """A granted Query answered, but its requested session was not published."""


class QueryStorageError(QueryError):
    """Query could not safely read or publish local durable state."""


class MeldError(MemCommitError):
    """Base class for public Meld failures."""


class MeldInputError(MeldError):
    """The caller supplied an invalid Meld request."""


class MeldContextError(MeldError):
    """A requested Meld source or target is unavailable."""


class MeldAuthorityError(MeldError):
    """The active Profile or Grant does not authorize this Meld."""


class MeldProviderFailure(MeldError):
    """The semantic provider could not complete a required Meld turn."""


class MeldConflictError(MeldError):
    """A bound Meld Context or saved session changed concurrently."""


class MeldStorageError(MeldError):
    """Meld could not safely read or publish local durable state."""


class MeldExecutionError(MeldError):
    """An authorized Meld failed before a complete result was published."""


class AtomizeGroundingError(MemCommitError):
    """Base class for public conversational Atomize Grounding failures."""


class AtomizeGroundingInputError(AtomizeGroundingError):
    """The caller supplied an invalid Grounding selector or dialogue turn."""


class AtomizeGroundingContextError(AtomizeGroundingError):
    """The requested Context or its saved Atomize analysis is unavailable."""


class AtomizeGroundingProviderFailure(AtomizeGroundingError):
    """The semantic provider could not complete a Grounding turn."""


class AtomizeGroundingConflictError(AtomizeGroundingError):
    """A bound Context, analysis, workbench, or dialogue changed concurrently."""


class AtomizeGroundingStorageError(AtomizeGroundingError):
    """Grounding could not safely read or publish local durable state."""


class AtomizeGroundingExecutionError(AtomizeGroundingError):
    """Grounding failed before publishing one complete requested outcome."""


class AtomizeError(MemCommitError):
    """Base class for public structural Atomize failures."""


class AtomizeInputError(AtomizeError):
    """The caller supplied an invalid structural Atomize request."""


class AtomizeContextError(AtomizeError):
    """The requested local Atomize Context is unavailable."""


class AtomizeProviderFailure(AtomizeError):
    """The semantic provider could not complete structural analysis."""


class AtomizeConflictError(AtomizeError):
    """The Source or accepted analysis/workbench revision changed."""


class AtomizeStorageError(AtomizeError):
    """Atomize could not safely read or publish local durable state."""


class AtomizeExecutionError(AtomizeError):
    """Structural Atomize failed before one complete outcome was published."""


class SemanticError(MemCommitError):
    """Base class for public Distill and Elaborate failures."""


class SemanticInputError(SemanticError):
    """The caller supplied an invalid semantic-operation request."""


class SemanticContextError(SemanticError):
    """A selected Context or Ground is unavailable or stale."""


class SemanticAuthorityError(SemanticError):
    """The selected frame is not authorized for semantic derivation."""


class SemanticProviderFailure(SemanticError):
    """The configured semantic provider could not complete the request."""


class SemanticConflictError(SemanticError):
    """A frozen proposal or its Source changed before publication."""


class SemanticStorageError(SemanticError):
    """The operation could not safely access local durable state."""


class SemanticExecutionError(SemanticError):
    """An authorized semantic operation failed before complete publication."""


__all__ = [
    "AddAuthorityError",
    "AddConflictError",
    "AddContextError",
    "AddError",
    "AddExecutionError",
    "AddInputError",
    "AddStorageError",
    "AtomizeGroundingConflictError",
    "AtomizeGroundingContextError",
    "AtomizeGroundingError",
    "AtomizeGroundingExecutionError",
    "AtomizeGroundingInputError",
    "AtomizeGroundingProviderFailure",
    "AtomizeGroundingStorageError",
    "AtomizeConflictError",
    "AtomizeContextError",
    "AtomizeError",
    "AtomizeExecutionError",
    "AtomizeInputError",
    "AtomizeProviderFailure",
    "AtomizeStorageError",
    "MemCommitError",
    "MeldAuthorityError",
    "MeldConflictError",
    "MeldContextError",
    "MeldError",
    "MeldExecutionError",
    "MeldInputError",
    "MeldProviderFailure",
    "MeldStorageError",
    "QueryAuthorityError",
    "QueryConfigurationError",
    "QueryContextError",
    "QueryError",
    "QueryExecutionError",
    "QueryInputError",
    "QueryProviderFailure",
    "QueryPublicationError",
    "QueryStorageError",
    "SemanticAuthorityError",
    "SemanticConflictError",
    "SemanticContextError",
    "SemanticError",
    "SemanticExecutionError",
    "SemanticInputError",
    "SemanticProviderFailure",
    "SemanticStorageError",
]
