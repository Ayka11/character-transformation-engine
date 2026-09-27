# Integrated Decision & Intervention Engine V1.7

Status: MDL/DRV architecture specification — not empirically validated.

V1.7 closes the operational loop between the scientific evidence layers and the user runtime.

Closed loop:
ASSESS → CLASSIFY → SELECT REGISTERED RULE → SAFETY CHECK → INTERVENTION → MEASURE → ADAPT → LOG → EVALUATE

The engine distinguishes:
- EVD: evidence-supported rules
- MDL: model-derived rules
- HYP: hypothesis-driven rules
- RPT: reported/self-report inputs
- DRV: derived decisions

No rule is promoted merely because it produces an observed improvement in one user.

## Core safety principle

Intervention execution is subordinate to:
1. registered rule scope
2. safety constraints
3. current capacity
4. data quality
5. evidence status

When required inputs are unknown, the engine uses UNKNOWN/INDETERMINATE rather than a favorable default.

## Adaptive loop

1. Build baseline.
2. Estimate current state.
3. Select an eligible intervention rule.
4. Assign an adaptive load level.
5. Execute the intervention.
6. Capture behavior/state outcomes.
7. Evaluate response.
8. Decide CONTINUE, ADJUST, HOLD, DEESCALATE, or STOP.
9. Preserve provenance.
10. Feed eligible results into the research pipeline.

This is an execution architecture, not a claim that any intervention is clinically or scientifically validated.
