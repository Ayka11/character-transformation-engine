# Canonical Compatibility Matrix V2 API

## Endpoint

`POST /compatibility/v2/canonical`

Accepts `profile_a` and `profile_b` keyed by registered Master Matrix V1.0 item IDs,
with optional `roles_a`, `roles_b`, and `contexts`. Values are validated against
each catalog item's declared scale. Invalid IDs or values return HTTP 422. Missing
values are not imputed.

The response includes Matrix V2 rows, row coverage, `catalog_coverage` by P1–P5,
scientific status, and canonical input provenance for both profiles. The catalog
coverage object lists supplied and missing item IDs per domain and whether both
profiles cover the full registered catalog. Partial coverage is informational and is
not treated as incompatibility.

Same-item alignment is descriptive; heuristic role/value rules remain conditional and
require human review. No scalar compatibility score is produced.

The existing `POST /compatibility` route and V1/V2/V3 response contract are unchanged.
This additive endpoint is an implementation baseline, not an empirically validated
predictive service.
