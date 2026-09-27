# Compatibility & Recovery Audit — Master Matrix V1.0

Status: IMPLEMENTED / NOT EMPIRICALLY VALIDATED

## 1. Compatibility Engine V1.0

| Requirement | Runtime implementation | Status |
|---|---|---|
| V1 Bio / Tempo vector | `compatibility_v1()` | IMPLEMENTED |
| Tempo delta | `dimensions.tempo.delta` / `absolute_delta` | IMPLEMENTED when explicitly supplied |
| Energy delta | `dimensions.energy.delta`; accepts `energy` or Master Matrix `subjective_energy` | IMPLEMENTED |
| Reactivity delta | `dimensions.reactivity.delta` | IMPLEMENTED when explicitly supplied |
| Recovery delta | `dimensions.recovery.delta`; accepts `recovery` or Master Matrix `recovery_index` | IMPLEMENTED |
| V2 Values vector | `compatibility_v2()` | IMPLEMENTED |
| Spearman rank correlation | tie-aware ranked correlation | IMPLEMENTED |
| Top Alignments | `top_alignments` | IMPLEMENTED |
| Value Gaps | `value_gaps` | IMPLEMENTED |
| Conflict zones | explicit heuristic map including Order vs Autonomy | IMPLEMENTED / HEURISTIC |
| V3 Behavioral vector | `compatibility_v3()` | IMPLEMENTED |
| Leader + Strategist synergy | default role interaction | IMPLEMENTED / MODEL-DERIVED |
| Leader + Leader competition | default role interaction | IMPLEMENTED / MODEL-DERIVED |
| Scenarios / interventions | `scenarios_and_interventions()` | IMPLEMENTED |
| 24-hour decision buffer | material tempo-gap scenario | IMPLEMENTED / MODEL-DERIVED |
| Single authoritative compatibility % | deliberately absent | PASS |

The public API is `POST /compatibility` and returns V1, V2, V3, scenario mappings, provenance and `authoritative_scalar=false`.

### Compatibility boundary

Tempo and reactivity are not part of the current canonical P1 Master Matrix item list. The runtime therefore does **not** silently infer them from unrelated measurements. Missing dimensions are reported explicitly and the V1 vector can be `PARTIAL`.

All compatibility calculations are tagged `DRV` and marked `MODEL_DERIVED_NOT_VALIDATED`. Conflict labels and default role interactions are heuristics/model rules, not empirical evidence.

## 2. Recovery / Detox Level A

| Requirement | Runtime implementation | Status |
|---|---|---|
| Stress >= 8 => Level A | `evaluate_recovery_gate()` | IMPLEMENTED |
| C_cap < 3 => Level A | `evaluate_recovery_gate()` | IMPLEMENTED |
| Missing capacity inputs remain UNKNOWN/safety blocked | delegates to `compute_capacity()` | IMPLEMENTED |
| Recovery < 4/10 for 3 consecutive days | `evaluate_bio_reset()` | IMPLEMENTED |
| Bio Reset pauses sprint | `record_day(..., recovery_indices=...)` | IMPLEMENTED |
| Incoming stimulus restriction | `RESTRICT_INCOMING_STIMULI` | IMPLEMENTED |
| Micro-actions limited to 5–30 s | `micro_action_seconds=(5,30)` | IMPLEMENTED |
| Exclude cognitively costly tests | `exclude_cognitively_costly_tests=true` | IMPLEMENTED |
| Compromised state separated from traits | `isolate_compromised_state_from_traits()` | IMPLEMENTED |

The public API exposes:
- `POST /runtime/recovery-gate`
- `POST /runtime/bio-reset`
- `POST /runtime/recovery-plan`
- `POST /runtime/state-trait-isolation`

## 3. Pipeline integration

```text
DAILY TELEMETRY (P1)
        |
        v
CAPACITY ENGINE (C_cap)
        |
        +---- stress >= 8 OR C_cap < 3 ----> LEVEL A / RECOVERY
        |                                      |
        |                                      +--> Bio Reset / stimulus restriction
        |                                      +--> 5–30 s micro-actions
        |                                      +--> sprint pause
        |
        +---- capacity available -----------> TRAIT GRAPH
                                               |
                                               +--> root-cause routing
                                               +--> Levels B–E sprint path
```

The existing TraitGraph routes an intervention toward a low-scoring eligible downstream blocker rather than automatically lowering the requested top-level trait.

## 4. Provenance and state/trait separation

Observed assessment measurements are created with `OBS` provenance. Compatibility and recovery decisions are model-derived `DRV` outputs with input hashes. The recovery module records a compromised **CURRENT STATE** without rewriting P2–P5 trait values.

These rules are implementation safeguards, not claims that the underlying model has been empirically validated.

## 5. Verification status

The changes are committed directly to `main`.

Relevant current components:
- `backend/cte/compatibility.py`
- `backend/cte/recovery.py`
- `backend/cte/sprint.py`
- `backend/cte/api.py`
- `backend/tests/test_compatibility.py`
- `backend/tests/test_recovery.py`
- `backend/tests/test_sprint.py`

GitHub Actions is configured to run the backend suite on pushes to `main`. The latest observed run (#39) executed pytest and reported 97 passed / 34 failed. The failures are in pre-existing claim-gate, graph-lineage, persistence and longitudinal contracts; the new Compatibility/Recovery tests were not present among the reported failures.

Therefore the repository status remains **IMPLEMENTATION_BASELINE**, not fully TESTED/VALIDATED.

## 6. Remaining architectural gaps

1. Persistent daily telemetry aggregation for maintaining the 3-day recovery streak across independent API calls is not yet a dedicated durable service. The current sprint endpoint accepts the recovery history explicitly.
2. Tempo and reactivity require an explicit measurement contract if they are intended to become canonical Master Matrix variables.
3. The current C_cap formula is preserved from the existing runtime. Its numeric maximum is 5.3 on the 0–10 inputs, so Levels D/E are unreachable under that formula. This should be resolved by a separately registered model/spec change rather than silently altering the formula.
4. Empirical validation of compatibility rules, recovery thresholds and intervention efficacy remains outside the implementation baseline.
5. Production database, authentication/authorization and observability remain separate production-readiness work.

