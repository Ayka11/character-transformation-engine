"""Longitudinal descriptive change analysis.

Implements the explicitly specified longitudinal metrics at a descriptive
boundary. Inferential CI/p-values are intentionally not fabricated here.
"""
from __future__ import annotations
from dataclasses import dataclass
from statistics import mean, pstdev
from .provenance import Provenance, ProvenanceTag, content_hash

@dataclass(frozen=True)
class LongitudinalResult:
    n: int
    absolute_change: float | None
    relative_change: float | None
    standardized_change: float | None
    within_person_effect: float | None
    ci_status: str
    limitations: tuple[str, ...]
    provenance: Provenance

def longitudinal_change(baseline: list[float | None], current: list[float | None], *, source_id: str="cte.longitudinal", source_version: str="2.1.0") -> LongitudinalResult:
    if len(baseline) != len(current):
        raise ValueError("baseline and current must have equal length")
    pairs=[(b,c) for b,c in zip(baseline,current) if b is not None and c is not None]
    if not pairs:
        prov=Provenance(ProvenanceTag.DRV,source_id,source_version,content_hash({"baseline":baseline,"current":current}),"Longitudinal descriptive result; not evidence")
        return LongitudinalResult(0,None,None,None,None,"NOT_ESTIMABLE",("No complete baseline/current pairs",),prov)
    changes=[c-b for b,c in pairs]
    avg_change=mean(changes)
    # Relative change is the mean of each complete participant pair's
    # relative change, rather than change of pooled means.
    individual_relative=[(c-b)/b for b,c in pairs if b != 0]
    relative=None if len(individual_relative) != len(pairs) else mean(individual_relative)
    sd=pstdev(changes)
    standardized=None if sd == 0 else avg_change/sd
    prov=Provenance(ProvenanceTag.DRV,source_id,source_version,content_hash({"baseline":baseline,"current":current}),"Longitudinal descriptive result; not evidence")
    limitations=[]
    if len(pairs) < len(baseline):
        limitations.append("Incomplete pairs excluded descriptively; missingness requires registered sensitivity analysis")
    limitations.append("Confidence interval not estimated by this descriptive runtime")
    return LongitudinalResult(len(pairs),avg_change,relative,standardized,standardized,"NOT_ESTIMATED",tuple(limitations),prov)
