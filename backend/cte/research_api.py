"""FastAPI adapter for Research Execution V1.2."""

from __future__ import annotations

from dataclasses import asdict
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Any

from .evidence_graph import register_edge, register_node
from .graph_registry import GraphRegistry
from .persistence import SQLiteRuntimeStore
from .reporting import SECTION_CODES, ReportService, register_spec as register_report_spec
from .research_execution import ResearchService
from .research_e2e import ResearchE2ECoordinator

class StudyInput(BaseModel):
    study_id: str
    study_code: str
    title: str
    research_question: str
    hypothesis_ids: list[str] = Field(default_factory=list)
    design_type: str
    protocol_version: str
    preregistration_ref: str | None = None
    population_definition: dict = Field(default_factory=dict)
    inclusion_criteria: dict = Field(default_factory=dict)
    exclusion_criteria: dict = Field(default_factory=dict)
    primary_outcomes: list[str]
    secondary_outcomes: list[str] = Field(default_factory=list)
    status: str = "REGISTERED"

class ProtocolInput(BaseModel):
    protocol_id: str
    version: str
    design: dict = Field(default_factory=dict)
    measurement_schedule: dict = Field(default_factory=dict)
    analysis_plan: dict = Field(default_factory=dict)
    preregistration_ref: str | None = None

class ExperimentInput(BaseModel):
    experiment_id: str
    experiment_code: str
    intervention_spec: dict = Field(default_factory=dict)
    comparator_spec: dict | None = None
    randomization_spec: dict | None = None
    blinding_spec: dict | None = None
    duration_days: int | None = Field(None, ge=1)
    measurement_schedule: dict = Field(default_factory=dict)
    analysis_plan: dict = Field(default_factory=dict)
    seed: int | None = None
    software_version: str
    protocol_id: str

class ArmInput(BaseModel):
    arm_id: str
    arm_code: str
    arm_type: str
    intervention: dict | None = None
    target_level: str | None = None
    sample_target: int | None = Field(None, ge=0)

class ParticipantInput(BaseModel):
    participant_id: str
    external_participant_code: str
    eligibility_status: str
    consent_status: str
    enrollment_date: str | None = None
    withdrawal_date: str | None = None
    demographic_snapshot: dict | None = None
    baseline_snapshot_id: str | None = None

class AssignmentInput(BaseModel):
    assignment_id: str
    participant_id: str
    arm_id: str
    assignment_method: str
    randomization_seed: int | None = None
    status: str = "ACTIVE"

class TrialInput(BaseModel):
    trial_id: str
    participant_id: str
    arm_id: str | None = None
    trial_number: int
    trial_time: str
    task_id: str
    condition: dict = Field(default_factory=dict)
    stimulus: dict | None = None
    response: dict | None = None
    outcome: dict | None = None
    duration_ms: int | None = Field(None, ge=0)
    validity_status: str = "PENDING"
    raw_payload: dict | None = None

class QCInput(BaseModel):
    qc_run_id: str
    qc_version: str = "1.2.0"

class AnalysisInput(BaseModel):
    analysis_run_id: str
    qc_run_id: str
    dataset_manifest_id: str
    analysis_version: str
    statistical_plan: dict = Field(default_factory=dict)
    dataset_definition: dict = Field(default_factory=dict)
    model_specification: dict = Field(default_factory=dict)
    random_seed: int | None = None

class ManifestInput(BaseModel):
    dataset_manifest_id: str
    dataset_version: str = "1.0"

class ClaimInput(BaseModel):
    claim_id: str
    current_state: str = "REGISTERED"
    target_state: str = "DESCRIPTIVE_RESULT"
    provenance_class: str = "EXP"
    metadata: dict = Field(default_factory=dict)
    previous_claim_id: str | None = None

class ReplicateInput(BaseModel):
    replication_id: str
    independent: bool = True
    criteria_registered: bool = True
    status: str = "REGISTERED"

class GeneralizeInput(BaseModel):
    generalization_id: str
    run_status: str = "REGISTERED"
    target_population_context: str

class ResearchE2EInput(BaseModel):
    execution_id: str
    correlation_id: str
    study: dict[str, Any]
    protocol: dict[str, Any]
    experiment: dict[str, Any]
    arm: dict[str, Any]
    participant: dict[str, Any]
    assignment: dict[str, Any]
    trial: dict[str, Any]
    observations: list[dict[str, Any]]
    requested_trait: str | None = None
    blockers: dict[str, float] = Field(default_factory=dict)
    recovery_indices: list[float | None] = Field(default_factory=list)

