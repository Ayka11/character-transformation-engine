"""In-memory executable registry for the evidence graph lineage contract."""
from __future__ import annotations
from dataclasses import dataclass, field
from .evidence_graph import GraphNode, GraphEdge, register_node, register_edge

@dataclass(frozen=True)
class GraphAuditEvent:
    operation: str
    node_id: str | None
    edge_id: str | None
    claim_id: str | None
    payload_hash: str
    actor_type: str

@dataclass(frozen=True)
class ContradictionSet:
    contradiction_set_id: str
    claim_id: str
    node_ids: tuple[str,...]
    contradiction_type: str
    resolution_status: str
    resolution_note: str | None
    provenance_class: str
    version: str
    immutable_hash: str

@dataclass(frozen=True)
class InferenceBlock:
    inference_block_id: str
    from_node_type: str
    to_claim_level: str
    blocked_inference: str
    reason_code: str
    rule_id: str
    immutable_hash: str

@dataclass
class GraphRegistry:
    nodes: dict[str, GraphNode]
    edges: dict[str, GraphEdge]
    audit_events: list[GraphAuditEvent] = field(default_factory=list)
    contradiction_sets: dict[str, ContradictionSet] = field(default_factory=dict)
    inference_blocks: dict[str, InferenceBlock] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "GraphRegistry":
        return cls({}, {})

    def add_node(self, node: GraphNode) -> GraphNode:
        if node.node_id in self.nodes:
            existing=self.nodes[node.node_id]
            if existing.immutable_hash != node.immutable_hash:
                raise ValueError("immutable node conflict")
            return existing
        self.nodes[node.node_id]=node
        self.audit_events.append(GraphAuditEvent("NODE_REGISTERED",node.node_id,None,
            node.node_id if node.node_type=="CLAIM" else None,node.immutable_hash,"runtime"))
        return node

    def add_edge(self, edge: GraphEdge) -> GraphEdge:
        if edge.edge_id in self.edges:
            existing=self.edges[edge.edge_id]
            if existing.input_hash != edge.input_hash:
                raise ValueError("immutable edge conflict")
            return existing
        if edge.from_node_id not in self.nodes or edge.to_node_id not in self.nodes:
            raise ValueError("edge references unknown node")
        self.edges[edge.edge_id]=edge
        claim_id = edge.to_node_id if self.nodes.get(edge.to_node_id, None) and self.nodes[edge.to_node_id].node_type=="CLAIM" else (edge.from_node_id if self.nodes.get(edge.from_node_id, None) and self.nodes[edge.from_node_id].node_type=="CLAIM" else None)
        self.audit_events.append(GraphAuditEvent("EDGE_REGISTERED",None,edge.edge_id,claim_id,edge.input_hash,"runtime"))
        return edge


    def register_contradiction_set(self, contradiction_set_id: str, claim_id: str,
                                    node_ids: list[str], contradiction_type: str,
                                    resolution_status: str = "UNRESOLVED",
                                    resolution_note: str | None = None) -> ContradictionSet:
        if contradiction_set_id in self.contradiction_sets:
            raise ValueError("contradiction set already registered")
        claim=self.nodes.get(claim_id)
        if claim is None or claim.node_type!="CLAIM":
            raise ValueError("claim is not registered")
        if not node_ids:
            raise ValueError("contradiction set requires at least one node")
        for node_id in node_ids:
            if node_id not in self.nodes:
                raise ValueError("contradiction references unknown node")
        if resolution_status not in {"OPEN","EXPLAINED","UNRESOLVED","RESOLVED_BY_NEW_EVIDENCE"}:
            raise ValueError("unsupported contradiction resolution status")
        payload={"contradiction_set_id":contradiction_set_id,"claim_id":claim_id,
                 "node_ids":node_ids,"contradiction_type":contradiction_type,
                 "resolution_status":resolution_status,"resolution_note":resolution_note}
        item=ContradictionSet(contradiction_set_id,claim_id,tuple(node_ids),contradiction_type,
            resolution_status,resolution_note,"DRV","1.4",content_hash(payload))
        self.contradiction_sets[contradiction_set_id]=item
        for node_id in node_ids:
            self.add_edge(register_edge(f"{contradiction_set_id}:contradicts:{node_id}:{claim_id}",
                self.nodes[node_id],claim,"CONTRADICTS",rationale=contradiction_type))
        return item

    def register_inference_block(self, inference_block_id: str, from_node_type: str,
                                 to_claim_level: str, blocked_inference: str,
                                 reason_code: str, rule_id: str) -> InferenceBlock:
        if inference_block_id in self.inference_blocks:
            raise ValueError("inference block already registered")
        payload={"inference_block_id":inference_block_id,"from_node_type":from_node_type,
                 "to_claim_level":to_claim_level,"blocked_inference":blocked_inference,
                 "reason_code":reason_code,"rule_id":rule_id}
        item=InferenceBlock(inference_block_id,from_node_type,to_claim_level,blocked_inference,
            reason_code,rule_id,content_hash(payload))
        self.inference_blocks[inference_block_id]=item
        return item

    def contradiction_requirements(self, claim_id: str) -> set[str]:
        return {"unresolved_material_contradiction"} if any(
            s.claim_id==claim_id and s.resolution_status in {"OPEN","UNRESOLVED"}
            for s in self.contradiction_sets.values()) else set()

    def claim_subgraph(self, claim_id: str) -> tuple[list[GraphNode], list[GraphEdge]]:
        claim=self.nodes.get(claim_id)
        if claim is None or claim.node_type!="CLAIM":
            raise ValueError("claim is not registered")
        seen={claim_id}
        queue=[claim_id]
        while queue:
            current=queue.pop()
            for edge in self.edges.values():
                if edge.to_node_id != current or edge.from_node_id in seen:
                    continue
                if edge.from_node_id not in self.nodes:
                    continue
                seen.add(edge.from_node_id)
                queue.append(edge.from_node_id)
        nodes=[self.nodes[nid] for nid in seen]
        edges=[e for e in self.edges.values() if e.from_node_id in seen and e.to_node_id in seen]
        return nodes,edges

    def claim_audit(self, claim_id: str) -> list[GraphAuditEvent]:
        nodes,edges=self.claim_subgraph(claim_id)
        ids={n.node_id for n in nodes}
        edge_ids={e.edge_id for e in edges}
        return [e for e in self.audit_events if (e.claim_id==claim_id) or
                (e.node_id in ids) or (e.edge_id in edge_ids)]
    
    def upstream_types(self, node_id: str) -> set[str]:
        if node_id not in self.nodes:
            raise ValueError("node is not registered")
        return {self.nodes[e.from_node_id].node_type for e in self.edges.values()
                if e.to_node_id == node_id and e.from_node_id in self.nodes}

    def claim_upstream_types(self, result_id: str) -> set[str]:
        """Return types reachable upstream from a RESULT through registered edges."""
        if result_id not in self.nodes or self.nodes[result_id].node_type != "RESULT":
            raise ValueError("RESULT node is not registered")
        found: set[str] = {"RESULT"}
        frontier=[result_id]
        seen={result_id}
        while frontier:
            current=frontier.pop()
            for edge in self.edges.values():
                if edge.to_node_id != current or edge.from_node_id in seen:
                    continue
                if edge.from_node_id not in self.nodes:
                    continue
                seen.add(edge.from_node_id)
                found.add(self.nodes[edge.from_node_id].node_type)
                frontier.append(edge.from_node_id)
        return found


    def _upstream_nodes(self, result_id: str) -> list[GraphNode]:
        if result_id not in self.nodes or self.nodes[result_id].node_type != "RESULT":
            raise ValueError("RESULT node is not registered")
        found=[]
        frontier=[result_id]
        seen={result_id}
        while frontier:
            current=frontier.pop()
            for edge in self.edges.values():
                if edge.to_node_id != current or edge.from_node_id in seen:
                    continue
                node=self.nodes.get(edge.from_node_id)
                if node is None:
                    continue
                seen.add(node.node_id)
                found.append(node)
                frontier.append(node.node_id)
        return found

    def claim_requirements(self, result_id: str, claim_ids: set[str] | None = None) -> set[str]:
        """Derive V1.4 transition prerequisites from registered graph metadata/lineage."""
        self.require_lineage_for_result(result_id)
        nodes=self._upstream_nodes(result_id)
        all_nodes=[self.nodes[result_id],*nodes]
        types={n.node_type for n in all_nodes}
        req={"valid_result"} if self.nodes[result_id].metadata.get("qc_status")=="PASS" else set()
        if "ANALYSIS" in types:
            req.add("registered_analysis")
        if bool(self.nodes[result_id].metadata.get("validated_descriptive_result",False)):
            req.add("validated_descriptive_result")
        for node in nodes:
            md=node.metadata or {}
            design=str(md.get("design_type","")).upper()
            if node.node_type=="PROTOCOL" and md.get("kind")=="EVIDENCE_CRITERIA":
                allowed_claim_ids=claim_ids or set()
                if md.get("claim_id") in allowed_claim_ids:
                    req.add("registered_evidence_criteria")
            if node.node_type=="PROTOCOL" and design=="ASSOCIATIONAL":
                req.add("association_design")
            if node.node_type=="PROTOCOL" and design=="INTERVENTION":
                req.add("registered_intervention")
            if node.node_type=="REPLICATION" and bool(md.get("independent",False)) and md.get("assessment_status")=="REPLICATED":
                req.add("independent_replication")
            if node.node_type=="REPLICATION" and bool(md.get("criteria_registered",False)) and md.get("assessment_status")=="REPLICATED":
                req.add("registered_replication_criteria")
            if node.node_type=="GENERALIZATION" and md.get("run_status")=="COMPLETED" and md.get("result_status")=="GENERALIZABLE":
                req.add("generalization_run")
            if node.node_type=="GENERALIZATION" and md.get("target_population_context"):
                req.add("target_population_context")
        if all(n.provenance_class and n.version and n.immutable_hash for n in all_nodes):
            req.add("complete_provenance")
        return req

    def register_claim(self, claim_id: str, result_id: str | None, current_state: str,
                       target_state: str, provenance_class: str, metadata: dict,
                       previous_claim_id: str | None = None) -> GraphNode:
        if claim_id in self.nodes:
            raise ValueError("claim node already registered")
        if current_state != "HYPOTHESIS" and previous_claim_id is None:
            raise ValueError("previous_claim_id is required for non-initial claim transitions")
        if previous_claim_id is not None:
            previous=self.nodes.get(previous_claim_id)
            if previous is None or previous.node_type!="CLAIM":
                raise ValueError("previous claim is not registered")
            stored_state=previous.metadata.get("state")
            if stored_state != current_state:
                raise ValueError("current_state does not match previous claim state")
            if result_id is None:
                result_id=previous.metadata.get("result_id")
        if target_state != "REGISTERED" or current_state != "HYPOTHESIS":
            if not result_id:
                raise ValueError("result_id is required for result-backed claim transitions")
        requirements={"claim_registration"} if current_state=="HYPOTHESIS" and target_state=="REGISTERED" else set()
        if result_id:
            requirements=self.claim_requirements(result_id) | requirements
        from .claim_gate import validate_claim_transition
        validate_claim_transition(current_state,target_state,requirements,provenance_class)
        payload=dict(metadata)
        payload.update({"current_state":current_state,"state":target_state,"result_id":result_id})
        claim=register_node(claim_id,"CLAIM",claim_id,provenance_class,"2.1.0",payload)
        self.add_node(claim)
        try:
            if result_id:
                self.add_edge(register_edge(
                    f"{claim_id}:supports:{result_id}",
                    self.nodes[result_id],
                    claim,
                    "SUPPORTS",
                    rationale=f"claim transition {current_state} -> {target_state}",
                ))
            if previous_claim_id:
                self.add_edge(register_edge(
                    f"{claim_id}:derived-from:{previous_claim_id}",
                    claim,
                    self.nodes[previous_claim_id],
                    "DERIVED_FROM",
                    rationale=f"claim state history {current_state} -> {target_state}",
                ))
            return claim
        except Exception:
            self.nodes.pop(claim_id, None)
            raise

    def require_lineage_for_result(self, result_id: str) -> None:
        result=self.nodes.get(result_id)
        if result is None or result.node_type != "RESULT":
            raise ValueError("RESULT node is not registered")
        analysis_ids={e.from_node_id for e in self.edges.values() if e.to_node_id==result_id and e.edge_type=="RESULTS_IN"}
        if not analysis_ids:
            raise ValueError("RESULT requires ANALYSIS -> RESULT lineage")
        for analysis_id in analysis_ids:
            if self.nodes[analysis_id].node_type != "ANALYSIS":
                raise ValueError("RESULT lineage source must be ANALYSIS")
            upstream={e.from_node_id for e in self.edges.values() if e.to_node_id==analysis_id and e.edge_type=="ANALYZED_FROM"}
            if not any(self.nodes[x].node_type in {"DATASET","MEASUREMENT"} for x in upstream):
                raise ValueError("ANALYSIS requires DATASET or MEASUREMENT upstream")

def build_registry() -> GraphRegistry:
    return GraphRegistry.empty()
