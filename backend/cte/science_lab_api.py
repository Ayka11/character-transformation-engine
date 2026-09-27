"""FastAPI adapter for Science Lab V2.3."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .graph_registry import GraphRegistry
from .persistence import SQLiteRuntimeStore
from .science_lab import ScienceLabService
from .science_lab_report import render_report


class MatrixInput(BaseModel):
    matrix_id: str
    study_id: str
    name: str
    primary_outcome: str
    design: dict[str, Any] = Field(default_factory=dict)
    status: str = "REGISTERED"


class ScenarioInput(BaseModel):
    scenario_id: str
    name: str
    description: str
    conditions: dict[str, Any] = Field(default_factory=dict)
    expected_outcomes: list[str] = Field(default_factory=list)
    independent: bool = True


class ScenarioRunInput(BaseModel):
    payload: dict[str, Any]

class ScenarioMatrixGenerationInput(BaseModel):
    factors: dict[str, list[Any]]
    max_scenarios: int = Field(128, ge=1)
    name_prefix: str = "Factorial"

class ReplicationAssessmentInput(BaseModel):
    assessment_id: str
    replication_spec_id: str
    source_claim_id: str
    primary_outcome_id: str
    source_result_id: str
    independent_study_id: str
    dataset_manifest_id: str
    protocol_hash: str
    input_hash: str
    source_estimate: float | None = None
    target_estimate: float | None = None
    source_effect_size: float | None = None
    target_effect_size: float | None = None
    source_ci_low: float | None = None
    source_ci_high: float | None = None
    target_ci_low: float | None = None
    target_ci_high: float | None = None
    effect_tolerance: float = Field(0.20, ge=0)
    protocol_fidelity: bool | None = None
    measurement_fidelity: bool | None = None
    outcome_definition: bool | None = None
    data_quality: bool | None = None


class GeneralizationAssessmentInput(BaseModel):
    assessment_id: str
    generalization_spec_id: str
    source_claim_id: str
    source_result_id: str
    source_population: dict[str, Any] = Field(default_factory=dict)
    target_population: dict[str, Any] = Field(default_factory=dict)
    source_context: dict[str, Any] = Field(default_factory=dict)
    target_context: dict[str, Any]
    dataset_manifest_id: str
    source_estimate: float | None = None
    transported_estimate: float | None = None
    transport_error: float | None = None
    dimensions: dict[str, str] = Field(default_factory=dict)
    max_transport_error: float = Field(0.20, ge=0)
    max_heterogeneity: float | None = Field(None, ge=0)
    heterogeneity_statistic: float | None = None


def install_science_lab_api(
    app: FastAPI,
    registry: GraphRegistry,
    store: SQLiteRuntimeStore,
    e2e_coordinator,
):
    research = e2e_coordinator.research
    service = ScienceLabService(registry, store, research, e2e_coordinator)

    @app.post("/science-lab/matrices")
    def create_matrix(p: MatrixInput):
        return asdict(service.register_matrix(**p.model_dump()))

    @app.post("/science-lab/matrices/{matrix_id}/scenarios")
    def create_scenario(matrix_id: str, p: ScenarioInput):
        return asdict(service.register_scenario(matrix_id=matrix_id, **p.model_dump()))

    @app.post("/science-lab/matrices/{matrix_id}/scenarios/{scenario_id}/run")
    def run_scenario(matrix_id: str, scenario_id: str, p: ScenarioRunInput):
        return asdict(service.run_scenario(
            matrix_id=matrix_id,
            scenario_id=scenario_id,
            payload=p.payload,
        ))

    @app.post("/science-lab/matrices/{matrix_id}/generate-scenarios")
    def generate_scenarios(matrix_id: str, p: ScenarioMatrixGenerationInput):
        return {
            "matrix_id": matrix_id,
            "scenarios": [
                asdict(x) for x in service.generate_scenarios(
                    matrix_id=matrix_id,
                    factors=p.factors,
                    max_scenarios=p.max_scenarios,
                    name_prefix=p.name_prefix,
                )
            ],
        }

    @app.post("/science-lab/matrices/{matrix_id}/replication")
    def assess_replication(matrix_id: str, p: ReplicationAssessmentInput):
        return asdict(service.register_replication_assessment(
            matrix_id=matrix_id, **p.model_dump()
        ))

    @app.post("/science-lab/matrices/{matrix_id}/generalization")
    def assess_generalization(matrix_id: str, p: GeneralizationAssessmentInput):
        return asdict(service.register_generalization_assessment(
            matrix_id=matrix_id, **p.model_dump()
        ))

    @app.get("/science-lab/matrices/{matrix_id}/provenance")
    def matrix_provenance(matrix_id: str):
        bundle = service.report_bundle(matrix_id)
        return {
            "matrix_id": matrix_id,
            "transformation_provenance": bundle["transformation_provenance"],
            "downstream_transformation_provenance": bundle["downstream_transformation_provenance"],
            "claim_validation": bundle["claim_validation"],
            "scientific_status": bundle["provenance"]["scientific_status"],
        }

    @app.get("/science-lab/matrices/{matrix_id}/claims")
    def validate_claims(matrix_id: str):
        return service.claim_validation(matrix_id)

    @app.get("/science-lab/matrices/{matrix_id}/statistics")
    def matrix_statistics(matrix_id: str):
        return service.descriptive_statistics(matrix_id)

    @app.get("/science-lab/matrices/{matrix_id}/report")
    def build_report_bundle(matrix_id: str):
        return service.report_bundle(matrix_id)

    @app.get("/science-lab/matrices/{matrix_id}/report.html", include_in_schema=False)
    def render_report_html(matrix_id: str):
        from fastapi.responses import HTMLResponse
        return HTMLResponse(render_report(service.report_bundle(matrix_id)))

    @app.get("/science-lab/matrices/{matrix_id}")
    def get_matrix(matrix_id: str):
        matrix=service.matrices.get(matrix_id)
        if matrix is None:
            raise ValueError("experiment matrix is not registered")
        return {
            "matrix": asdict(matrix),
            "scenarios":[asdict(service.scenarios[x]) for x in matrix.scenario_ids],
            "scenario_runs":[asdict(x) for x in service.runs.values() if x.matrix_id==matrix_id],
        }

    return service
