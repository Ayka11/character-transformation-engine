# Evidence Graph Runtime Status

The first executable graph boundary is now implemented.

Supported node types follow the V1.4 contract. Supported edge types follow the V1.4 contract. Node registration requires a recognized provenance class.

The runtime enforces the first structural transition:

`ANALYSIS --RESULTS_IN--> RESULT`

Invalid directions are rejected rather than silently rewritten.

Endpoint: POST /graph/edge

Current implementation is an executable contract boundary; persistence remains defined by the V1.4 SQL schema and is not claimed to be connected yet.
