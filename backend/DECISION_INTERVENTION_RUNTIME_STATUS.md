# Decision & Intervention Runtime Status

V1.7 executable baseline is implemented as an in-memory decision/intervention service.

Implemented:
- versioned registered intervention rules with provenance classes;
- active-rule-only selection;
- domain scope and required-input checks;
- contraindication-aware safety gating;
- PASS/HOLD/BLOCK assignment states;
- intervention session creation and explicit missing measurement handling;
- response evaluation across target/state/behavior/safety/adherence/capacity dimensions;
- safety-first adaptation decisions: CONTINUE, ADJUST, HOLD, DEESCALATE, STOP, INSUFFICIENT_DATA;
- research links that explicitly mark runtime observations as not automatically evidence;
- audit events for assignments and runtime decisions.

Runtime persistence is currently in-memory. Intervention outcomes do not automatically promote model-derived or hypothesis-driven rules to evidence-supported status.
