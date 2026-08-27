# Fit consumed-calibration artifact

`fit.json` preserves the 18 reviewed cases originally stored at
`memcommit/eval/fixtures/fit.json`. It balances six `YES`, six `MAY`, and six
`NO` ordinary-reading boundaries. Expected labels and reviewer rationales were
local scoring evidence and were never sent in the production Fit prompt.

The runner and corpus were introduced in commit `1f30686e4`. That commit
records one configured-provider observation of 18/18 matching labels. No raw
provider response, provider/model identity, timing record, or standalone run
ledger was retained, so the observation is not reproducible evidence of model
stability or general accuracy.

The last tree containing the executable runner and its dedicated tests is
commit `4fd2d0033`. They were retired from the distributed package on
2026-08-27; the corpus remains here as a research artifact and design-history
boundary. Current `mem fit` behavior and its production tests do not load this
artifact.
