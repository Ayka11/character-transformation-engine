# Evidence Graph Registry Status

The executable graph registry now enforces lineage and immutability.

Required RESULT lineage:

`DATASET or MEASUREMENT -> ANALYSIS -> RESULT`

A RESULT without an incoming `RESULTS_IN` edge from ANALYSIS is rejected. An ANALYSIS without upstream DATASET or MEASUREMENT is rejected when RESULT lineage is checked.

Node and edge IDs are immutable: re-registering the same ID with a different content hash is rejected.

The registry is currently in-memory. The V1.4 SQL schema remains the persistence contract; this implementation does not claim database persistence.
