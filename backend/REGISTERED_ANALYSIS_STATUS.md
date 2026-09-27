# Registered Analysis Runtime

The validation runtime now supports an immutable dataset manifest and a registered paired-effect calculation.

Manifest fields:
- manifest_id
- analysis_spec_id
- values_hash
- total sample count
- complete paired count
- missing count

The paired result is blocked if the input hash differs from the locked manifest.

A 95% confidence interval is returned only when at least two complete pairs exist. It is explicitly labelled `ESTIMABLE_NORMAL_APPROX`; the implementation does not silently substitute t critical values.

Endpoint: POST /validation/paired

The result remains DRV provenance and is not automatically promoted to EVD or a scientific claim.
