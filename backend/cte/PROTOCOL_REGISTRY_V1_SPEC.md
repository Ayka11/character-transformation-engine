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
