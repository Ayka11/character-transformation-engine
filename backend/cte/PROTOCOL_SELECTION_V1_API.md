# Protocol Selection API V1

## Endpoint

`POST /protocols/v1/select-candidates`

This additive endpoint wraps the deterministic Protocol Selection Engine V1.0.
The caller supplies a protocol registry snapshot plus canonical profile, current state,
goals, contexts, constraints, capacity, and safety status. The API does not persist or
approve registry entries; registry governance and persistence remain separate work.

## Contract and safety

- `safety_status` must be `PASS`, `BLOCK`, or `UNKNOWN`.
- Unknown safety cannot return `ELIGIBLE_FOR_REVIEW`; a block makes active candidates
  ineligible.
- Missing required measurements, state, or capacity are not imputed.
- Invalid registry contracts and unknown safety labels return HTTP 422.
- The response contains no ranking or authoritative scalar. Every candidate has
  `selection_authorized=false` and `requires_human_review=true`.
- The endpoint is not authorization to execute an intervention.
- Scientific status remains `IMPLEMENTATION_BASELINE`.

## Example request

```json
{
  "protocols": [{
    "protocol_id": "regulation.pause",
    "version": "1.0",
    "status": "ACTIVE",
    "required_measurements": ["P3.pause_capacity"],
    "required_state": {"sprint_status": "ACTIVE"},
    "goal_tags": ["self_regulation"],
    "context_tags": ["work"],
    "contraindications": ["acute_crisis"],
    "minimum_capacity": 4,
    "evidence_class": "MODEL_DERIVED"
  }],
  "profile": {"P3.pause_capacity": 6},
  "state": {"sprint_status": "ACTIVE"},
  "goals": ["self_regulation"],
  "contexts": ["work"],
  "constraints": [],
  "capacity": 6,
  "safety_status": "PASS"
}
```

The registry is caller-supplied in this version; do not treat arbitrary client-provided
protocols as approved. Production integration must load an authenticated, governed
registry and preserve registry version/hash and selection provenance.
