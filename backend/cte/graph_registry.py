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
