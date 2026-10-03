"""Executable V1.6 scientific reporting snapshot engine.

This renders registered artifacts; it does not create new evidence.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .provenance import content_hash
from .persistence import SQLiteRuntimeStore

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
    source_artifacts:tuple[str,...]=()
    decisions:dict[str,dict]=field(default_factory=dict)
    sections:dict[str,ReportSection]=field(default_factory=dict)
    bindings:dict[str,ReportClaimBinding]=field(default_factory=dict)
    qc:dict[str,ReportQC]=field(default_factory=dict)
    report_output_hash:str|None=None
    superseded_by:str|None=None
    execution_id:str|None=None
    report_output_hash_version:int=1

def claim_language(claim_status:str)->tuple[str,str]:
    if claim_status=="HYPOTHESIS":
        return "HYPOTHESIS_STATUS","Registered hypothesis; the report does not imply that a result has been established."
    if claim_status=="REGISTERED":
        return "REGISTERED_STATUS","Registered claim; the report does not imply a stronger result status."
    if claim_status=="UNSUPPORTED":
        return "UNSUPPORTED_STATUS","Claim is currently unsupported under the registered evidence graph."
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
    for artifact_id in sorted(set(artifact_ids)):
        node=registry.nodes.get(artifact_id)
        if node is None:
            raise ValueError(f"source artifact is not registered: {artifact_id}")
        entries.append((artifact_id,node.node_type,node.immutable_hash,node.version,node.provenance_class))
    return content_hash(entries)

class ReportService:
    def __init__(self,registry,store:SQLiteRuntimeStore|None=None):
        self.registry=registry
        self.store=store
        self.specs={}
        self.runs={}
        self._hydrate()

    def _hydrate(self):
        if self.store is None:
            return
        for snap in self.store.list_snapshots("report.spec"):
            p=snap.payload
            if content_hash(p) != snap.payload_hash:
                raise ValueError(f"report snapshot integrity failure: {snap.namespace}/{snap.key}")
            self.specs[p["report_spec_id"]]=ReportSpec(
                p["report_spec_id"],p["name"],p["version"],tuple(p["section_order"]),
                p.get("rendering_rules",{}),p.get("claim_language_rules",{}),p["immutable_hash"])
        for snap in self.store.list_snapshots("report.run"):
            p=snap.payload
            if content_hash(p) != snap.payload_hash:
                raise ValueError(f"report snapshot integrity failure: {snap.namespace}/{snap.key}")
            sections={k:ReportSection(v["report_section_id"],v["report_run_id"],v["section_code"],v["ordinal"],
                v["content"],tuple(v["source_artifacts"]),v["derivation_rule_id"],v["derivation_rule_version"],
                v["evidence_status"],tuple(v["limitations"]),v["immutable_hash"]) for k,v in p.get("sections",{}).items()}
            bindings={k:ReportClaimBinding(v["binding_id"],v["report_run_id"],v["claim_id"],v["claim_status"],
                tuple(v["supporting_nodes"]),tuple(v["limiting_nodes"]),tuple(v["contradiction_nodes"]),
                v["allowed_language_rule_id"],v["generated_statement"],v["immutable_hash"]) for k,v in p.get("bindings",{}).items()}
            qc={k:ReportQC(v["report_qc_id"],v["report_run_id"],v["check_code"],v["status"],
                v["observed"],v.get("expected"),v["message"],v["immutable_hash"]) for k,v in p.get("qc",{}).items()}
            self.runs[p["report_run_id"]]=ReportRun(
                p["report_run_id"],p["report_spec_id"],p["study_id"],p["source_manifest_hash"],
                p["report_input_hash"],p.get("status","REGISTERED"),tuple(p.get("source_artifacts",())),
                dict(p.get("decisions",{})),sections,bindings,qc,p.get("report_output_hash"),p.get("superseded_by"),p.get("execution_id"),
                p.get("report_output_hash_version",1)
            )
            run=self.runs[p["report_run_id"]]
            self._validate_recovered_run(run)

    def _validate_recovered_run(self,run:ReportRun):
        spec=self.specs.get(run.report_spec_id)
        if spec is None:
            raise ValueError(f"report snapshot integrity failure: report.run/{run.report_run_id} references missing spec")
        spec_payload={"report_spec_id":spec.report_spec_id,"name":spec.name,"version":spec.version,
                      "section_order":spec.section_order,"rendering_rules":spec.rendering_rules,
                      "claim_language_rules":spec.claim_language_rules}
        if content_hash(spec_payload)!=spec.immutable_hash:
            raise ValueError(f"report snapshot integrity failure: report.spec/{spec.report_spec_id} immutable hash")
        for key,section in run.sections.items():
            payload={"report_section_id":section.report_section_id,"report_run_id":section.report_run_id,
                     "section_code":section.section_code,"ordinal":section.ordinal,"content":section.content,
                     "source_artifacts":list(section.source_artifacts),"derivation_rule_id":section.derivation_rule_id,
                     "derivation_rule_version":section.derivation_rule_version,"evidence_status":section.evidence_status,
                     "limitations":list(section.limitations)}
            if key!=section.section_code or content_hash(payload)!=section.immutable_hash:
                raise ValueError(f"report snapshot integrity failure: report.run/{run.report_run_id} section/{key}")
        for key,binding in run.bindings.items():
            payload={"binding_id":binding.binding_id,"report_run_id":binding.report_run_id,"claim_id":binding.claim_id,
                     "claim_status":binding.claim_status,"supporting_nodes":binding.supporting_nodes,
                     "limiting_nodes":binding.limiting_nodes,"contradiction_nodes":binding.contradiction_nodes,
                     "allowed_language_rule_id":binding.allowed_language_rule_id,"generated_statement":binding.generated_statement}
            if key!=binding.claim_id or content_hash(payload)!=binding.immutable_hash:
                raise ValueError(f"report snapshot integrity failure: report.run/{run.report_run_id} binding/{key}")
        for key,item in run.decisions.items():
            payload={name:value for name,value in item.items() if name!="immutable_hash"}
            if key!=item.get("decision_id") or content_hash(payload)!=item.get("immutable_hash"):
                raise ValueError(f"report snapshot integrity failure: report.run/{run.report_run_id} decision/{key}")
        for key,qc in run.qc.items():
            payload={"report_qc_id":qc.report_qc_id,"run_id":run.report_run_id,"check_code":qc.check_code,
                     "status":qc.status,"observed":qc.observed,"expected":qc.expected,"message":qc.message}
            if key!=qc.check_code or content_hash(payload)!=qc.immutable_hash:
                raise ValueError(f"report snapshot integrity failure: report.run/{run.report_run_id} qc/{key}")
        if run.status in {"PUBLISHED","SUPERSEDED"}:
            if not run.report_output_hash:
                raise ValueError(f"report snapshot integrity failure: report.run/{run.report_run_id} missing output hash")
            if run.report_output_hash_version>=2:
                expected=content_hash({"run_id":run.report_run_id,
                    "sections":[run.sections[k].immutable_hash for k in sorted(run.sections)],
                    "bindings":[run.bindings[k].immutable_hash for k in sorted(run.bindings)],
                    "qc":[run.qc[k].immutable_hash for k in sorted(run.qc)]})
                if expected!=run.report_output_hash:
                    raise ValueError(f"report snapshot integrity failure: report.run/{run.report_run_id} output hash")

    def _persist_run(self,run:ReportRun):
        if self.store is None:
            return
        payload={"report_run_id":run.report_run_id,"report_spec_id":run.report_spec_id,"study_id":run.study_id,
            "source_manifest_hash":run.source_manifest_hash,"report_input_hash":run.report_input_hash,
            "status":run.status,"source_artifacts":list(run.source_artifacts),"decisions":run.decisions,
            "sections":{k:{
                "report_section_id":v.report_section_id,"report_run_id":v.report_run_id,"section_code":v.section_code,
                "ordinal":v.ordinal,"content":v.content,"source_artifacts":list(v.source_artifacts),
                "derivation_rule_id":v.derivation_rule_id,"derivation_rule_version":v.derivation_rule_version,
                "evidence_status":v.evidence_status,"limitations":list(v.limitations),"immutable_hash":v.immutable_hash
            } for k,v in run.sections.items()},
            "bindings":{k:{
                "binding_id":v.binding_id,"report_run_id":v.report_run_id,"claim_id":v.claim_id,"claim_status":v.claim_status,
                "supporting_nodes":list(v.supporting_nodes),"limiting_nodes":list(v.limiting_nodes),
                "contradiction_nodes":list(v.contradiction_nodes),"allowed_language_rule_id":v.allowed_language_rule_id,
                "generated_statement":v.generated_statement,"immutable_hash":v.immutable_hash
            } for k,v in run.bindings.items()},
            "qc":{k:{
                "report_qc_id":v.report_qc_id,"report_run_id":v.report_run_id,"check_code":v.check_code,
                "status":v.status,"observed":v.observed,"expected":v.expected,"message":v.message,"immutable_hash":v.immutable_hash
            } for k,v in run.qc.items()},
            "report_output_hash":run.report_output_hash,"report_output_hash_version":run.report_output_hash_version,
            "superseded_by":run.superseded_by,"execution_id":run.execution_id}
        self.store.put_snapshot("report.run",run.report_run_id,payload,"1.6")


    def register_spec(self,spec:ReportSpec)->ReportSpec:
        if spec.report_spec_id in self.specs:
            raise ValueError("report spec already registered")
        self.specs[spec.report_spec_id]=spec
        if self.store is not None:
            self.store.put_snapshot("report.spec",spec.report_spec_id,{"report_spec_id":spec.report_spec_id,
                "name":spec.name,"version":spec.version,"section_order":list(spec.section_order),
                "rendering_rules":spec.rendering_rules,"claim_language_rules":spec.claim_language_rules,
                "immutable_hash":spec.immutable_hash},spec.version)
        return spec

    def create(self,report_run_id:str,report_spec_id:str,study_id:str,artifact_ids:list[str],execution_id:str|None=None)->ReportRun:
        if report_run_id in self.runs: raise ValueError("report run already registered")
        spec=self.specs.get(report_spec_id)
        if spec is None: raise ValueError("report spec is not registered")
        if not artifact_ids: raise ValueError("source artifacts are required")
        if execution_id and self.store is not None and self.store.get_snapshot("orchestrator.execution",execution_id) is None:
            raise ValueError("execution_id is not registered in orchestrator persistence")
        manifest=build_source_manifest(self.registry,artifact_ids)
        run=ReportRun(report_run_id,report_spec_id,study_id,manifest,content_hash({"report_run_id":report_run_id,"spec":report_spec_id,"manifest":manifest}),"REGISTERED",tuple(artifact_ids),{},execution_id=execution_id)
        self.runs[report_run_id]=run
        self._persist_run(run)
        return run

    def add_decision(self,run_id:str,decision_id:str,decision_type:str,decision:str,rule_id:str,inputs:dict,rationale:str)->dict:
        run=self.runs.get(run_id)
        if run is None: raise ValueError("report run is not registered")
        if run.status in {"PUBLISHED","SUPERSEDED"}: raise ValueError("immutable report cannot be modified")
        if decision_id in run.decisions: raise ValueError("report decision already registered")
        payload={"decision_id":decision_id,"report_run_id":run_id,"decision_type":decision_type,"decision":decision,"rule_id":rule_id,"inputs":inputs,"rationale":rationale}
        item={**payload,"immutable_hash":content_hash(payload)}
        run.decisions[decision_id]=item
        self._persist_run(run)
        return item

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
        self._persist_run(run)
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
        self._persist_run(run)
        return binding

    def qc_run(self,run_id:str)->dict:
        run=self.runs.get(run_id)
        if run is None: raise ValueError("report run is not registered")
        if run.status in {"PUBLISHED","SUPERSEDED"}:
            raise ValueError("immutable report cannot be rechecked")
        expected=set(self.specs[run.report_spec_id].section_order)
        observed=set(run.sections)
        checks={}
        def add(code,status,observed,expected,message):
            payload={"report_qc_id":f"{run_id}:{code}","run_id":run_id,"check_code":code,"status":status,"observed":observed,"expected":expected,"message":message}
            checks[code]=ReportQC(payload["report_qc_id"],run_id,code,status,observed,expected,message,content_hash(payload))
        add("REQUIRED_SECTIONS","PASS" if observed==expected else "FAIL",
            {"present":sorted(observed),"missing":sorted(expected-observed)},
            {"required":sorted(expected)},"required section coverage")
        artifact_ids=sorted(set(run.source_artifacts))
        try: manifest=build_source_manifest(self.registry,artifact_ids)
        except ValueError: manifest=None
        add("SOURCE_MANIFEST","PASS" if manifest==run.source_manifest_hash else "FAIL",
            {"current":manifest},"registered source manifest hash","source manifest must match")
        # Missing source nodes are a report-QC failure, not a KeyError that
        # aborts the whole report lifecycle after graph damage or retention.
        provenance_ok=all(
            aid in self.registry.nodes
            and bool(self.registry.nodes[aid].provenance_class
                     and self.registry.nodes[aid].version
                     and self.registry.nodes[aid].immutable_hash)
            for section in run.sections.values()
            for aid in section.source_artifacts
        )
        add("PROVENANCE","PASS" if provenance_ok else "FAIL",{"complete":provenance_ok},{"complete":True},"source provenance completeness")
        # A report must not retain a stale claim binding after the evidence graph changes.
        bindings_ok=True
        binding_errors=[]
        for claim_id,binding in run.bindings.items():
            claim=self.registry.nodes.get(binding.claim_id)
            if claim is None or claim.node_type!="CLAIM":
                bindings_ok=False
                binding_errors.append({"claim_id":claim_id,"reason":"claim missing or wrong type"})
                continue
            status=claim.metadata.get("state","REGISTERED")
            try:
                _nodes,edges=self.registry.claim_subgraph(binding.claim_id)
            except (KeyError,ValueError):
                bindings_ok=False
                binding_errors.append({"claim_id":claim_id,"reason":"claim subgraph unavailable"})
                continue
            support=tuple(sorted(e.from_node_id for e in edges if e.to_node_id==binding.claim_id and e.edge_type=="SUPPORTS"))
            limits=tuple(sorted(e.from_node_id for e in edges if e.to_node_id==binding.claim_id and e.edge_type in {"LIMITS","QUALIFIES"}))
            contradictions=tuple(sorted(e.from_node_id for e in edges if e.to_node_id==binding.claim_id and e.edge_type=="CONTRADICTS"))
            rule,statement=claim_language(status)
            payload={"binding_id":binding.binding_id,"report_run_id":binding.report_run_id,"claim_id":binding.claim_id,
                     "claim_status":binding.claim_status,"supporting_nodes":binding.supporting_nodes,
                     "limiting_nodes":binding.limiting_nodes,"contradiction_nodes":binding.contradiction_nodes,
                     "allowed_language_rule_id":binding.allowed_language_rule_id,"generated_statement":binding.generated_statement}
            if (binding.report_run_id!=run_id or binding.claim_id!=claim_id or binding.claim_status!=status
                    or binding.supporting_nodes!=support or binding.limiting_nodes!=limits
                    or binding.contradiction_nodes!=contradictions or binding.allowed_language_rule_id!=rule
                    or binding.generated_statement!=statement or binding.immutable_hash!=content_hash(payload)):
                bindings_ok=False
                binding_errors.append({"claim_id":claim_id,"reason":"binding does not match current claim graph or immutable hash"})
        add("CLAIM_BINDINGS","PASS" if bindings_ok else "FAIL",
            {"valid":bindings_ok,"errors":binding_errors},{"valid":True},
            "claim bindings must match current claim status, graph references, and immutable hash")
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
        self._persist_run(run)
        blocking=[code for code,q in checks.items() if q.status=="FAIL"]
        run.status="QC_FAILED" if blocking else "QC_PASSED"
        self._persist_run(run)
        return {"status":run.status,"blocking_checks":blocking,"checks":{k:v.status for k,v in checks.items()}}

    def publish(self,run_id:str)->ReportRun:
        run=self.runs.get(run_id)
        if run is None: raise ValueError("report run is not registered")
        if run.status!="QC_PASSED": raise ValueError("report cannot publish before QC_PASSED")
        current_qc=self.qc_run(run_id)
        if current_qc["status"]!="QC_PASSED":
            raise ValueError("report cannot publish because current-state QC failed")
        previous_status=run.status
        previous_hash=run.report_output_hash
        previous_hash_version=run.report_output_hash_version
        run.report_output_hash_version=2
        run.report_output_hash=content_hash({"run_id":run.report_run_id,
            "sections":[run.sections[k].immutable_hash for k in sorted(run.sections)],
            "bindings":[run.bindings[k].immutable_hash for k in sorted(run.bindings)],
            "qc":[run.qc[k].immutable_hash for k in sorted(run.qc)]})
        run.status="PUBLISHED"
        try:
            self._persist_run(run)
        except Exception:
            run.status=previous_status
            run.report_output_hash=previous_hash
            run.report_output_hash_version=previous_hash_version
            raise
        return run

    def supersede(self,old_id:str,new_id:str)->ReportRun:
        old=self.runs.get(old_id); new=self.runs.get(new_id)
        if old is None or new is None: raise ValueError("both reports must be registered")
        if old_id==new_id: raise ValueError("a report cannot supersede itself")
        if old.status!="PUBLISHED": raise ValueError("only published reports can be superseded")
        if new.status!="PUBLISHED": raise ValueError("a report can only be superseded by a published report")
        previous_status=old.status
        previous_successor=old.superseded_by
        old.superseded_by=new_id
        old.status="SUPERSEDED"
        try:
            self._persist_run(old)
        except Exception:
            old.status=previous_status
            old.superseded_by=previous_successor
            raise
        return new
