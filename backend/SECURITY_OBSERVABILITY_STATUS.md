# Security & Observability Status

Status: **IMPLEMENTED / CI-TESTED / NOT PRODUCTION-HARDENED**

Implemented:
- configurable in-process sliding-window rate limiting with HTTP 429/Retry-After;
- protected operational backup/restore and retention API via CTE_OPS_API_KEY;
- optional read/write API-key authentication using environment variables;
- read/write authorization split: GET/HEAD/OPTIONS accept read or write keys, mutating routes require the write key;
- public health/docs/UI/assets routes remain available for deployment bootstrap;
- request IDs via X-Request-ID;
- X-Process-Time-Ms latency response header;
- operational HTTP_REQUEST audit events persisted through the configured runtime store;
- Science Lab browser UI can store and send X-CTE-API-Key.

Environment:
- CTE_API_KEY: single fallback key for both read and write;
- CTE_READ_API_KEY: read access;
- CTE_WRITE_API_KEY: write access;
- CTE_LOG_LEVEL: logging level.

Production boundary:
- secret storage/rotation and external identity provider integration are not implemented;
- rate limiting, abuse protection, backup/recovery and long-term audit retention remain open;
- API key authentication is a lightweight deployment safeguard, not a replacement for enterprise IAM.

CI:
- GitHub Actions run #397 passed the backend suite with the security/observability tests.
- The live PostgreSQL integration job in the same run also passed.