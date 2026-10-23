"""Reference retained an immutable Memory or Context snapshot as a direct item.

Its execution was removed when Context items were restricted to owned Memories.
This package preserves the operation's design identity, not an executable stub.
Previous implementation: commit 8d6b88953, application/operations/reference/.
Reintroduction requires a new representation compatible with Memory-only Contexts.
"""
