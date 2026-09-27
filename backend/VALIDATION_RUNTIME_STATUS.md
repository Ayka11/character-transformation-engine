# Validation Runtime Status

The first executable validation boundary is now present.

QC checks:
- missingness is quantified;
- duplicate observation IDs fail QC;
- values outside the 0-10 measurement contract fail QC;
- missing values are never silently imputed;
- no estimable observations return NOT_ESTIMABLE.

Descriptive analysis currently returns n, mean, minimum, maximum, QC status, and DRV provenance.

This is intentionally below inferential analysis. It does not calculate causal effects, p-values, confidence intervals, replication, generalization, or evidence-supported claims.

Next boundary: registered analysis specifications and longitudinal change analysis with explicit effect-size/CI requirements where estimable.
