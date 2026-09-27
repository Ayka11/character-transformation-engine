"""V2.2 execution coordinator for the research path.

This coordinator intentionally composes the existing runtime services rather
than re-implementing their rules. It creates one execution envelope and records
stage-level hashes/provenance for the Research Execution V1.2 pipeline.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .assessment import build_profile
from .evidence_graph import register_node
from .state_engine import derive_daily_state
from .capacity import compute_capacity
from .graph_registry import GraphRegistry
from .intervention import plan_21_day_sprint
from .models import DailyState
from .orchestrator import LIFECYCLE, OrchestratorService
from .provenance import content_hash
from .recovery import evaluate_recovery_gate
from .research_execution import ResearchService


E2E_REQUIRED_STAGES = (
    "INTAKE","PROFILE","ASSESSMENT","STATE_ESTIMATION","CAPACITY",
    "RULE_ELIGIBILITY","SAFETY_GATE","MEASUREMENT","QC","ANALYSIS","CLAIM","AUDIT",
)


class ResearchE2ECoordinator:
    def __init__(self, orchestrator: OrchestratorService, research: ResearchService,
                 registry: GraphRegistry):
        self.orchestrator=orchestrator
        self.research=research
        self.registry=registry

    def run(self, *,
            execution_id: str,
            correlation_id: str,
            study: dict[str, Any],
            protocol: dict[str, Any],
            experiment: dict[str, Any],
            arm: dict[str, Any],
            participant: dict[str, Any],
            assignment: dict[str, Any],
            trial: dict[str, Any],
            observations: list[dict[str, Any]],
            requested_trait: str | None = None,
            blockers: dict[str, float] | None = None,
            recovery_indices: list[float | None] | None = None) -> dict[str, Any]:
        if not observations:
            raise ValueError("E2E execution requires assessment observations")
        execution=self.orchestrator.create_execution(
            execution_id,correlation_id,
            {"study":study,"protocol":protocol,"experiment":experiment,
             "participant":participant,"trial":trial,"observations":observations},
            required_stages=list(E2E_REQUIRED_STAGES)
        )
        self.orchestrator.start(execution_id)

        def stage(name: str, payload: Any, *, metadata: dict | None = None):
            in_hash=content_hash(payload)
            out_hash=content_hash({"stage":name,"payload":payload})
            self.orchestrator.advance_stage(
                execution_id,name,"PASSED",input_hash=in_hash,output_hash=out_hash,
                module_version="2.2",provenance_record_id=f"{execution_id}:{name}",
                metadata=metadata or {}
            )
            return out_hash

        stage("INTAKE",{"study_id":study.get("study_id"),"execution_id":execution_id})

        profile=build_profile(
            observations,
            source_id=f"research-e2e:{execution_id}:assessment",
            source_version="2.2",
        )
        profile_payload={"measurements":[asdict(m) for m in profile.measurements]}
        profile_hash=stage("PROFILE",profile_payload)

        for measurement in profile.measurements:
            self.registry.add_node(register_node(
                measurement.measurement_id,"MEASUREMENT",measurement.measurement_id,
                measurement.provenance.tag.value,measurement.provenance.source_version,
                {"item_id":measurement.item_id,"value":measurement.value,
                 "execution_id":execution_id}
            ))
        stage("ASSESSMENT",profile_payload,metadata={"measurement_count":len(profile.measurements)})

        state_result=derive_daily_state(profile)
        state_payload={"state":asdict(state_result.state),"missing":list(state_result.missing)}
        stage("STATE_ESTIMATION",state_payload,metadata={"missing":list(state_result.missing)})

        capacity=compute_capacity(state_result.state)
        capacity_payload=asdict(capacity)
        stage("CAPACITY",capacity_payload,metadata={"safety_block":capacity.safety_block})

        eligibility={
            "requested_trait":requested_trait,
            "blockers":blockers or {},
            "profile_hash":profile_hash,
        }
        stage("RULE_ELIGIBILITY",eligibility)

        recovery=evaluate_recovery_gate(state_result.state)
        safety_payload=asdict(recovery)
        if recovery.safety_block:
            self.orchestrator.advance_stage(
                execution_id,"SAFETY_GATE","BLOCKED",
                input_hash=content_hash(recovery),
                output_hash=content_hash(safety_payload),
                module_version="1.0",
                provenance_record_id=f"{execution_id}:SAFETY_GATE",
                reason="Level A recovery/safety condition is active",
                metadata={"safety_status":"BLOCK","level":recovery.level}
            )
            return {
                "execution":asdict(self.orchestrator.executions[execution_id]),
                "status":"BLOCKED",
                "safety_gate":safety_payload,
                "research":None,
            }
        stage("SAFETY_GATE",safety_payload,metadata={"safety_status":"PASS","level":recovery.level})

        if requested_trait and blockers is not None:
            # Planning only: no intervention is executed by this coordinator.
            from .trait_graph import TraitGraph
            graph=TraitGraph({
                requested_trait:list(blockers.keys())
            })
            plan=plan_21_day_sprint(
                state_result.state,requested_trait,graph,blockers,
                "consistent recovery routine","one deliberate pause before a response"
            )
            intervention_payload=asdict(plan)
        else:
            intervention_payload={"status":"NOT_REQUESTED"}
        stage("MEASUREMENT",{"recovery":recovery.inputs,
                              "observations":observations,
                              "recovery_indices":recovery_indices or []})

        study_obj=self.research.register_study(**study)
        protocol_obj=self.research.register_protocol(study_id=study_obj.study_id,**protocol)
        experiment_obj=self.research.create_experiment(
            study_id=study_obj.study_id,protocol_id=protocol_obj.protocol_id,**experiment
        )
        arm_obj=self.research.register_arm(experiment_id=experiment_obj.experiment_id,**arm)
        participant_obj=self.research.enroll_participant(
            study_id=study_obj.study_id,**participant
        )
        assignment_payload=dict(assignment)
        if assignment_payload.get("participant_id") != participant_obj.participant_id:
            raise ValueError("assignment participant_id does not match enrolled participant")
        assignment_obj=self.research.assign_participant(**assignment_payload)
        trial_obj=self.research.ingest_trial(
            experiment_id=experiment_obj.experiment_id,**trial
        )

        qc=self.research.run_qc(
            qc_run_id=f"{execution_id}:qc",
            study_id=study_obj.study_id,
            experiment_id=experiment_obj.experiment_id
        )
        qc_payload=asdict(qc)
        if not qc.passed:
            self.orchestrator.advance_stage(
                execution_id,"QC","BLOCKED",
                input_hash=qc.input_hash,output_hash=qc.output_hash,
                module_version="1.2",provenance_record_id=qc.qc_run_id,
                reason="Research QC failed; analysis cannot proceed",
                metadata={"qc_status":"FAIL"}
            )
            return {"execution":asdict(self.orchestrator.executions[execution_id]),
                    "status":"BLOCKED","safety_gate":safety_payload,
                    "research":{"study":asdict(study_obj),"qc":qc_payload}}
        stage("QC",qc_payload,metadata={"passed":True})

        manifest=self.research.create_manifest(
            dataset_manifest_id=f"{execution_id}:manifest",
            experiment_id=experiment_obj.experiment_id,
            dataset_version="1.0"
        )
        analysis,results=self.research.run_analysis(
            analysis_run_id=f"{execution_id}:analysis",
            study_id=study_obj.study_id,
            experiment_id=experiment_obj.experiment_id,
            qc_run_id=qc.qc_run_id,
            dataset_manifest_id=manifest.dataset_manifest_id,
            analysis_version="1.2.0",
            statistical_plan=experiment_obj.analysis_plan,
            dataset_definition={"filter":"VALID"},
            model_specification={"estimator":"MEAN"},
            random_seed=experiment_obj.seed
        )
        analysis_payload=asdict(analysis)
        stage("ANALYSIS",analysis_payload,metadata={"result_count":len(results)})

        claim=None
        if results:
            claim=self.registry.register_claim(
                f"{execution_id}:claim",results[0].result_id,
                "REGISTERED","DESCRIPTIVE_RESULT","EXP",
                {"execution_id":execution_id,"research_analysis_id":analysis.analysis_run_id}
            )
            stage("CLAIM",asdict(claim),metadata={"claim_state":"DESCRIPTIVE_RESULT","claim_gate_passed":True})
        else:
            self.orchestrator.advance_stage(
                execution_id,"CLAIM","SKIPPED",
                reason="No estimable research result was produced",
                metadata={"claim_state":"NOT_ESTIMABLE"}
            )

        audit_payload={
            "execution_id":execution_id,
            "research_study_id":study_obj.study_id,
            "protocol_id":protocol_obj.protocol_id,
            "experiment_id":experiment_obj.experiment_id,
            "participant_id":participant_obj.participant_id,
            "assignment_id":assignment_obj.assignment_id,
            "trial_id":trial_obj.trial_id,
            "qc_run_id":qc.qc_run_id,
            "dataset_manifest_id":manifest.dataset_manifest_id,
            "analysis_run_id":analysis.analysis_run_id,
            "result_ids":[r.result_id for r in results],
            "claim_id":claim.node_id if claim else None,
        }
        stage("AUDIT",audit_payload)

        completed=self.orchestrator.complete(execution_id)
        return {
            "execution":asdict(completed),
            "status":"COMPLETED",
            "safety_gate":safety_payload,
            "intervention_plan":intervention_payload,
            "research":{
                "study":asdict(study_obj),
                "protocol":asdict(protocol_obj),
                "experiment":asdict(experiment_obj),
                "arm":asdict(arm_obj),
                "participant":asdict(participant_obj),
                "assignment":asdict(assignment_obj),
                "trial":asdict(trial_obj),
                "qc":qc_payload,
                "manifest":asdict(manifest),
                "analysis":analysis_payload,
                "results":[asdict(r) for r in results],
                "claim":asdict(claim) if claim else None,
            },
            "provenance":self.orchestrator.provenance(execution_id),
        }
