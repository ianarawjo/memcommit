# practice-source ADMIN issues

## PS2-A-RENAME-BRANCH-HISTORY — CRITICAL

Renaming a Context that retains a Branch creation checkpoint changes the live
owner name but leaves the Branch receipt's target name unchanged. The global
command-history builder then rejects the checkpoint as outside its creation
membership, so an exact Undo/Redo top cannot be verified.

The audit stopped after counted sequence 37. Sequence 38 (`undo --keep`) was
not invoked. The exact mismatch, the consistent six-member sequence-37 Branch
receipt, pre/post digests, and frozen traceback source point are preserved in
`admin-blocker-evidence.json`.

The reviewed inverse Rename M2 restored the original owner membership and the
exact B2 stack top, after which Undo2/Redo2 succeeded.

## PS2-A-BRANCH-HISTORY-CASCADE — CRITICAL

Branching from the recovered B1 copied B1's owned Branch checkpoint into B3
without rebinding its receipt to B3. Checkout M3 copied that invalid history
again into co3. Both new commands also wrote valid own-creation checkpoints,
but the global stack builder stops on B3's inherited foreign-owner checkpoint
before the Checkout3 top can be verified. The original R subtree had zero
Branch checkpoints, so this is specifically a Branch-bearing Source cascade.

The audit paused again after counted sequence 44. It then retained the malformed
history as a reviewed negative control: Undo3/Redo3, Redo4, Undo4, and
Undo5/Redo5 all failed before Context or current-pointer mutation. The
owner/receipt pairs, clean-source scan, exact digests, and failure source point
are preserved in `admin-blocker-2-evidence.json`.

## PS2-A-INIT-STUDY-UUID-CREATES — CRITICAL

A UUID-shaped Study name was accepted, created a managed Study plus its
granted-memory Profile/Store, and activated the new Profile. The immediate
post-call assertion caught the identity escape. After exact byte/hash
snapshots, an approved atomic host recovery changed only `active_uid`; both
unexpected Profiles and Stores remain preserved.

## PS2-A-INIT-SPARSE-PARENT — MEDIUM

Init without `--parents` successfully created `.../missing-parent/leaf` while
the lexical parent `.../missing-parent` remained physically absent. Consumers
that require a materialized hierarchy must use `--parents` and verify it.
