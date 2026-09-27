"""Executable V1.6 scientific reporting snapshot engine.

This renders registered artifacts; it does not create new evidence.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .provenance import content_hash

SECTION_CODES=(
    "EXECUTIVE_SUMMARY","RESEARCH_QUESTION_HYPOTHESES","MEASUREMENT_SPECIFICATION",
    "STUDY_DESIGN_PARTICIPANTS","DATA_QUALITY_QC","STATISTICAL_ANALYSIS",
    "RESULTS_UNCERTAINTY","REPLICATION","GENERALIZATION_TRANSPORT",
    "EVIDENCE_CLAIM_GRAPH","CLAIM_STATUS","LIMITATIONS_BOUNDARIES",
    "PROVENANCE_MANIFEST","REPRODUCIBILITY_METADATA",
)
ALLOWED_EVIDENCE_STATUS=set((
    "OBSERVATION","MEASUREMENT","DESCRIPTIVE_RESULT","ASSOCIATIONAL_RESULT",
    "INTERVENTION_RESULT","REPLICATED_RESULT","GENERALIZED_RESULT",
    "EVIDENCE_SUPPORTED","LIMITED","INDETERMINATE",
))
CLAIM_ORDER={
    "HYPOTHESIS":0,"REGISTERED":1,"DESCRIPTIVE_RESULT":2,"ASSOCIATIONAL_RESULT":3,
    "INTERVENTION_RESULT":4,"REPLICATED_RESULT":5,"GENERALIZED_RESULT":6,"EVIDENCE_SUPPORTED":7,
    "INDETERMINATE":0,"UNSUPPORTED":0,"CONTRADICTED":0,
}

@dataclass(frozen=True)
class ReportSpec:
    report_spec_id:str
    name:str
    version:str
    section_order:tuple[str,...]
    rendering_rules:dict
    claim_language_rules:dict
    immutable_hash:str

def register_spec(report_spec_id:str,name:str,version:str="1.6",
                  section_order:list[str]|None=None,
                  rendering_rules:dict|None=None,
                  claim_language_rules:dict|None=None)->ReportSpec:
    sections=tuple(section_order or SECTION_CODES)
    if set(sections)!=set(SECTION_CODES):
        raise ValueError("report specification must contain the V1.6 section set")
    payload={"report_spec_id":report_spec_id,"name":name,"version":version,
             "section_order":sections,"rendering_rules":rendering_rules or {},
             "claim_language_rules":claim_language_rules or {}}
    return ReportSpec(report_spec_id,name,version,sections,rendering_rules or {},
                      claim_language_rules or {},content_hash(payload))

@dataclass(frozen=True)
class ReportSection:
    report_section_id:str
    report_run_id:str
    section_code:str
    ordinal:int
    content:dict
    source_artifacts:tuple[str,...]
    derivation_rule_id:str
    derivation_rule_version:str
    evidence_status:str
    limitations:tuple[str,...]
    immutable_hash:str

@dataclass(frozen=True)
class ReportClaimBinding:
    binding_id:str
    report_run_id:str
    claim_id:str
    claim_status:str
    supporting_nodes:tuple[str,...]
    limiting_nodes:tuple[str,...]
    contradiction_nodes:tuple[str,...]
    allowed_language_rule_id:str
    generated_statement:str
    immutable_hash:str

@dataclass(frozen=True)
class ReportQC:
    report_qc_id:str
    report_run_id:str
    check_code:str
    status:str
    observed:dict
    expected:dict|None
    message:str
    immutable_hash:str

@dataclass
class ReportRun:
    report_run_id:str
    report_spec_id:str
    study_id:str
    source_manifest_hash:str
    report_input_hash:str
    status:str="REGISTERED"
    sections:dict[str,ReportSection]=field(default_factory=dict)
    bindings:dict[str,ReportClaimBinding]=field(default_factory=dict)
    qc:dict[str,ReportQC]=field(default_factory=dict)
    report_output_hash:str|None=None
    superseded_by:str|None=None

def claim_language(claim_status:str)->tuple[str,str]:
    if claim_status=="ASSOCIATIONAL_RESULT":
        return "ASSOCIATIONAL_STATUS","Registered associational result; this status does not by itself establish causality."
    if claim_status=="INTERVENTION_RESULT":
        return "INTERVENTION_STATUS","Registered intervention result under the declared design and analysis."
    if claim_status=="REPLICATED_RESULT":
        return "REPLICATION_STATUS","Registered replicated result under the registered replication criteria."
    if claim_status=="GENERALIZED_RESULT":
        return "GENERALIZATION_STATUS","Registered generalized result within the declared target population and context."
    if claim_status=="EVIDENCE_SUPPORTED":
        return "EVIDENCE_STATUS","Evidence-supported claim under the registered evidence criteria and provenance."
    if claim_status=="CONTRADICTED":
        return "CONTRADICTION_STATUS","Claim has an unresolved contradiction recorded in the evidence graph."
    if claim_status=="INDETERMINATE":
        return "INDETERMINATE_STATUS","Claim status is indeterminate because required information is insufficient or conflicting."
    return "DESCRIPTIVE_STATUS","Registered descriptive result; the report does not infer stronger causal or universal claims."

def build_source_manifest(registry, artifact_ids:list[str])->str:
    entries=[]
    for artifact_id in artifact_ids:
        node=registry.nodes.get(artifact_id)
        if node is None:
            raise ValueError(f"source artifact is not registered: {artifact_id}")
        entries.append((artifact_id,node.node_type,node.immutable_hash,node.version,node.provenance_class))
    return content_hash(entries)

class ReportService:
    def __init__(self,registry):
        self.registry=registry
        self.specs={}
        self.runs={}

    def create(self,report_run_id:str,report_spec_id:str,study_id:str,artifact_ids:list[str])->ReportRun:
        if report_run_id in self.runs: raise ValueError("report run already registered")
        spec=self.specs.get(report_spec_id)
        if spec is None: raise ValueError("report spec is not registered")
        if not artifact_ids: raise ValueError("source artifacts are required")
        manifest=build_source_manifest(self.registry,artifact_ids)
        run=ReportRun(report_run_id,report_spec_id,study_id,manifest,content_hash({"report_run_id":report_run_id,"spec":report_spec_id,"manifest":manifest}))
        self.runs[report_run_id]=run
        return run

    def add_section(self,run_id:str,section_code:str,content:dict,source_artifacts:list[str],
                    ordinal:int,derivation_rule_id:str="V1.6_RENDER",derivation_rule_version:str="1.6",
                    evidence_status:str="INDETERMINATE",limitations:list[str]|None=None)->ReportSection:
        run=self.runs.get(run_id)
        if run is None: raise ValueError("report run is not registered")
        if run.status in {"PUBLISHED","SUPERSEDED"}: raise ValueError("immutable report cannot be modified")
        if section_code not in SECTION_CODES: raise ValueError("unsupported report section")
        if evidence_status not in ALLOWED_EVIDENCE_STATUS: raise ValueError("unsupported evidence status")
        for artifact_id in source_artifacts:
            if artifact_id not in self.registry.nodes: raise ValueError(f"source artifact is not registered: {artifact_id}")
        payload={"report_section_id":f"{run_id}:{section_code}","report_run_id":run_id,"section_code":section_code,
                 "ordinal":ordinal,"content":content,"source_artifacts":source_artifacts,
                 "derivation_rule_id":derivation_rule_id,"derivation_rule_version":derivation_rule_version,
                 "evidence_status":evidence_status,"limitations":limitations or []}
        sec=ReportSection(payload["report_section_id"],run_id,section_code,ordinal,content,tuple(source_artifacts),
                          derivation_rule_id,derivation_rule_version,evidence_status,tuple(limitations or []),content_hash(payload))
        if section_code in run.sections: raise ValueError("report section already registered")
        run.sections[section_code]=sec
        return sec

    def bind_claim(self,run_id:str,claim_id:str,allowed_claim_status:str|None=None)->ReportClaimBinding:
        run=self.runs.get(run_id)
        claim=self.registry.nodes.get(claim_id)
        if run is None: raise ValueError("report run is not registered")
        if claim is None or claim.node_type!="CLAIM": raise ValueError("claim is not registered")
        if run.status in {"PUBLISHED","SUPERSEDED"}: raise ValueError("immutable report cannot be modified")
        status=claim.metadata.get("state","REGISTERED")
        if allowed_claim_status and status!=allowed_claim_status: raise ValueError("claim status mismatch")
        nodes,edges=self.registry.claim_subgraph(claim_id)
        ids={n.node_id for n in nodes}
        support=tuple(sorted(e.from_node_id for e in edges if e.to_node_id==claim_id and e.edge_type=="SUPPORTS"))
        limits=tuple(sorted(e.from_node_id for e in edges if e.to_node_id==claim_id and e.edge_type in {"LIMITS","QUALIFIES"}))
        contradictions=tuple(sorted(e.from_node_id for e in edges if e.to_node_id==claim_id and e.edge_type=="CONTRADICTS"))
        rule,statement=claim_language(status)
        payload={"binding_id":f"{run_id}:{claim_id}","report_run_id":run_id,"claim_id":claim_id,"claim_status":status,
                 "supporting_nodes":support,"limiting_nodes":limits,"contradiction_nodes":contradictions,
                 "allowed_language_rule_id":rule,"generated_statement":statement}
        binding=ReportClaimBinding(payload["binding_id"],run_id,claim_id,status,support,limits,contradictions,rule,statement,content_hash(payload))
        run.bindings[claim_id]=binding
        return binding

    def qc_run(self,run_id:str)->dict:
        run=self.runs.get(run_id)
        if run is None: raise ValueError("report run is not registered")
        expected=set(self.specs[run.report_spec_id].section_order)
        observed=set(run.sections)
        checks={}
        def add(code,status,observed,expected,message):
            payload={"report_qc_id":f"{run_id}:{code}","run_id":run_id,"check_code":code,"status":status,"observed":observed,"expected":expected,"message":message}
            checks[code]=ReportQC(payload["report_qc_id"],run_id,code,status,observed,expected,message,content_hash(payload))
        add("REQUIRED_SECTIONS","PASS" if observed==expected else "FAIL",
            {"present":sorted(observed),"missing":sorted(expected-observed)},
            {"required":sorted(expected)},"required section coverage")
        artifact_ids=sorted({a for s in run.sections.values() for a in s.source_artifacts})
        try: manifest=build_source_manifest(self.registry,artifact_ids)
        except ValueError: manifest=None
        add("SOURCE_MANIFEST","PASS" if manifest==run.source_manifest_hash else "FAIL",
            {"current":manifest},"registered source manifest hash","source manifest must match")
        provenance_ok=all(bool(n.provenance_class and n.version and n.immutable_hash) for s in run.sections.values() for aid in s.source_artifacts for n in [self.registry.nodes[aid]])
        add("PROVENANCE","PASS" if provenance_ok else "FAIL",{"complete":provenance_ok},{"complete":True},"source provenance completeness")
        has_rep=any(n.node_type=="REPLICATION" for n in self.registry.nodes.values())
        has_gen=any(n.node_type=="GENERALIZATION" for n in self.registry.nodes.values())
        section_codes=set(run.sections)
        rep_ok=(not has_rep) or "REPLICATION" in section_codes
        gen_ok=(not has_gen) or "GENERALIZATION_TRANSPORT" in section_codes
        add("REPLICATION_REPORTING","PASS" if rep_ok else "FAIL",{"required":has_rep,"present":"REPLICATION" in section_codes},{"reported":True},"replication must be explicitly reported when applicable")
        add("GENERALIZATION_REPORTING","PASS" if gen_ok else "FAIL",{"required":has_gen,"present":"GENERALIZATION_TRANSPORT" in section_codes},{"reported":True},"generalization must be explicitly reported when applicable")
        limitation_ok="LIMITATIONS_BOUNDARIES" in section_codes
        add("LIMITATIONS","PASS" if limitation_ok else "FAIL",{"present":limitation_ok},{"required":True},"limitations and boundaries are required")
        run.qc=checks
        blocking=[code for code,q in checks.items() if q.status=="FAIL"]
        run.status="QC_FAILED" if blocking else "QC_PASSED"
        return {"status":run.status,"blocking_checks":blocking,"checks":{k:v.status for k,v in checks.items()}}

    def publish(self,run_id:str)->ReportRun:
        run=self.runs.get(run_id)
        if run is None: raise ValueError("report run is not registered")
        if run.status!="QC_PASSED": raise ValueError("report cannot publish before QC_PASSED")
        run.report_output_hash=content_hash({"run_id":run.report_run_id,
            "sections":[s.immutable_hash for s in run.sections.values()],
            "bindings":[b.immutable_hash for b in run.bindings.values()],
            "qc":[q.immutable_hash for q in run.qc.values()]})
        run.status="PUBLISHED"
        return run

    def supersede(self,old_id:str,new_id:str)->ReportRun:
        old=self.runs.get(old_id); new=self.runs.get(new_id)
        if old is None or new is None: raise ValueError("both reports must be registered")
        if old.status!="PUBLISHED": raise ValueError("only published reports can be superseded")
        old.superseded_by=new_id
        old.status="SUPERSEDED"
        return new
