# Longitudinal Validation Runtime

The executable validation layer now includes descriptive longitudinal change metrics:

- absolute_change
- relative_change
- standardized_change
- within_person_effect (currently the same descriptive standardized change metric)

Missing baseline/current pairs are excluded from the descriptive calculation but explicitly reported as a limitation; no imputation occurs.

Confidence intervals and inferential p-values are not fabricated by this layer. The existing V1.3 contract requires CI where inferential effect sizes are estimable, so an inferential statistics implementation must be added before those fields can be marked estimable.

Endpoint: POST /validation/longitudinal
