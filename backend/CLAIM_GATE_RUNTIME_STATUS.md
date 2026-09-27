# Claim Gate Runtime Status

The Claim Gate now derives upstream evidence types directly from the in-memory Evidence Graph Registry. Clients cannot satisfy a claim transition by declaring prerequisite node types in the request.

`POST /graph/claim-gate` accepts a registered `result_id`, current state, target level, and provenance class. The registry traverses registered incoming lineage and supplies the actual upstream node types to the Claim Gate.

This closes the previous declaration-only bypass. Persistent graph storage remains a separate implementation layer.

The registry also preserves claim-state history using immutable claim snapshots linked by `DERIVED_FROM`. Result-backed claims receive an explicit `RESULT -> CLAIM` `SUPPORTS` edge.

Manual graph edges now require both endpoints to be pre-registered; node registration accepts explicit provenance, version, and metadata so claim prerequisites can be derived from the graph rather than client-declared types.
