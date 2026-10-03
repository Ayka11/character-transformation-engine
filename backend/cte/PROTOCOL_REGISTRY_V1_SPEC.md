# Governed Protocol Registry V1 — service contract

## Data model

- A definition is an immutable snapshot keyed by `protocol_id@version`.
- Registration always creates lifecycle status `DRAFT`, regardless of a caller-supplied status.
- Definition hash is computed by the runtime store and returned for provenance.
- Lifecycle changes are append-only `PROTOCOL_LIFECYCLE_CHANGED` events with actor, reason,
  protocol/version identity, output hash and provenance reference.
- Lifecycle state transitions are restricted: `DRAFT → ACTIVE|RETIRED`,
  `ACTIVE → SUSPENDED|RETIRED`, `SUSPENDED → ACTIVE|RETIRED`; `RETIRED` is terminal.
- New definition changes require a new version. An existing immutable version cannot be overwritten.

## API integration and security boundary

This change supplies persistence and lifecycle primitives, not HTTP endpoints. Callers must
authenticate the actor and authorize the operation before invoking mutations. An `actor_id`
field is audit attribution, not proof of identity. Do not expose registry mutation routes
until authentication, role separation (author/reviewer/approver), and concurrency controls
are implemented. The current service records the lifecycle history and does not itself
provide transactional compare-and-swap across concurrent transitions.

## Scientific and operational limitations

Protocol activation is a governance state, not evidence of efficacy or safety. Registry
status does not authorize execution. Candidate selection remains review-only and must be
re-evaluated with current profile/state/safety inputs. `SCIENTIFIC_STATUS` remains
`IMPLEMENTATION_BASELINE` until empirical validation and replication criteria are met.


## Registry-backed candidate selection

`POST /protocols/v1/select-registered-candidates` accepts explicit `protocol_id` and
`version` references and resolves each against the immutable registry. Unknown versions
fail closed with HTTP 404; duplicate references are rejected. The response includes each
candidate's definition hash and marks the registry source. Existing selector safeguards
remain in force: no ranking, no scalar score, unknown safety remains conditional, and
candidate selection never authorizes execution. This endpoint is read-only; it does not
expose registry mutation operations.


## Atomic lifecycle transitions (v1.1 implementation)

Lifecycle transitions use a storage-level compare-and-append operation. SQLite acquires a
write reservation before checking the latest status; PostgreSQL serializes updates for each
protocol version with a transaction-scoped advisory lock. The expected status is checked
inside the same transaction that appends the event. A competing transition based on stale
state fails with `concurrent lifecycle transition conflict` and must be re-read and explicitly
retried by the caller. This provides concurrency control, not caller authentication or role
authorization; those remain required before exposing mutation APIs.


## Integrity audit (read-only)

The registry service exposes a read-only integrity audit for a protocol version. It recomputes
the immutable definition hash, validates lifecycle event identity/output hashes and provenance,
checks the initial DRAFT event and allowed transition sequence, and reports structured
violation codes. A passing audit establishes internal consistency of stored records only; it
does not establish that protocol content is scientifically valid, effective, safe, or correctly
attributed to a real person. The audit is a service method, not a new HTTP endpoint.
