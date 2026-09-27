# Evidence & Claim Runtime Status

The executable V1.4 evidence/claim layer now includes:

- immutable graph nodes and edges;
- result lineage enforcement;
- claim state-machine enforcement;
- claim transition history via DERIVED_FROM;
- graph-backed replication and generalization prerequisites;
- claim-bound evidence criteria;
- EVIDENCE_SUPPORTED gating on registered criteria and EVD provenance;
- explicit contradiction sets and CONTRADICTS edges;
- graph-backed INDETERMINATE transitions for insufficient or conflicting information;
- registered inference blocks that can prevent prohibited claim transitions;
- claim subgraph, lineage, support, and audit endpoints.

No transition is treated as empirical validation merely because the runtime accepts it. The V1.4/V1.5 specifications remain the normative design contracts, and persistent SQL storage is not yet claimed as connected to this in-memory runtime registry.
