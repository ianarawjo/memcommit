# Python API adapter

This package is MemCommit's public programmatic adapter for Python callers.
It owns `MemCommitClient`, public request and result values, public errors,
and the operation wrappers that translate between that contract and
application use cases.

Application rules remain under `memcommit.application`; this package may
assemble those rules for Python callers but must not become their canonical
owner.
