"""Research Execution V1.2 runtime.

Implements the repository's registered research pipeline:
QUESTION -> HYPOTHESIS -> STUDY -> PROTOCOL -> PARTICIPANT_ENROLLMENT ->
EXPERIMENT -> ARM_ASSIGNMENT -> TRIAL_DATA -> QC -> ANALYSIS -> RESULT.

The runtime is deterministic by default, provenance-aware, and conservative:
raw trial observations remain separate from derived results; QC must pass before
analysis; a dataset manifest is immutable and every analysis references it.
This is an implementation baseline, not empirical validation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from .evidence_graph import register_edge, register_node
from .graph_registry import GraphRegistry
from .persistence import SQLiteRuntimeStore
from .provenance import Provenance, ProvenanceTag, content_hash
from .result_node import build_result, graph_node

VERSION = "1.2.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _prov(source: str, payload: Any, tag: str = "EXP") -> Provenance:
    return Provenance(
        ProvenanceTag(tag),
        source,
        VERSION,
        content_hash(payload),
        "Research execution runtime; not empirical validation",
    )


@dataclass(frozen=True)
class ResearchProtocol:
    protocol_id: str
    study_id: str
    version: str
    design: dict
    measurement_schedule: dict
    analysis_plan: dict
    preregistration_ref: str | None
    provenance: Provenance
    immutable_hash: str


@dataclass
class Study:
    study_id: str
    study_code: str
    title: str
    research_question: str
    hypothesis_ids: tuple[str, ...]
    design_type: str
    protocol_version: str
    preregistration_ref: str | None
    population_definition: dict
    inclusion_criteria: dict
    exclusion_criteria: dict
    primary_outcomes: tuple[str, ...]
    secondary_outcomes: tuple[str, ...]
    status: str
    protocol_id: str
    created_at: str
    immutable_hash: str


@dataclass
class Experiment:
    experiment_id: str
    study_id: str
    experiment_code: str
    intervention_spec: dict
    comparator_spec: dict | None
    randomization_spec: dict | None
    blinding_spec: dict | None
    duration_days: int | None
    measurement_schedule: dict
    analysis_plan: dict
    seed: int | None
    software_version: str
    status: str
    protocol_id: str
    immutable_hash: str


@dataclass(frozen=True)
class ExperimentArm:
    arm_id: str
    experiment_id: str
    arm_code: str
    arm_type: str
    intervention: dict | None
    target_level: str | None
    sample_target: int | None
    immutable_hash: str


@dataclass
class Participant:
    participant_id: str
    study_id: str
    external_participant_code: str
    eligibility_status: str
    consent_status: str
    enrollment_date: str | None
    withdrawal_date: str | None
    demographic_snapshot: dict | None
    baseline_snapshot_id: str | None
    immutable_hash: str


@dataclass(frozen=True)
class Assignment:
    assignment_id: str
    participant_id: str
    arm_id: str
    assigned_at: str
    assignment_method: str
    randomization_seed: int | None
    status: str
    immutable_hash: str


@dataclass(frozen=True)
class Trial:
    trial_id: str
    experiment_id: str
    participant_id: str
    arm_id: str | None
    trial_number: int
    trial_time: str
    task_id: str
    condition: dict
    stimulus: dict | None
    response: dict | None
    outcome: dict | None
    duration_ms: int | None
    validity_status: str
    raw_payload: dict | None
    trial_hash: str


@dataclass(frozen=True)
class DatasetManifest:
    dataset_manifest_id: str
    experiment_id: str
    dataset_version: str
    trial_ids: tuple[str, ...]
    row_count: int
    variable_schema: dict
    inclusion_filter: str
    exclusion_filter: str
    checksum: str
    created_at: str


@dataclass(frozen=True)
class QCRun:
    qc_run_id: str
    study_id: str
    experiment_id: str
    qc_version: str
    checks: dict
    exclusions: tuple[str, ...]
    warnings: tuple[str, ...]
    passed: bool
    input_hash: str
    output_hash: str
    executed_at: str


@dataclass
class AnalysisRun:
    analysis_run_id: str
    study_id: str
    experiment_id: str
    qc_run_id: str
    dataset_manifest_id: str
    analysis_version: str
    statistical_plan: dict
    dataset_definition: dict
    model_specification: dict
    random_seed: int | None
    input_hash: str
    output_hash: str | None
    status: str


@dataclass(frozen=True)
class StatisticalResult:
    result_id: str
    analysis_run_id: str
    outcome_id: str
    estimator: str
    estimate: float | None
    standard_error: float | None
    confidence_interval: dict | None
    p_value: float | None
    effect_size: dict | None
    sample_size: int
    missing_count: int
    multiplicity_adjustment: str | None
    interpretation: str
    result_status: str
    provenance: Provenance


class ResearchService:
    def __init__(self, registry: GraphRegistry, store: SQLiteRuntimeStore | None = None):
        self.registry = registry
        self.store = store
        self.studies: dict[str, Study] = {}
        self.protocols: dict[str, ResearchProtocol] = {}
        self.experiments: dict[str, Experiment] = {}
        self.arms: dict[str, ExperimentArm] = {}
        self.participants: dict[str, Participant] = {}
        self.assignments: dict[str, Assignment] = {}
        self.trials: dict[str, Trial] = {}
        self.manifests: dict[str, DatasetManifest] = {}
        self.qc_runs: dict[str, QCRun] = {}
        self.analyses: dict[str, AnalysisRun] = {}
        self.results: dict[str, StatisticalResult] = {}
        self._hydrate()

    def _snap(self, namespace: str, key: str, payload: dict, version: str = VERSION):
        if self.store is not None:
            return self.store.put_snapshot(namespace, key, payload, version)

    def _hydrate(self):
        if self.store is None:
            return
        for s in self.store.list_snapshots("research.study"):
            p=s.payload
            self.studies[p["study_id"]]=Study(
                p["study_id"],p["study_code"],p["title"],p["research_question"],
                tuple(p["hypothesis_ids"]),p["design_type"],p["protocol_version"],
                p.get("preregistration_ref"),p["population_definition"],
                p["inclusion_criteria"],p["exclusion_criteria"],
                tuple(p["primary_outcomes"]),tuple(p["secondary_outcomes"]),
                p["status"],p["protocol_id"],p["created_at"],p["immutable_hash"])
        for s in self.store.list_snapshots("research.protocol"):
            p=s.payload
            prov=Provenance(ProvenanceTag(p["provenance_tag"]),"research.protocol",p["version"],p["provenance_input_hash"],p["provenance_note"])
            self.protocols[p["protocol_id"]]=ResearchProtocol(p["protocol_id"],p["study_id"],p["version"],p["design"],p["measurement_schedule"],p["analysis_plan"],p.get("preregistration_ref"),prov,p["immutable_hash"])
        for s in self.store.list_snapshots("research.experiment"):
            p=s.payload
            self.experiments[p["experiment_id"]]=Experiment(**p)
        for s in self.store.list_snapshots("research.arm"):
            self.arms[s.key]=ExperimentArm(**s.payload)
        for s in self.store.list_snapshots("research.participant"):
            self.participants[s.key]=Participant(**s.payload)
        for s in self.store.list_snapshots("research.assignment"):
            self.assignments[s.key]=Assignment(**s.payload)
        for s in self.store.list_snapshots("research.trial"):
            self.trials[s.key]=Trial(**s.payload)
        for s in self.store.list_snapshots("research.manifest"):
            p=s.payload
            self.manifests[s.key]=DatasetManifest(
                p["dataset_manifest_id"],p["experiment_id"],p["dataset_version"],
                tuple(p["trial_ids"]),p["row_count"],p["variable_schema"],
                p["inclusion_filter"],p["exclusion_filter"],p["checksum"],p["created_at"])
        for s in self.store.list_snapshots("research.qc"):
            p=s.payload
            self.qc_runs[s.key]=QCRun(
                p["qc_run_id"],p["study_id"],p["experiment_id"],p["qc_version"],
                p["checks"],tuple(p["exclusions"]),tuple(p["warnings"]),p["passed"],
                p["input_hash"],p["output_hash"],p["executed_at"])
        for s in self.store.list_snapshots("research.analysis"):
            p=s.payload
            self.analyses[s.key]=AnalysisRun(**p)
        for s in self.store.list_snapshots("research.result"):
            p=s.payload
            prov=Provenance(ProvenanceTag(p["provenance_tag"]),p["source"],p["version"],p["provenance_input_hash"],p["provenance_note"])
            self.results[s.key]=StatisticalResult(
                p["result_id"],p["analysis_run_id"],p["outcome_id"],p["estimator"],
                p["estimate"],p["standard_error"],p["confidence_interval"],p["p_value"],
                p["effect_size"],p["sample_size"],p["missing_count"],
                p["multiplicity_adjustment"],p["interpretation"],p["result_status"],prov)

    def _require_study(self, study_id: str) -> Study:
        if study_id not in self.studies:
            raise ValueError("study is not registered")
        return self.studies[study_id]

    def register_study(self, *, study_id: str, study_code: str, title: str,
                        research_question: str, hypothesis_ids: list[str],
                        design_type: str, protocol_version: str,
                        preregistration_ref: str | None, population_definition: dict,
                        inclusion_criteria: dict, exclusion_criteria: dict,
                        primary_outcomes: list[str], secondary_outcomes: list[str] | None = None,
                        status: str = "REGISTERED") -> Study:
        if study_id in self.studies:
            raise ValueError("study already registered")
        if status not in {"DRAFT","REGISTERED"}:
            raise ValueError("study must start in DRAFT or REGISTERED")
        if not primary_outcomes:
            raise ValueError("at least one primary outcome is required")
        payload={
            "study_id":study_id,"study_code":study_code,"title":title,
            "research_question":research_question,"hypothesis_ids":list(hypothesis_ids),
            "design_type":design_type,"protocol_version":protocol_version,
            "preregistration_ref":preregistration_ref,
            "population_definition":population_definition,
            "inclusion_criteria":inclusion_criteria,"exclusion_criteria":exclusion_criteria,
            "primary_outcomes":list(primary_outcomes),
            "secondary_outcomes":list(secondary_outcomes or []),
        }
        item=Study(study_id,study_code,title,research_question,tuple(hypothesis_ids),
                   design_type,protocol_version,preregistration_ref,population_definition,
                   inclusion_criteria,exclusion_criteria,tuple(primary_outcomes),
                   tuple(secondary_outcomes or []),status,f"{study_id}:protocol",
                   _now(),content_hash(payload))
        self.studies[study_id]=item
        self._snap("research.study",study_id,{**asdict(item)})
        self.registry.add_node(register_node(study_id,"SOURCE",study_id,"EXP",VERSION,
            {"kind":"STUDY","study_code":study_code,"research_question":research_question,"status":status}))
        return item

    def register_protocol(self, *, protocol_id: str, study_id: str, version: str,
                          design: dict, measurement_schedule: dict, analysis_plan: dict,
                          preregistration_ref: str | None = None) -> ResearchProtocol:
        self._require_study(study_id)
        if protocol_id in self.protocols:
            raise ValueError("protocol already registered")
        payload={"protocol_id":protocol_id,"study_id":study_id,"version":version,
                 "design":design,"measurement_schedule":measurement_schedule,
                 "analysis_plan":analysis_plan,"preregistration_ref":preregistration_ref}
        prov=_prov("research.protocol",payload)
        item=ResearchProtocol(protocol_id,study_id,version,design,measurement_schedule,analysis_plan,preregistration_ref,prov,content_hash(payload))
        self.protocols[protocol_id]=item
        self._snap("research.protocol",protocol_id,{
            **payload,"provenance_tag":prov.tag.value,"provenance_input_hash":prov.input_hash,
            "provenance_note":prov.note,"immutable_hash":item.immutable_hash})
        self.registry.add_node(register_node(protocol_id,"PROTOCOL",protocol_id,"EXP",version,
            {"kind":"RESEARCH_PROTOCOL","study_id":study_id,"design":design,
             "measurement_schedule":measurement_schedule,"analysis_plan":analysis_plan}))
        self.registry.add_edge(register_edge(f"{study_id}:protocol:{protocol_id}",
            self.registry.nodes[study_id],self.registry.nodes[protocol_id],"USES_PROTOCOL",
            rationale="registered research protocol"))
        return item

    def create_experiment(self, *, experiment_id: str, study_id: str,
                          experiment_code: str, intervention_spec: dict,
                          comparator_spec: dict | None, randomization_spec: dict | None,
                          blinding_spec: dict | None, duration_days: int | None,
                          measurement_schedule: dict, analysis_plan: dict,
                          seed: int | None, software_version: str,
                          protocol_id: str) -> Experiment:
        self._require_study(study_id)
        protocol=self.protocols.get(protocol_id)
        if protocol is None or protocol.study_id != study_id:
            raise ValueError("protocol_id must reference a protocol for the study")
        if experiment_id in self.experiments:
            raise ValueError("experiment already registered")
        payload={"experiment_id":experiment_id,"study_id":study_id,"experiment_code":experiment_code,
                 "intervention_spec":intervention_spec,"comparator_spec":comparator_spec,
                 "randomization_spec":randomization_spec,"blinding_spec":blinding_spec,
                 "duration_days":duration_days,"measurement_schedule":measurement_schedule,
                 "analysis_plan":analysis_plan,"seed":seed,"software_version":software_version,
                 "protocol_id":protocol_id}
        item=Experiment(experiment_id,study_id,experiment_code,intervention_spec,comparator_spec,
                        randomization_spec,blinding_spec,duration_days,measurement_schedule,
                        analysis_plan,seed,software_version,"PLANNED",protocol_id,content_hash(payload))
        self.experiments[experiment_id]=item
        self._snap("research.experiment",experiment_id,asdict(item))
        self.registry.add_node(register_node(experiment_id,"SOURCE",experiment_id,"EXP",VERSION,
            {"kind":"EXPERIMENT","study_id":study_id,"protocol_id":protocol_id,"status":"PLANNED"}))
        return item

    def register_arm(self, *, arm_id: str, experiment_id: str, arm_code: str,
                     arm_type: str, intervention: dict | None,
                     target_level: str | None, sample_target: int | None) -> ExperimentArm:
        if experiment_id not in self.experiments:
            raise ValueError("experiment is not registered")
        if arm_type not in {"CONTROL","INTERVENTION","COMPARATOR","OTHER"}:
            raise ValueError("unsupported arm_type")
        if arm_id in self.arms:
            raise ValueError("arm already registered")
        payload={"arm_id":arm_id,"experiment_id":experiment_id,"arm_code":arm_code,
                 "arm_type":arm_type,"intervention":intervention,
                 "target_level":target_level,"sample_target":sample_target}
        item=ExperimentArm(arm_id,experiment_id,arm_code,arm_type,intervention,target_level,sample_target,content_hash(payload))
        self.arms[arm_id]=item
        self._snap("research.arm",arm_id,asdict(item))
        self.registry.add_node(register_node(arm_id,"SOURCE",arm_id,"EXP",VERSION,
            {"kind":"ARM","experiment_id":experiment_id,"arm_type":arm_type,"arm_code":arm_code}))
        return item

    def enroll_participant(self, *, participant_id: str, study_id: str,
                           external_participant_code: str, eligibility_status: str,
                           consent_status: str, enrollment_date: str | None,
                           withdrawal_date: str | None, demographic_snapshot: dict | None,
                           baseline_snapshot_id: str | None) -> Participant:
        self._require_study(study_id)
        if participant_id in self.participants:
            raise ValueError("participant already enrolled")
        if consent_status not in {"PENDING","CONSENTED","WITHDRAWN"}:
            raise ValueError("unsupported consent_status")
        if eligibility_status not in {"PENDING","ELIGIBLE","INELIGIBLE"}:
            raise ValueError("unsupported eligibility_status")
        payload={"participant_id":participant_id,"study_id":study_id,
                 "external_participant_code":external_participant_code,
                 "eligibility_status":eligibility_status,"consent_status":consent_status,
                 "enrollment_date":enrollment_date,"withdrawal_date":withdrawal_date,
                 "demographic_snapshot":demographic_snapshot,
                 "baseline_snapshot_id":baseline_snapshot_id}
        item=Participant(participant_id,study_id,external_participant_code,eligibility_status,
                         consent_status,enrollment_date,withdrawal_date,demographic_snapshot,
                         baseline_snapshot_id,content_hash(payload))
        self.participants[participant_id]=item
        self._snap("research.participant",participant_id,asdict(item))
        self.registry.add_node(register_node(participant_id,"SOURCE",participant_id,"EXP",VERSION,
            {"kind":"PARTICIPANT","study_id":study_id,"eligibility_status":eligibility_status,
             "consent_status":consent_status}))
        return item

    def assign_participant(self, *, assignment_id: str, participant_id: str,
                           arm_id: str, assignment_method: str,
                           randomization_seed: int | None, status: str = "ACTIVE") -> Assignment:
        participant=self.participants.get(participant_id)
        arm=self.arms.get(arm_id)
        if participant is None or arm is None:
            raise ValueError("participant and arm must be registered")
        experiment=self.experiments[arm.experiment_id]
        if participant.study_id != experiment.study_id:
            raise ValueError("participant and arm must belong to the same study")
        if participant.eligibility_status != "ELIGIBLE" or participant.consent_status != "CONSENTED":
            raise ValueError("participant is not eligible/consented")
        if assignment_id in self.assignments:
            raise ValueError("assignment already registered")
        payload={"assignment_id":assignment_id,"participant_id":participant_id,"arm_id":arm_id,
                 "assigned_at":_now(),"assignment_method":assignment_method,
                 "randomization_seed":randomization_seed,"status":status}
        item=Assignment(assignment_id,participant_id,arm_id,payload["assigned_at"],
                        assignment_method,randomization_seed,status,content_hash(payload))
        self.assignments[assignment_id]=item
        self._snap("research.assignment",assignment_id,asdict(item))
        return item

    def ingest_trial(self, *, trial_id: str, experiment_id: str, participant_id: str,
                     arm_id: str | None, trial_number: int, trial_time: str, task_id: str,
                     condition: dict, stimulus: dict | None, response: dict | None,
                     outcome: dict | None, duration_ms: int | None,
                     validity_status: str = "PENDING", raw_payload: dict | None = None) -> Trial:
        experiment=self.experiments.get(experiment_id)
        participant=self.participants.get(participant_id)
        if experiment is None or participant is None:
            raise ValueError("experiment and participant must be registered")
        if participant.study_id != experiment.study_id:
            raise ValueError("participant does not belong to experiment study")
        if arm_id is not None:
            arm=self.arms.get(arm_id)
            if arm is None or arm.experiment_id != experiment_id:
                raise ValueError("arm_id must belong to experiment")
        if trial_id in self.trials:
            raise ValueError("trial already registered")
        if validity_status not in {"PENDING","VALID","INVALID","EXCLUDED"}:
            raise ValueError("unsupported validity_status")
        payload={"trial_id":trial_id,"experiment_id":experiment_id,"participant_id":participant_id,
                 "arm_id":arm_id,"trial_number":trial_number,"trial_time":trial_time,"task_id":task_id,
                 "condition":condition,"stimulus":stimulus,"response":response,"outcome":outcome,
                 "duration_ms":duration_ms,"validity_status":validity_status,"raw_payload":raw_payload}
        trial_hash=content_hash(payload)
        item=Trial(**payload,trial_hash=trial_hash)
        self.trials[trial_id]=item
        self._snap("research.trial",trial_id,asdict(item))
        self.registry.add_node(register_node(trial_id,"OBSERVATION",trial_id,"OBS",VERSION,
            {"kind":"TRIAL","experiment_id":experiment_id,"participant_id":participant_id,
             "arm_id":arm_id,"trial_number":trial_number,"task_id":task_id,"trial_hash":trial_hash}))
        return item

    def run_qc(self, *, qc_run_id: str, study_id: str, experiment_id: str,
               qc_version: str = VERSION) -> QCRun:
        self._require_study(study_id)
        if experiment_id not in self.experiments:
            raise ValueError("experiment is not registered")
        trials=[t for t in self.trials.values() if t.experiment_id==experiment_id]
        if not trials:
            raise ValueError("QC requires at least one trial")
        checks:dict[str,Any]={}
        warnings=[]
        exclusions=[]
        checks["trial_hashes_unique"]=len({t.trial_hash for t in trials})==len(trials)
        pending=[t.trial_id for t in trials if t.validity_status=="PENDING"]
        checks["no_pending_trials"]=not pending
        if pending:
            warnings.append(f"pending trials: {len(pending)}")
        invalid=[t.trial_id for t in trials if t.validity_status in {"INVALID","EXCLUDED"}]
        exclusions.extend(invalid)
        checks["all_participants_registered"]=all(t.participant_id in self.participants for t in trials)
        checks["all_assigned_arms_valid"]=all(
            t.arm_id is None or (t.arm_id in self.arms and self.arms[t.arm_id].experiment_id==experiment_id)
            for t in trials
        )
        passed=all(checks.values()) and bool(trials)
        input_hash=content_hash([asdict(t) for t in sorted(trials,key=lambda x:x.trial_id)])
        output_hash=content_hash({"checks":checks,"exclusions":exclusions,"warnings":warnings})
        item=QCRun(qc_run_id,study_id,experiment_id,qc_version,checks,tuple(exclusions),
                   tuple(warnings),passed,input_hash,output_hash,_now())
        self.qc_runs[qc_run_id]=item
        self._snap("research.qc",qc_run_id,asdict(item))
        self.registry.add_node(register_node(qc_run_id,"ANALYSIS",qc_run_id,"EXP",qc_version,
            {"kind":"RESEARCH_QC","study_id":study_id,"experiment_id":experiment_id,
             "passed":passed,"input_hash":input_hash,"output_hash":output_hash}))
        return item

    def create_manifest(self, *, dataset_manifest_id: str, experiment_id: str,
                        dataset_version: str = "1.0") -> DatasetManifest:
        if dataset_manifest_id in self.manifests:
            raise ValueError("dataset manifest already registered")
        if experiment_id not in self.experiments:
            raise ValueError("experiment is not registered")
        trials=[t for t in self.trials.values() if t.experiment_id==experiment_id and t.validity_status=="VALID"]
        if not trials:
            raise ValueError("dataset manifest requires at least one VALID trial")
        variable_schema={
            "trial_id":"string","participant_id":"string","arm_id":"string|null",
            "trial_number":"integer","task_id":"string","condition":"object",
            "response":"object|null","outcome":"object|null","duration_ms":"integer|null"
        }
        checksum=content_hash([t.trial_hash for t in sorted(trials,key=lambda x:x.trial_id)])
        item=DatasetManifest(dataset_manifest_id,experiment_id,dataset_version,
                             tuple(t.trial_id for t in sorted(trials,key=lambda x:x.trial_id)),
                             len(trials),variable_schema,
                             "validity_status == VALID","validity_status != VALID",checksum,_now())
        self.manifests[dataset_manifest_id]=item
        self._snap("research.manifest",dataset_manifest_id,asdict(item))
        self.registry.add_node(register_node(dataset_manifest_id,"DATASET",dataset_manifest_id,"EXP",dataset_version,
            {"kind":"RESEARCH_DATASET_MANIFEST","experiment_id":experiment_id,
             "row_count":len(trials),"checksum":checksum,"trial_ids":list(item.trial_ids)}))
        for t in trials:
            self.registry.add_edge(register_edge(f"{dataset_manifest_id}:trial:{t.trial_id}",
                self.registry.nodes[t.trial_id],self.registry.nodes[dataset_manifest_id],"MEASURED_FROM",
                rationale="trial included in immutable dataset manifest"))
        return item

    def run_analysis(self, *, analysis_run_id: str, study_id: str, experiment_id: str,
                     qc_run_id: str, dataset_manifest_id: str, analysis_version: str,
                     statistical_plan: dict, dataset_definition: dict,
                     model_specification: dict, random_seed: int | None = None) -> tuple[AnalysisRun, list[StatisticalResult]]:
        if analysis_run_id in self.analyses:
            raise ValueError("analysis run already registered")
        qc=self.qc_runs.get(qc_run_id)
        manifest=self.manifests.get(dataset_manifest_id)
        if qc is None or not qc.passed:
            raise ValueError("analysis requires a PASSED QC run")
        if manifest is None:
            raise ValueError("dataset manifest is not registered")
        if manifest.experiment_id != experiment_id or qc.experiment_id != experiment_id:
            raise ValueError("QC, manifest and experiment must match")
        if analysis_run_id in self.analyses:
            raise ValueError("analysis run already registered")
        trials=[self.trials[t] for t in manifest.trial_ids]
        input_hash=content_hash({"manifest":asdict(manifest),"plan":statistical_plan,"model":model_specification,"seed":random_seed})
        analysis=AnalysisRun(analysis_run_id,study_id,experiment_id,qc_run_id,dataset_manifest_id,
                            analysis_version,statistical_plan,dataset_definition,model_specification,
                            random_seed,input_hash,None,"RUNNING")
        self.analyses[analysis_run_id]=analysis
        self._snap("research.analysis",analysis_run_id,asdict(analysis))
        self.registry.add_node(register_node(analysis_run_id,"ANALYSIS",analysis_run_id,"EXP",analysis_version,
            {"kind":"RESEARCH_ANALYSIS","study_id":study_id,"experiment_id":experiment_id,
             "qc_run_id":qc_run_id,"dataset_manifest_id":dataset_manifest_id,
             "analysis_version":analysis_version,"random_seed":random_seed}))
        self.registry.add_edge(register_edge(f"{analysis_run_id}:manifest:{dataset_manifest_id}",
            self.registry.nodes[analysis_run_id],self.registry.nodes[dataset_manifest_id],"ANALYZED_FROM",
            rationale="analysis references immutable dataset manifest"))
        values_by_arm:dict[str,list[float]]={}
        for t in trials:
            if not t.outcome or "value" not in t.outcome or not isinstance(t.outcome["value"],(int,float)):
                continue
            key=t.arm_id or "UNASSIGNED"
            values_by_arm.setdefault(key,[]).append(float(t.outcome["value"]))
        results=[]
        for outcome_id in self._outcome_ids(trials):
            values=[]
            for t in trials:
                if t.outcome and outcome_id in t.outcome and isinstance(t.outcome[outcome_id],(int,float)):
                    values.append(float(t.outcome[outcome_id]))
            estimate=mean(values) if values else None
            result_id=f"{analysis_run_id}:result:{outcome_id}"
            prov=_prov("research.analysis.result",{"analysis_run_id":analysis_run_id,"outcome_id":outcome_id,"values":values})
            result=StatisticalResult(result_id,analysis_run_id,outcome_id,"MEAN",estimate,None,None,None,
                                     {"type":"DESCRIPTIVE_MEAN"} if estimate is not None else None,
                                     len(values),len(trials)-len(values),None,
                                     "Descriptive mean across valid trial observations" if estimate is not None else "Not estimable from numeric observations",
                                     "ESTIMABLE" if estimate is not None else "NOT_ESTIMABLE",prov)
            self.results[result_id]=result
            self._snap("research.result",result_id,{
                **asdict(result),"provenance_tag":prov.tag.value,"source":prov.source_id,
                "version":prov.source_version,"provenance_input_hash":prov.input_hash,"provenance_note":prov.note})
            node=build_result(result_id=result_id,analysis_id=analysis_run_id,manifest_id=dataset_manifest_id,
                              analysis_spec_id=analysis_version,qc_status="PASS" if result.result_status=="ESTIMABLE" else "NOT_ESTIMABLE",
                              n=result.sample_size,estimate=result.estimate,ci95_low=None,ci95_high=None)
            self.registry.add_node(register_node(result_id,"RESULT",result_id,"EXP",analysis_version,graph_node(node)["metadata_json"]))
            self.registry.add_edge(register_edge(f"{analysis_run_id}:result:{result_id}",
                self.registry.nodes[analysis_run_id],self.registry.nodes[result_id],"RESULTS_IN",
                rationale="research statistical result"))
            results.append(result)
        analysis.status="COMPLETED"
        analysis.output_hash=content_hash([asdict(r) for r in results])
        self._snap("research.analysis",analysis_run_id,asdict(analysis))
        return analysis,results

    @staticmethod
    def _outcome_ids(trials: list[Trial]) -> list[str]:
        ids=set()
        for t in trials:
            ids.update((t.outcome or {}).keys())
        return sorted(ids)

    def study_provenance(self, study_id: str) -> dict:
        self._require_study(study_id)
        node_ids={study_id}
        for collection in (self.protocols,self.experiments,self.arms,self.participants,self.trials,self.qc_runs,self.analyses,self.results):
            for obj in collection.values():
                data=asdict(obj)
                if data.get("study_id")==study_id or data.get("experiment_id") in {e.experiment_id for e in self.experiments.values() if e.study_id==study_id}:
                    for key in ("protocol_id","experiment_id","arm_id","participant_id","qc_run_id","analysis_run_id","result_id"):
                        value=data.get(key)
                        if value: node_ids.add(value)
        graph_nodes=[asdict(self.registry.nodes[n]) for n in sorted(node_ids) if n in self.registry.nodes]
        graph_edges=[asdict(e) for e in self.registry.edges.values() if e.from_node_id in node_ids or e.to_node_id in node_ids]
        return {"study_id":study_id,"nodes":graph_nodes,"edges":graph_edges,"node_count":len(graph_nodes),"edge_count":len(graph_edges)}
