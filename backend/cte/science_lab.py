"""Science Lab V2.3 runtime.

Experiment Matrix -> Scenario Runs -> Replication Assessment ->
Generalization Assessment -> Claim Validation -> Report Bundle.

This layer composes the already-tested Research Execution and evidence runtime.
It does not silently upgrade model-derived outputs to empirical evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .evidence_graph import register_edge, register_node
from .generalization_engine import evaluate as evaluate_generalization
from .generalization_engine import register_run as register_generalization_run
from .generalization_engine import register_spec as register_generalization_spec
from .graph_registry import GraphRegistry
from .persistence import SQLiteRuntimeStore
from .provenance import Provenance, ProvenanceTag, content_hash
from .replication_engine import evaluate_outcome as evaluate_replication_outcome
from .replication_engine import register_run as register_replication_run
from .replication_engine import register_spec as register_replication_spec
from .research_e2e import ResearchE2ECoordinator
from .research_execution import ResearchService

VERSION = "2.3.0"


def _prov(source: str, payload: Any) -> Provenance:
    return Provenance(
        ProvenanceTag.EXP,
        source,
        VERSION,
        content_hash(payload),
        "Science Lab runtime; not empirical validation",
    )


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    matrix_id: str
    name: str
    description: str
    conditions: dict
    expected_outcomes: tuple[str, ...]
    independent: bool
    immutable_hash: str


@dataclass
class ExperimentMatrix:
    matrix_id: str
    study_id: str
    name: str
    primary_outcome: str
    design: dict
    scenario_ids: tuple[str, ...]
    status: str
    immutable_hash: str


@dataclass
class ScenarioRun:
    run_id: str
    matrix_id: str
    scenario_id: str
    execution_id: str
    status: str
    result_ids: tuple[str, ...]
    estimate_by_outcome: dict[str, float | None]
    safety_status: str
    output_hash: str
    provenance: Provenance


@dataclass(frozen=True)
class ReplicationAssessmentRecord:
    assessment_id: str
    matrix_id: str
    replication_run_id: str
    source_result_id: str
    status: str
    rationale: str
    provenance: Provenance


@dataclass(frozen=True)
class GeneralizationAssessmentRecord:
    assessment_id: str
    matrix_id: str
    generalization_run_id: str
    source_result_id: str
    status: str
    rationale: str
    provenance: Provenance


class ScienceLabService:
    def __init__(
        self,
        registry: GraphRegistry,
        store: SQLiteRuntimeStore | None,
        research: ResearchService,
        coordinator: ResearchE2ECoordinator,
    ):
        self.registry = registry
        self.store = store
        self.research = research
        self.coordinator = coordinator
        self.matrices: dict[str, ExperimentMatrix] = {}
        self.scenarios: dict[str, ScenarioDefinition] = {}
        self.runs: dict[str, ScenarioRun] = {}
        self.replication_assessments: dict[str, ReplicationAssessmentRecord] = {}
        self.generalization_assessments: dict[str, GeneralizationAssessmentRecord] = {}
        self._hydrate()

    def _put(self, namespace: str, key: str, payload: dict):
        if self.store is not None:
            self.store.put_snapshot(namespace, key, payload, VERSION)

    def _hydrate(self):
        if self.store is None:
            return
        for snap in self.store.list_snapshots("science_lab.matrix"):
            p = snap.payload
            self.matrices[snap.key] = ExperimentMatrix(**p)
        for snap in self.store.list_snapshots("science_lab.scenario"):
            p = snap.payload
            self.scenarios[snap.key] = ScenarioDefinition(**p)
        for snap in self.store.list_snapshots("science_lab.run"):
            p = snap.payload
            prov = Provenance(
                ProvenanceTag(p["provenance_tag"]),
                p["source"],
                p["version"],
                p["provenance_input_hash"],
                p["provenance_note"],
            )
            self.runs[snap.key] = ScenarioRun(
                p["run_id"], p["matrix_id"], p["scenario_id"], p["execution_id"],
                p["status"], tuple(p["result_ids"]),
                dict(p["estimate_by_outcome"]), p["safety_status"],
                p["output_hash"], prov,
            )

    def register_matrix(
        self,
        *,
        matrix_id: str,
        study_id: str,
        name: str,
        primary_outcome: str,
        design: dict,
        status: str = "REGISTERED",
    ) -> ExperimentMatrix:
        if matrix_id in self.matrices:
            raise ValueError("experiment matrix already registered")
        if status not in {"DRAFT", "REGISTERED", "ACTIVE"}:
            raise ValueError("unsupported matrix status")
        payload = {
            "matrix_id": matrix_id, "study_id": study_id, "name": name,
            "primary_outcome": primary_outcome, "design": design,
        }
        item = ExperimentMatrix(
            matrix_id, study_id, name, primary_outcome, dict(design), tuple(),
            status, content_hash(payload),
        )
        self.matrices[matrix_id] = item
        self._put("science_lab.matrix", matrix_id, asdict(item))
        self.registry.add_node(register_node(
            matrix_id, "PROTOCOL", matrix_id, "EXP", VERSION,
            {"kind": "EXPERIMENT_MATRIX", "study_id": study_id,
             "primary_outcome": primary_outcome, "design": design, "status": status},
        ))
        return item

    def register_scenario(
        self,
        *,
        scenario_id: str,
        matrix_id: str,
        name: str,
        description: str,
        conditions: dict,
        expected_outcomes: list[str] | None = None,
        independent: bool = True,
    ) -> ScenarioDefinition:
        matrix = self.matrices.get(matrix_id)
        if matrix is None:
            raise ValueError("experiment matrix is not registered")
        if scenario_id in self.scenarios:
            raise ValueError("scenario already registered")
        payload = {
            "scenario_id": scenario_id, "matrix_id": matrix_id, "name": name,
            "description": description, "conditions": conditions,
            "expected_outcomes": list(expected_outcomes or []),
            "independent": independent,
        }
        item = ScenarioDefinition(
            scenario_id, matrix_id, name, description, dict(conditions),
            tuple(expected_outcomes or []), independent, content_hash(payload),
        )
        self.scenarios[scenario_id] = item
        matrix.scenario_ids = tuple(list(matrix.scenario_ids) + [scenario_id])
        self._put("science_lab.scenario", scenario_id, asdict(item))
        self._put("science_lab.matrix", matrix_id, asdict(matrix))
        self.registry.add_node(register_node(
            scenario_id, "PROTOCOL", scenario_id, "EXP", VERSION,
            {"kind": "EXPERIMENT_SCENARIO", "matrix_id": matrix_id,
             "conditions": conditions, "independent": independent},
        ))
        self.registry.add_edge(register_edge(
            f"{matrix_id}:scenario:{scenario_id}",
            self.registry.nodes[matrix_id], self.registry.nodes[scenario_id],
            "USES_PROTOCOL", rationale="scenario belongs to experiment matrix",
        ))
        return item

    def run_scenario(self, *, matrix_id: str, scenario_id: str, payload: dict) -> ScenarioRun:
        matrix = self.matrices.get(matrix_id)
        scenario = self.scenarios.get(scenario_id)
        if matrix is None or scenario is None:
            raise ValueError("matrix and scenario must be registered")
        if scenario.matrix_id != matrix_id:
            raise ValueError("scenario does not belong to matrix")
        if payload.get("execution_id") is None:
            raise ValueError("scenario payload requires execution_id")

        result = self.coordinator.run(**payload)
        execution_status = result["status"]
        research = result.get("research") or {}
        result_rows = research.get("results") or []
        result_ids = tuple(str(x["result_id"]) for x in result_rows)
        estimates = {
            str(x["outcome_id"]): x.get("estimate") for x in result_rows
        }
        safety_status = "BLOCK" if execution_status == "BLOCKED" else "PASS"
        provenance_payload = {
            "matrix_id": matrix_id, "scenario_id": scenario_id,
            "execution_id": payload["execution_id"], "status": execution_status,
            "result_ids": result_ids, "estimates": estimates,
        }
        prov = _prov("science_lab.scenario_run", provenance_payload)
        item = ScenarioRun(
            run_id=f"{matrix_id}:{scenario_id}:{payload['execution_id']}",
            matrix_id=matrix_id,
            scenario_id=scenario_id,
            execution_id=payload["execution_id"],
            status=execution_status,
            result_ids=result_ids,
            estimate_by_outcome=estimates,
            safety_status=safety_status,
            output_hash=content_hash(provenance_payload),
            provenance=prov,
        )
        self.runs[item.run_id] = item
        self._put("science_lab.run", item.run_id, {
            "run_id": item.run_id,
            "matrix_id": item.matrix_id,
            "scenario_id": item.scenario_id,
            "execution_id": item.execution_id,
            "status": item.status,
            "result_ids": list(item.result_ids),
            "estimate_by_outcome": item.estimate_by_outcome,
            "safety_status": item.safety_status,
            "output_hash": item.output_hash,
            "provenance_tag": prov.tag.value,
            "source": prov.source_id,
            "version": prov.source_version,
            "provenance_input_hash": prov.input_hash,
            "provenance_note": prov.note,
        })
        self.registry.add_node(register_node(
            item.run_id, "ANALYSIS", item.run_id, "EXP", VERSION,
            {"kind": "SCENARIO_RUN", "matrix_id": matrix_id,
             "scenario_id": scenario_id, "execution_id": item.execution_id,
             "status": item.status, "result_ids": list(result_ids),
             "output_hash": item.output_hash},
        ))
        for result_id in result_ids:
            if result_id in self.registry.nodes:
                self.registry.add_edge(register_edge(
                    f"{item.run_id}:result:{result_id}",
                    self.registry.nodes[result_id], self.registry.nodes[item.run_id],
                    "DERIVED_FROM", rationale="scenario run references research result",
                ))
        return item

    def register_replication_assessment(
        self,
        *,
        matrix_id: str,
        assessment_id: str,
        replication_spec_id: str,
        source_claim_id: str,
        primary_outcome_id: str,
        source_result_id: str,
        independent_study_id: str,
        dataset_manifest_id: str,
        protocol_hash: str,
        input_hash: str,
        source_estimate: float | None,
        target_estimate: float | None,
        source_effect_size: float | None,
        target_effect_size: float | None,
        source_ci_low: float | None = None,
        source_ci_high: float | None = None,
        target_ci_low: float | None = None,
        target_ci_high: float | None = None,
        effect_tolerance: float = 0.20,
        protocol_fidelity: bool | None = None,
        measurement_fidelity: bool | None = None,
        outcome_definition: bool | None = None,
        data_quality: bool | None = None,
    ) -> ReplicationAssessmentRecord:
        matrix = self.matrices.get(matrix_id)
        source = self.registry.nodes.get(source_result_id)
        if matrix is None or source is None or source.node_type != "RESULT":
            raise ValueError("matrix and source RESULT must be registered")
        if assessment_id in self.replication_assessments:
            raise ValueError("replication assessment already registered")
        spec = register_replication_spec(
            replication_spec_id, source_claim_id, primary_outcome_id,
            criteria={"effect_tolerance": effect_tolerance},
        )
        run = register_replication_run(
            f"{assessment_id}:run", spec,
            source_result_node_id=source_result_id,
            independent_study_id=independent_study_id,
            dataset_manifest_id=dataset_manifest_id,
            protocol_hash=protocol_hash,
            input_hash=input_hash,
            independent=True,
        )
        outcome = evaluate_replication_outcome(
            run,
            source_estimate=source_estimate, target_estimate=target_estimate,
            source_effect_size=source_effect_size, target_effect_size=target_effect_size,
            source_ci_low=source_ci_low, source_ci_high=source_ci_high,
            target_ci_low=target_ci_low, target_ci_high=target_ci_high,
            effect_tolerance=effect_tolerance,
            protocol_fidelity=protocol_fidelity,
            measurement_fidelity=measurement_fidelity,
            outcome_definition=outcome_definition,
            data_quality=data_quality,
        )
        self.registry.add_node(register_node(
            run.replication_run_id, "REPLICATION", run.replication_run_id, "EXP",
            "1.5", {"kind":"SCIENCE_LAB_REPLICATION_RUN",
                     "matrix_id":matrix_id,"source_result_id":source_result_id,
                     "independent":True,"criteria_registered":True,
                     "assessment_status":"REGISTERED"},
        ))
        self.registry.add_edge(register_edge(
            f"{run.replication_run_id}:replicates:{source_result_id}",
            self.registry.nodes[run.replication_run_id], source,
            "REPLICATES", rationale="Science Lab replication run",
        ))
        item = ReplicationAssessmentRecord(
            assessment_id, matrix_id, run.replication_run_id, source_result_id,
            outcome.overall_outcome, outcome.rationale, outcome.provenance,
        )
        self.replication_assessments[assessment_id] = item
        self._put("science_lab.replication", assessment_id, {
            **asdict(item),
            "provenance_tag": item.provenance.tag.value,
            "source": item.provenance.source_id,
            "version": item.provenance.source_version,
            "provenance_input_hash": item.provenance.input_hash,
            "provenance_note": item.provenance.note,
        })
        return item

    def register_generalization_assessment(
        self,
        *,
        matrix_id: str,
        assessment_id: str,
        generalization_spec_id: str,
        source_claim_id: str,
        source_result_id: str,
        source_population: dict,
        target_population: dict,
        source_context: dict,
        target_context: dict,
        dataset_manifest_id: str,
        source_estimate: float | None,
        transported_estimate: float | None,
        transport_error: float | None,
        dimensions: dict[str, str] | None = None,
        max_transport_error: float = 0.20,
        max_heterogeneity: float | None = None,
        heterogeneity_statistic: float | None = None,
    ) -> GeneralizationAssessmentRecord:
        matrix = self.matrices.get(matrix_id)
        source = self.registry.nodes.get(source_result_id)
        if matrix is None or source is None or source.node_type != "RESULT":
            raise ValueError("matrix and source RESULT must be registered")
        if assessment_id in self.generalization_assessments:
            raise ValueError("generalization assessment already registered")
        spec = register_generalization_spec(
            generalization_spec_id, source_claim_id,
            source_population=source_population, target_population=target_population,
            source_context=source_context, target_context=target_context,
        )
        run = register_generalization_run(
            f"{assessment_id}:run", spec,
            source_result_node_id=source_result_id,
            dataset_manifest_id=dataset_manifest_id,
            transport_analysis_version="1.5",
            input_hash=content_hash({"assessment_id": assessment_id, "dataset_manifest_id": dataset_manifest_id}),
        )
        outcome = evaluate_generalization(
            run,
            source_estimate=source_estimate, transported_estimate=transported_estimate,
            transport_error=transport_error,
            dimensions=dimensions,
            max_transport_error=max_transport_error,
            max_heterogeneity=max_heterogeneity,
            heterogeneity_statistic=heterogeneity_statistic,
        )
        node_id = f"{assessment_id}:run"
        self.registry.add_node(register_node(
            node_id, "GENERALIZATION", node_id, "EXP", "1.5",
            {"kind":"SCIENCE_LAB_GENERALIZATION_RUN","matrix_id":matrix_id,
             "source_result_id":source_result_id,"run_status":"REGISTERED",
             "target_context":target_context},
        ))
        self.registry.add_edge(register_edge(
            f"{node_id}:generalizes:{source_result_id}",
            self.registry.nodes[node_id], source, "GENERALIZES",
            rationale="Science Lab generalization run",
        ))
        item = GeneralizationAssessmentRecord(
            assessment_id, matrix_id, node_id, source_result_id,
            outcome.result_status, outcome.rationale, outcome.provenance,
        )
        self.generalization_assessments[assessment_id] = item
        self._put("science_lab.generalization", assessment_id, {
            **asdict(item),
            "provenance_tag": item.provenance.tag.value,
            "source": item.provenance.source_id,
            "version": item.provenance.source_version,
            "provenance_input_hash": item.provenance.input_hash,
            "provenance_note": item.provenance.note,
        })
        return item

    def claim_validation(self, matrix_id: str) -> dict:
        matrix = self.matrices.get(matrix_id)
        if matrix is None:
            raise ValueError("experiment matrix is not registered")
        claims = []
        for node in self.registry.nodes.values():
            if node.node_type != "CLAIM":
                continue
            if node.metadata.get("execution_id") and node.metadata.get("execution_id").startswith(tuple(
                run.execution_id for run in self.runs.values() if run.matrix_id == matrix_id
            )):
                claims.append({
                    "claim_id": node.node_id,
                    "state": node.metadata.get("state"),
                    "result_id": node.metadata.get("result_id"),
                    "requirements": sorted(self.registry.claim_requirements(
                        node.metadata.get("result_id")
                    )) if node.metadata.get("result_id") in self.registry.nodes else [],
                })
        return {"matrix_id": matrix_id, "claims": claims,
                "scientific_status": "IMPLEMENTATION_BASELINE"}

    def report_bundle(self, matrix_id: str) -> dict:
        matrix = self.matrices.get(matrix_id)
        if matrix is None:
            raise ValueError("experiment matrix is not registered")
        runs = [asdict(r) for r in self.runs.values() if r.matrix_id == matrix_id]
        replications = [asdict(r) for r in self.replication_assessments.values() if r.matrix_id == matrix_id]
        generalizations = [asdict(r) for r in self.generalization_assessments.values() if r.matrix_id == matrix_id]
        claims = self.claim_validation(matrix_id)
        payload = {
            "matrix": asdict(matrix),
            "scenarios": [asdict(self.scenarios[x]) for x in matrix.scenario_ids],
            "scenario_runs": runs,
            "replication_assessments": replications,
            "generalization_assessments": generalizations,
            "claim_validation": claims,
        }
        return {
            **payload,
            "provenance": {
                "version": VERSION,
                "tag": "EXP",
                "input_hash": content_hash(payload),
                "scientific_status": "IMPLEMENTATION_BASELINE",
            },
        }
