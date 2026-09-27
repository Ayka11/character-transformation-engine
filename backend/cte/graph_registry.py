"""In-memory executable registry for the evidence graph lineage contract."""
from __future__ import annotations
from dataclasses import dataclass
from .evidence_graph import GraphNode, GraphEdge, register_node, register_edge

@dataclass
class GraphRegistry:
    nodes: dict[str, GraphNode]
    edges: dict[str, GraphEdge]

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
        return edge


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

    def claim_requirements(self, result_id: str) -> set[str]:
        """Derive V1.4 transition prerequisites from registered graph metadata/lineage."""
        self.require_lineage_for_result(result_id)
        nodes=self._upstream_nodes(result_id)
        all_nodes=[self.nodes[result_id],*nodes]
        types={n.node_type for n in all_nodes}
        req={"valid_result"} if self.nodes[result_id].metadata.get("qc_status")=="PASS" else set()
        if "ANALYSIS" in types:
            req.add("registered_analysis")
        if self.nodes[result_id].metadata.get("qc_status")=="PASS":
            req.add("validated_descriptive_result")
        for node in nodes:
            md=node.metadata or {}
            design=str(md.get("design_type","")).upper()
            if node.node_type=="PROTOCOL" and design=="ASSOCIATIONAL":
                req.add("association_design")
            if node.node_type=="PROTOCOL" and design=="INTERVENTION":
                req.add("registered_intervention")
            if node.node_type=="REPLICATION" and bool(md.get("independent",False)):
                req.add("independent_replication")
            if node.node_type=="REPLICATION" and bool(md.get("criteria_registered",False)):
                req.add("registered_replication_criteria")
            if node.node_type=="GENERALIZATION" and md.get("run_status")=="COMPLETED":
                req.add("generalization_run")
            if node.node_type=="GENERALIZATION" and md.get("target_population_context"):
                req.add("target_population_context")
            if bool(md.get("evidence_criteria_registered",False)):
                req.add("registered_evidence_criteria")
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
