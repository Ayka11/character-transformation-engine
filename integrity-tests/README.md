# Production Integrity & Test Harness V1.9

Status: MDL/DRV test architecture. Tests validate implementation contracts; they do not validate scientific efficacy.

V1.9 verifies that V1.0–V1.8 preserve their declared invariants.

Test layers:
1. schema/contract validation
2. state-machine negative tests
3. provenance integrity
4. evidence-status guardrails
5. safety precedence
6. replication/generalization gates
7. report-language gates
8. end-to-end synthetic execution

Synthetic data is explicitly non-evidence and must never create an EVD claim.

## Exit criteria

A build may be marked INTEGRITY_PASS only when:
- required contracts load;
- forbidden transitions are rejected;
- required provenance fields are present;
- unknown data remains unknown;
- safety blocks override promotion;
- claim upgrades obey V1.4;
- replication/generalization require registered criteria;
- report publication gates reject incomplete lineage;
- synthetic execution reaches the expected terminal state.
