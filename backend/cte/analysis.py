"""Minimal QC and descriptive analysis runtime.

This implements the first executable validation boundary only. It does not
perform inferential statistics or establish evidence.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from statistics import mean
from .provenance import Provenance, ProvenanceTag, content_hash

class QCStatus(str, Enum):
    PASS="PASS"
    FAIL="FAIL"
    NOT_ESTIMABLE="NOT_ESTIMABLE"

@dataclass(frozen=True)
class AnalysisQC:
    status: QCStatus
    n: int
    missing: int
    duplicate_ids: int
    out_of_range: int
    reason: str

@dataclass(frozen=True)
class DescriptiveResult:
    n: int
    mean: float | None
    minimum: float | None
    maximum: float | None
    qc: AnalysisQC
    provenance: Provenance

def qc_values(values: list[float | None], ids: list[str] | None = None) -> AnalysisQC:
    ids = ids or [str(i) for i in range(len(values))]
    seen=set()
    duplicates=0
    for item in ids:
        if item in seen: duplicates += 1
        seen.add(item)
    missing=sum(v is None for v in values)
    invalid=sum(v is not None and not 0 <= v <= 10 for v in values)
    if invalid or duplicates:
        return AnalysisQC(QCStatus.FAIL,len(values),missing,duplicates,invalid,"Range or duplicate-ID QC failure")
    if not [v for v in values if v is not None]:
        return AnalysisQC(QCStatus.NOT_ESTIMABLE,len(values),missing,duplicates,invalid,"No estimable observations")
    status=QCStatus.PASS if missing == 0 else QCStatus.NOT_ESTIMABLE
    return AnalysisQC(status,len(values),missing,duplicates,invalid,"Complete observations" if status == QCStatus.PASS else "Missingness requires explicit handling")

def descriptive(values: list[float | None], *, source_id: str="cte.analysis", source_version: str="2.1.0", ids: list[str] | None=None) -> DescriptiveResult:
    qc=qc_values(values,ids)
    usable=[v for v in values if v is not None]
    prov=Provenance(ProvenanceTag.DRV,source_id,source_version,content_hash(values),"Descriptive runtime result; not evidence")
    if qc.status == QCStatus.FAIL or not usable:
        return DescriptiveResult(0 if not usable else len(usable),None,None,None,qc,prov)
    return DescriptiveResult(len(usable),mean(usable),min(usable),max(usable),qc,prov)
