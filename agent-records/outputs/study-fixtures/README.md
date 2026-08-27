# Historical generated Legacy Study packages

This directory preserves generated output from the former Study fixture
workflow. Each `task-N/` contains participant and authority stores plus the
Grant manifest that was used to validate the original split ownership model.

The runtime source of truth now lives under
`src/memcommit/study_scenarios/legacy/`. `mem init-study NAME --scenario
legacy` rebuilds and validates private intermediate packages from that source,
then publishes the same isolated participant/authority topology directly.
These recorded outputs are not imported, refreshed, or edited as a baseline.
