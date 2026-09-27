# Scientific Reporting Runtime Status

V1.6 executable baseline is implemented as a provenance-linked report snapshot service.

Implemented contract elements:
- versioned 14-section report specifications;
- source-artifact manifest hashing;
- immutable report sections and claim bindings;
- claim-language guardrails derived from registered claim state;
- explicit support, limitation and contradiction references;
- report decisions with immutable hashes;
- report QC for section coverage, source manifest, provenance, replication/generalization visibility and limitations;
- publication only after QC passes;
- published REPORT nodes linked to their source artifacts through DOCUMENTS edges;
- supersession lifecycle preserving prior report history.

A report is treated as a rendering of registered artifacts, not as a new source of evidence. Runtime acceptance is not empirical validation.
