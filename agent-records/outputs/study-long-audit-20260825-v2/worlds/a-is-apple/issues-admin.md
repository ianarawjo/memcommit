# a-is-apple ADMIN findings

## AIA-V2-A-RENAME-COMMAND-STACK-01 · HIGH

Renaming a Context created by Branch or `checkout -b` leaves its retained creation membership under the old target name. Global command-stack reconstruction then fails closed with `Branch checkpoint owner is outside its creation membership`, and every later Undo/Redo is unavailable. Avoid Rename while the producer remains in history; use explicit checkpoints/revert for recovery.

## Audit limitations

- Two interactive attempts (`help --emit-selection`, bare Branch) received pre-buffered keys before launcher startup and were terminated after their actual PTY state was captured.
- Exact-Memory Lock/Unlock M3 used the pre-Branch Source UID; Branch remapped the target UID, so both controls rejected the missing selector.
- Log M3 named the pre-Rename `co3` target after it had moved to `renamed-3`, so Context resolution failed safely.
