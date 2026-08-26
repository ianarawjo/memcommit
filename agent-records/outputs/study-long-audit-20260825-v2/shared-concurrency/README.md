# Shared-Profile concurrency supplemental lane

This focused lane is excluded from the official 1,980 attempts.

- Status: `complete`
- Recorded product calls: 115
- Setup: 24/24 succeeded
- Current: 5/30 actors observed their own Context; every round converged on one last-writer Context
- Switch: 19/30 failed closed on concurrent current change
- Explicit disjoint Branch: 5/6 failed on unrelated current change
- Update: winner `ticker`; 5/6 competing saves failed closed via active-record CAS
- Implicit Diff: 6/6 displayed the winner's endpoints and canary
- Registry identity: unchanged

The old silent Update overwrite is mitigated by CAS, but Profile-global current
and actor-unbound Diff remain shared-state boundaries. Explicit Branch is also
coupled to unrelated current state despite an explicit Source.

The first 102-call seed preflight never entered product commands because its
active Profile identity was wrong; it is preserved under `failed-seed-preflight/`.
