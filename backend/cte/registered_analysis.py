"""Registered paired analysis with immutable manifest hashing."""
from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from statistics import mean
from .provenance import Provenance, ProvenanceTag, content_hash

@dataclass(frozen=True)
class DatasetManifest:
    manifest_id: str
    analysis_spec_id: str
    values_hash: str
    n_total: int
    n_complete: int
    missing: int

def lock_manifest(baseline: list[float | None], current: list[float | None], *, manifest_id: str, analysis_spec_id: str) -> DatasetManifest:
    if len(baseline) != len(current):
        raise ValueError("baseline and current must have equal length")
    pairs=[(b,c) for b,c in zip(baseline,current) if b is not None and c is not None]
    return DatasetManifest(manifest_id, analysis_spec_id, content_hash({"baseline":baseline,"current":current}), len(baseline), len(pairs), len(baseline)-len(pairs))

@dataclass(frozen=True)
class PairedEffectResult:
    manifest_id: str
    analysis_spec_id: str
    n: int
    mean_change: float | None
    standard_error: float | None
    ci95_low: float | None
    ci95_high: float | None
    status: str
    provenance: Provenance

def paired_effect(baseline: list[float | None], current: list[float | None], manifest: DatasetManifest) -> PairedEffectResult:
    if manifest.values_hash != content_hash({"baseline":baseline,"current":current}):
        raise ValueError("dataset manifest hash mismatch")
    changes=[c-b for b,c in zip(baseline,current) if b is not None and c is not None]
    prov=Provenance(ProvenanceTag.DRV,"cte.registered_analysis","2.1.0",manifest.values_hash,"Registered paired descriptive/inferential result; not evidence")
    if len(changes) < 2:
        return PairedEffectResult(manifest.manifest_id,manifest.analysis_spec_id,len(changes),None,None,None,None,"NOT_ESTIMABLE",prov)
    m=mean(changes)
    variance=sum((x-m)**2 for x in changes)/(len(changes)-1)
    se=sqrt(variance/len(changes))
    # Normal-approximation CI is explicitly labelled; t critical values are not approximated silently.
    margin=1.96*se
    return PairedEffectResult(manifest.manifest_id,manifest.analysis_spec_id,len(changes),m,se,m-margin,m+margin,"ESTIMABLE_NORMAL_APPROX",prov)
