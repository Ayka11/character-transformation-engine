# Transformation Runtime — Production Readiness

## Closed-loop invariant

A transformation is production-valid only when the following chain is durable and internally consistent:

PRECONDITION → SAFETY → INTERVENTION → BEFORE SNAPSHOT → AFTER SNAPSHOT → DIFF → VALIDATION → CERTIFICATE → LEDGER → TERMINAL JOURNAL

EXECUTED is not VALIDATED, and VALIDATED is not COMPLETED.

## Persistence invariants

- State snapshots are immutable.
- Snapshot hashes and lineage hashes are independently verifiable.
- Transformation ledger entries are immutable.
- Request hashes provide idempotent replay protection.
- Character + sequence claims use optimistic concurrency.
- Non-initial transformations require a valid parent snapshot belonging to the same character.
- Terminal journal state is written only after durable ledger commit.
- Recovery never re-runs intervention for a request already represented by the ledger.

## Certificate invariant

A certificate is permitted only for a VALIDATED transition.

The integrity verifier must reject:
- validated entry without certificate;
- validated entry without after snapshot;
- certificate attached to failed/partial/rolled-back execution;
- forged before/after hash;
- forged snapshot lineage.

## Recovery invariant

For every crash boundary, recovery must resolve the durable state without creating a second intervention:

1. before snapshot only → non-terminal attempt;
2. intervention started → non-terminal attempt;
3. after snapshot captured → recoverable validation;
4. ledger committed → idempotent replay;
5. terminal journal committed → terminal;
6. corrupted snapshot/lineage → integrity failure, never silent promotion.

## API inspection

The transformation inspection API exposes:
- lineage;
- snapshot verification;
- ledger entries;
- per-entry integrity;
- global integrity scan;
- recovery scan;
- journal inspection.

Missing resources return HTTP 404.

## Final verification gates

Production readiness requires:
- backend pytest green;
- PostgreSQL integration green;
- adversarial/invariant suite green;
- transformation E2E green;
- Science Lab UI check green when present;
- no unresolved integrity findings;
- no non-terminal recovery attempts in a clean runtime;
- API smoke checks successful.
