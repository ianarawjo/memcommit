"""Lock is deferred until protection can cover mem and workspace files.

Execution is deferred while mem is paired with directly editable workspace files.
A native-only protection registry cannot govern those files or their editor writes.
This package preserves the future operation identity, not an executable stub.
Previous implementation: commit 99643be13, application/operations/lock/.
Reintroduction requires a defined ownership/delivery system and protection boundary
covering both native state and its workspace counterpart.
"""
