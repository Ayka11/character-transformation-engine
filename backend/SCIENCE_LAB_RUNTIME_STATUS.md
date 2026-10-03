# Science Lab V2.3 Runtime Status

Status: **IMPLEMENTED / CI-TESTED / NOT EMPIRICALLY VALIDATED**

The Science Lab composes the Research Execution V1.2 runtime and the V2.2 execution coordinator.

## Runtime

- Experiment Matrix registration.
- Scenario definitions with explicit conditions.
- Scenario execution through one execution_id.
- Durable scenario-run records and provenance.
- Descriptive primary-outcome statistics.
- Explicit replication assessment through the V1.5 replication engine.
- Explicit generalization assessment through the V1.5 transport engine.
- Claim validation against registered Evidence Graph lineage.
- Provenance-rich report bundle.
- Browser UI served at `/science-lab/ui`.

## Safety / scientific boundary

A blocked Level A safety execution remains blocked; Science Lab does not override the Safety Gate.

Science Lab descriptive statistics are not inferential evidence. Replication/generalization statuses remain tied to registered V1.5 criteria. Model-derived outputs retain EXP/DRV provenance and are not automatically promoted to EVD.

## CI

GitHub Actions run **#397** passed the current main backend suite and live PostgreSQL integration. The suite reports **251 passed / 12 skipped**, and the current workflow also rehearses PostgreSQL migration up/down on an isolated database.

## Next open layers

- production deployment approval and environment-specific PostgreSQL operations;
- authentication/authorization;
- observability and operational audit retention;
- richer inferential statistics where contractually registered;
- empirical scientific validation;
- richer frontend interaction beyond the current static browser console.