def install_research_api(app: FastAPI, registry: GraphRegistry, store: SQLiteRuntimeStore, orchestrator=None):
    service=ResearchService(registry,store)
    report_service=ReportService(registry,store)
    e2e=ResearchE2ECoordinator(orchestrator,service,registry) if orchestrator is not None else None
    report_spec_id="research-v1.2-report"
    if report_spec_id not in report_service.specs:
        report_service.register_spec(register_report_spec(report_spec_id,"Research Execution V1.2 Report","1.2"))

    @app.post("/research/e2e")
    def research_e2e(p: ResearchE2EInput):
        if e2e is None:
            raise ValueError("research E2E coordinator is not installed")
        return e2e.run(**p.model_dump())

    @app.post("/research/studies")
    def research_study(p: StudyInput):
        return asdict(service.register_study(**p.model_dump()))

    @app.post("/research/studies/{study_id}/protocol")
    def research_protocol(study_id: str,p: ProtocolInput):
        return asdict(service.register_protocol(study_id=study_id,**p.model_dump()))

    @app.post("/research/studies/{study_id}/experiments")
    def research_experiment(study_id: str,p: ExperimentInput):
        return asdict(service.create_experiment(study_id=study_id,**p.model_dump()))

    @app.post("/research/experiments/{experiment_id}/arms")
    def research_arm(experiment_id: str,p: ArmInput):
        return asdict(service.register_arm(experiment_id=experiment_id,**p.model_dump()))

    @app.post("/research/studies/{study_id}/participants")
    def research_participant(study_id: str,p: ParticipantInput):
        return asdict(service.enroll_participant(study_id=study_id,**p.model_dump()))

    @app.post("/research/participants/{participant_id}/assign")
    def research_assignment(participant_id: str,p: AssignmentInput):
        if p.participant_id != participant_id:
            raise ValueError("path and payload participant_id mismatch")
        return asdict(service.assign_participant(**p.model_dump()))

    @app.post("/research/experiments/{experiment_id}/trials")
    def research_trial(experiment_id: str,p: TrialInput):
        return asdict(service.ingest_trial(experiment_id=experiment_id,**p.model_dump()))

    @app.post("/research/experiments/{experiment_id}/qc")
    def research_qc(experiment_id: str,p: QCInput):
        return asdict(service.run_qc(qc_run_id=p.qc_run_id,study_id=service.experiments[experiment_id].study_id,
                                     experiment_id=experiment_id,qc_version=p.qc_version))

    @app.post("/research/experiments/{experiment_id}/manifest")
    def research_manifest(experiment_id: str,p: ManifestInput):
        return asdict(service.create_manifest(dataset_manifest_id=p.dataset_manifest_id,
                                               experiment_id=experiment_id,dataset_version=p.dataset_version))

    @app.post("/research/experiments/{experiment_id}/analysis")
    def research_analysis(experiment_id: str,p: AnalysisInput):
        study_id=service.experiments[experiment_id].study_id
        analysis,results=service.run_analysis(
            analysis_run_id=p.analysis_run_id,study_id=study_id,experiment_id=experiment_id,
            qc_run_id=p.qc_run_id,dataset_manifest_id=p.dataset_manifest_id,
            analysis_version=p.analysis_version,statistical_plan=p.statistical_plan,
            dataset_definition=p.dataset_definition,model_specification=p.model_specification,
            random_seed=p.random_seed
        )
        return {"analysis":asdict(analysis),"results":[asdict(x) for x in results]}

    @app.get("/research/analysis/{analysis_run_id}/results")
    def research_results(analysis_run_id: str):
        if analysis_run_id not in service.analyses:
            raise ValueError("analysis run is not registered")
        return {"analysis_id":analysis_run_id,
                "results":[asdict(x) for x in service.results.values() if x.analysis_run_id==analysis_run_id]}

    @app.post("/research/analysis/{analysis_run_id}/claim")
    def research_claim(analysis_run_id: str,p: ClaimInput):
        analysis=service.analyses.get(analysis_run_id)
        if analysis is None or analysis.status!="COMPLETED":
            raise ValueError("analysis run must be completed")
        results=[x for x in service.results.values() if x.analysis_run_id==analysis_run_id]
        if not results:
            raise ValueError("analysis has no statistical results")
        result_id=results[0].result_id
        claim=registry.register_claim(
            p.claim_id,result_id,p.current_state,p.target_state,p.provenance_class,
            p.metadata,p.previous_claim_id
        )
        return {"claim":asdict(claim),"result_id":result_id}

    @app.post("/research/claims/{claim_id}/replicate")
    def research_replicate(claim_id: str,p: ReplicateInput):
        claim=registry.nodes.get(claim_id)
        if claim is None or claim.node_type!="CLAIM":
            raise ValueError("claim is not registered")
        result_id=claim.metadata.get("result_id")
        if not result_id or result_id not in registry.nodes:
            raise ValueError("claim has no registered result")
        node=register_node(
            p.replication_id,"REPLICATION",p.replication_id,"EXP","1.2",
            {"source_claim_id":claim_id,"source_result_id":result_id,
             "independent":p.independent,"criteria_registered":p.criteria_registered,
             "assessment_status":p.status}
        )
        registry.add_node(node)
        registry.add_edge(register_edge(
            f"{p.replication_id}:replicates:{result_id}",node,registry.nodes[result_id],
            "REPLICATES",rationale="research V1.2 replication registration"
        ))
        return {"replication":asdict(node),"claim_id":claim_id}

    @app.post("/research/analysis/{analysis_run_id}/generalize")
    def research_generalize(analysis_run_id: str,p: GeneralizeInput):
        analysis=service.analyses.get(analysis_run_id)
        if analysis is None or analysis.status!="COMPLETED":
            raise ValueError("analysis run must be completed")
        result_ids=[x.result_id for x in service.results.values() if x.analysis_run_id==analysis_run_id]
        if not result_ids:
            raise ValueError("analysis has no result")
        node=register_node(
            p.generalization_id,"GENERALIZATION",p.generalization_id,"EXP","1.2",
            {"source_result_id":result_ids[0],"run_status":p.run_status,
             "target_population_context":p.target_population_context}
        )
        registry.add_node(node)
        registry.add_edge(register_edge(
            f"{p.generalization_id}:generalizes:{result_ids[0]}",node,registry.nodes[result_ids[0]],
            "GENERALIZES",rationale="research V1.2 generalization registration"
        ))
        return {"generalization":asdict(node),"analysis_id":analysis_run_id}

    @app.post("/research/studies/{study_id}/report")
    def research_report(study_id: str):
        study=service._require_study(study_id)
        artifact_ids=[study_id]
        artifact_ids.extend(e.experiment_id for e in service.experiments.values() if e.study_id==study_id)
        artifact_ids.extend(p.participant_id for p in service.participants.values() if p.study_id==study_id)
        artifact_ids.extend(q.qc_run_id for q in service.qc_runs.values() if q.study_id==study_id)
        artifact_ids.extend(a.analysis_run_id for a in service.analyses.values() if a.study_id==study_id)
        artifact_ids=[x for x in artifact_ids if x in registry.nodes]
        run=report_service.create(
            f"{study_id}:report",report_spec_id,study_id,artifact_ids
        )
        section_payload={
            "EXECUTIVE_SUMMARY":{"study":asdict(study)},
            "RESEARCH_QUESTION_HYPOTHESES":{"question":study.research_question,"hypotheses":list(study.hypothesis_ids)},
            "MEASUREMENT_SPECIFICATION":{"primary_outcomes":list(study.primary_outcomes)},
            "STUDY_DESIGN_PARTICIPANTS":{"design":study.design_type},
            "DATA_QUALITY_QC":{"qc_runs":[asdict(x) for x in service.qc_runs.values() if x.study_id==study_id]},
            "STATISTICAL_ANALYSIS":{"analyses":[asdict(x) for x in service.analyses.values() if x.study_id==study_id]},
            "RESULTS_UNCERTAINTY":{"results":[asdict(x) for x in service.results.values() if x.analysis_run_id in service.analyses and service.analyses[x.analysis_run_id].study_id==study_id]},
            "REPLICATION":{"replications":[asdict(n) for n in registry.nodes.values() if n.node_type=="REPLICATION"]},
            "GENERALIZATION_TRANSPORT":{"generalizations":[asdict(n) for n in registry.nodes.values() if n.node_type=="GENERALIZATION"]},
            "EVIDENCE_CLAIM_GRAPH":{"claims":[asdict(n) for n in registry.nodes.values() if n.node_type=="CLAIM"]},
            "CLAIM_STATUS":{"claims":[asdict(n) for n in registry.nodes.values() if n.node_type=="CLAIM"]},
            "LIMITATIONS_BOUNDARIES":{"limitations":["Research runtime is an implementation baseline; empirical validation is not implied."]},
            "PROVENANCE_MANIFEST":service.study_provenance(study_id),
            "REPRODUCIBILITY_METADATA":{"runtime_version":VERSION}
        }
        for i,code in enumerate(SECTION_CODES):
            report_service.add_section(
                run.report_run_id,code,section_payload.get(code,{}),artifact_ids[:min(1,len(artifact_ids))],i
            )
        qc=report_service.qc_run(run.report_run_id)
        if qc["status"]=="QC_PASSED":
            report_service.publish(run.report_run_id)
        return {"report":asdict(report_service.runs[run.report_run_id]),"qc":qc}

    @app.get("/research/studies/{study_id}/provenance")
    def research_provenance(study_id: str):
        return service.study_provenance(study_id)

    return service
