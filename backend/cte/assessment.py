"""Assessment boundary: observations become typed measurements with provenance."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .catalog import get_matrix_item
from .provenance import Provenance, ProvenanceTag, content_hash

@dataclass(frozen=True)
class Measurement:
    measurement_id: str
    item_id: str
    value: float
    provenance: Provenance

@dataclass(frozen=True)
class AssessmentProfile:
    measurements: tuple[Measurement, ...]
    source_id: str
    source_version: str
    def by_domain(self, domain: str) -> tuple[Measurement, ...]:
        return tuple(m for m in self.measurements if get_matrix_item(m.item_id).domain == domain)
    def values(self) -> dict[str, float]:
        return {m.item_id: m.value for m in self.measurements}

def _validate_value(item_id: str, value: float) -> None:
    item = get_matrix_item(item_id)
    if not 0 <= value <= 10:
        raise ValueError(f"{item_id} must be within 0-10")
    if item.domain == "P1" and item.kind != "state":
        raise ValueError(f"{item_id} violates P1 state contract")
    if item.domain == "P2" and item.kind != "trait":
        raise ValueError(f"{item_id} violates P2 trait contract")

def build_measurement(item_id: str, value: float, *, source_id: str, source_version: str, observation_id: str) -> Measurement:
    _validate_value(item_id, value)
    item = get_matrix_item(item_id)
    provenance = Provenance(
        tag=ProvenanceTag.OBS,
        source_id=source_id,
        source_version=source_version,
        input_hash=content_hash({"observation_id": observation_id, "item_id": item_id, "value": value}),
        note=f"Observed measurement for {item.name}",
    )
    return Measurement(f"{observation_id}:{item_id}", item_id, value, provenance)

def build_profile(observations: list[dict[str, Any]], *, source_id: str, source_version: str) -> AssessmentProfile:
    measurements = tuple(
        build_measurement(
            str(row["item_id"]), float(row["value"]),
            source_id=source_id, source_version=source_version,
            observation_id=str(row["observation_id"]),
        ) for row in observations
    )
    return AssessmentProfile(measurements, source_id, source_version)
