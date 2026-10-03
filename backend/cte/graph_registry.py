"""In-memory executable registry for the evidence graph lineage contract."""
from __future__ import annotations
from dataclasses import dataclass, field
from .evidence_graph import GraphNode, GraphEdge, register_node, register_edge
from .provenance import content_hash
from .persistence import SQLiteRuntimeStore

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
    store: SQLiteRuntimeStore | None = None
    integrity_errors: list[str] = field(default_factory=list)

    @classmethod
    def empty(cls, store: SQLiteRuntimeStore | None = None) -> "GraphRegistry":
        registry=cls({}, {}, store=store)
        if store is not None:
            for snap in store.list_snapshots("graph.node"):
                p=snap.payload
                registry.nodes[p["node_id"]]=GraphNode(**p)
            for snap in store.list_snapshots("graph.edge"):
                p=snap.payload
                registry.edges[p["edge_id"]]=GraphEdge(**p)
            for snap in store.list_snapshots("graph.contradiction"):
                p=snap.payload
                registry.contradiction_sets[p["contradiction_set_id"]]=ContradictionSet(**p)
            for snap in store.list_snapshots("graph.inference"):
                p=snap.payload
                registry.inference_blocks[p["inference_block_id"]]=InferenceBlock(**p)
            # Recompute canonical fingerprints during recovery instead of
            # trusting persisted envelope fields. A backup/database attacker
            # could otherwise alter both a snapshot payload and its storage hash.
            for node in registry.nodes.values():
                canonical = register_node(
                    node.node_id, node.node_type, node.entity_id,
                    node.provenance_class, node.version, node.metadata,
                )
                if canonical.immutable_hash != node.immutable_hash:
                    raise ValueError(f"evidence graph node integrity failure: {node.node_id}")
            for edge in registry.edges.values():
                if edge.from_node_id not in registry.nodes or edge.to_node_id not in registry.nodes:
                    # Preserve degraded recovery so downstream claim validation can
                    # report missing lineage instead of crashing service startup.
                    registry.integrity_errors.append(
                        f"evidence graph edge references missing node: {edge.edge_id}"
                    )
                    continue
                canonical_hash = content_hash({
                    "edge_id": edge.edge_id,
                    "from": edge.from_node_id,
                    "to": edge.to_node_id,
                    "type": edge.edge_type,
                    "rationale": edge.rationale,
                })
                if canonical_hash != edge.input_hash:
                    raise ValueError(f"evidence graph edge integrity failure: {edge.edge_id}")
            for event in store.list_events("graph"):
                registry.audit_events.append(GraphAuditEvent(
                    event["event_type"],event["payload"].get("node_id"),event["payload"].get("edge_id"),
                    event["payload"].get("claim_id"),event["payload"].get("payload_hash",""),"runtime"
                ))
        return registry

    def add_node(self, node: GraphNode) -> GraphNode:
        if node.node_id in self.nodes:
            existing=self.nodes[node.node_id]
            # The content hash intentionally excludes envelope metadata for
            # backward compatibility, so compare provenance/version separately.
            # Otherwise an ID replay could silently substitute a different
            # provenance class or schema version while retaining the same hash.
            if (
                existing.immutable_hash != node.immutable_hash
                or existing.provenance_class != node.provenance_class
                or existing.version != node.version
            ):
                raise ValueError("immutable node conflict")
            return existing
        if self.store is not None:
            self.store.put_snapshot("graph.node",node.node_id,{"node_id":node.node_id,"node_type":node.node_type,"entity_id":node.entity_id,"provenance_class":node.provenance_class,"version":node.version,"immutable_hash":node.immutable_hash,"metadata":node.metadata},node.version)
        self.nodes[node.node_id]=node
        audit=GraphAuditEvent("NODE_REGISTERED",node.node_id,None,
            node.node_id if node.node_type=="CLAIM" else None,node.immutable_hash,"runtime")
        self.audit_events.append(audit)
        if self.store is not None:
            self.store.append_event(f"graph:node:{node.node_id}","graph","NODE_REGISTERED",
                                     {"node_id":node.node_id,"payload_hash":node.immutable_hash,
                                      "claim_id":audit.claim_id},provenance_record_id=node.version)
        return node

    def add_edge(self, edge: GraphEdge) -> GraphEdge:
        if edge.edge_id in self.edges:
            existing=self.edges[edge.edge_id]
            # input_hash is a content fingerprint, but relation_status is not
            # part of the canonical edge hash. Compare the complete immutable
            # record so a replay cannot silently substitute status metadata.
            if existing != edge:
                raise ValueError("immutable edge conflict")
            return existing
        if edge.from_node_id not in self.nodes or edge.to_node_id not in self.nodes:
            raise ValueError("edge references unknown node")
        if self.store is not None:
            self.store.put_snapshot("graph.edge",edge.edge_id,{"edge_id":edge.edge_id,"from_node_id":edge.from_node_id,"to_node_id":edge.to_node_id,"edge_type":edge.edge_type,"relation_status":edge.relation_status,"input_hash":edge.input_hash,"rationale":edge.rationale},"1.4")
        self.edges[edge.edge_id]=edge
        claim_id = edge.to_node_id if self.nodes.get(edge.to_node_id, None) and self.nodes[edge.to_node_id].node_type=="CLAIM" else (edge.from_node_id if self.nodes.get(edge.from_node_id, None) and self.nodes[edge.from_node_id].node_type=="CLAIM" else None)
        audit=GraphAuditEvent("EDGE_REGISTERED",None,edge.edge_id,claim_id,edge.input_hash,"runtime")
        self.audit_events.append(audit)
        if self.store is not None:
            self.store.append_event(f"graph:edge:{edge.edge_id}","graph","EDGE_REGISTERED",
                                    {"edge_id":edge.edge_id,"payload_hash":edge.input_hash,"claim_id":claim_id},
                                    input_hash=edge.input_hash,provenance_record_id="1.4")
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
        if self.store is not None:
            self.store.put_snapshot("graph.contradiction",contradiction_set_id,{"contradiction_set_id":item.contradiction_set_id,"claim_id":item.claim_id,"node_ids":list(item.node_ids),"contradiction_type":item.contradiction_type,"resolution_status":item.resolution_status,"resolution_note":item.resolution_note,"provenance_class":item.provenance_class,"version":item.version,"immutable_hash":item.immutable_hash},item.version)
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
        if self.store is not None:
            self.store.put_snapshot("graph.inference",inference_block_id,{"inference_block_id":item.inference_block_id,"from_node_type":item.from_node_type,"to_claim_level":item.to_claim_level,"blocked_inference":item.blocked_inference,"reason_code":item.reason_code,"rule_id":item.rule_id,"immutable_hash":item.immutable_hash},"1.4")
        self.inference_blocks[inference_block_id]=item
        return item

    def contradiction_requirements(self, claim_ids: set[str]) -> set[str]:
        return {"unresolved_material_contradiction"} if any(
            s.claim_id in claim_ids and s.resolution_status in {"OPEN","UNRESOLVED"}
            for s in self.contradiction_sets.values()) else set()

    def claim_subgraph(self, claim_id: str) -> tuple[list[GraphNode], list[GraphEdge]]:
        claim=self.nodes.get(claim_id)
        if claim is None or claim.node_type!="CLAIM":
            raise ValueError("claim is not registered")
        seen={claim_id}
        queue=[claim_id]
        while queue:
            current=queue.pop()
            for node_id in self._lineage_neighbors(current):
                if node_id in seen or node_id not in self.nodes:
                    continue
                seen.add(node_id)
                queue.append(node_id)
        nodes=[self.nodes[nid] for nid in seen]
        edges=[e for e in self.edges.values() if e.from_node_id in seen and e.to_node_id in seen]
        return nodes,edges

    def claim_audit(self, claim_id: str) -> list[GraphAuditEvent]:
        nodes,edges=self.claim_subgraph(claim_id)
        ids={n.node_id for n in nodes}
        edge_ids={e.edge_id for e in edges}
        matching=[e for e in self.audit_events if (e.claim_id==claim_id) or
                  (e.node_id in ids) or (e.edge_id in edge_ids)]
        return sorted(matching, key=lambda e: (
            e.operation, e.node_id or "", e.edge_id or "",
            e.claim_id or "", e.payload_hash
        ))
    
    def upstream_types(self, node_id: str) -> set[str]:
        if node_id not in self.nodes:
            raise ValueError("node is not registered")
        return {self.nodes[e.from_node_id].node_type for e in self.edges.values()
                if e.to_node_id == node_id and e.from_node_id in self.nodes}

    def _lineage_neighbors(self, current: str) -> list[str]:
        """Return research-lineage neighbors with edge semantics respected."""
        neighbors=[]
        node=self.nodes[current]
        for edge in self.edges.values():
            # Most research/result edges point into the object they qualify.
            if edge.to_node_id == current and edge.from_node_id != current:
                neighbors.append(edge.from_node_id)
            # ANALYZED_FROM, USES_PROTOCOL and DERIVED_FROM point outward from
            # the current node in the lineage graph.
            if edge.from_node_id == current and edge.edge_type in {"ANALYZED_FROM","USES_PROTOCOL","DERIVED_FROM"} and edge.to_node_id != current:
                neighbors.append(edge.to_node_id)
        return neighbors

    def claim_upstream_types(self, result_id: str) -> set[str]:
        """Return lineage types reachable from a RESULT using typed edge semantics."""
        if result_id not in self.nodes or self.nodes[result_id].node_type != "RESULT":
            raise ValueError("RESULT node is not registered")
        found: set[str] = {"RESULT"}
        frontier=[result_id]
        seen={result_id}
        while frontier:
            current=frontier.pop()
            for node_id in self._lineage_neighbors(current):
                if node_id in seen or node_id not in self.nodes:
                    continue
                seen.add(node_id)
                found.add(self.nodes[node_id].node_type)
                frontier.append(node_id)
        return found

    def _upstream_nodes(self, result_id: str) -> list[GraphNode]:
        if result_id not in self.nodes or self.nodes[result_id].node_type != "RESULT":
            raise ValueError("RESULT node is not registered")
        found=[]
        frontier=[result_id]
        seen={result_id}
        while frontier:
            current=frontier.pop()
            for node_id in self._lineage_neighbors(current):
                node=self.nodes.get(node_id)
                if node is None or node_id in seen:
                    continue
                seen.add(node_id)
                found.append(node)
                frontier.append(node_id)
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
            if node.node_type=="REPLICATION":
                assessment_status=md.get("assessment_status")
                # A fixture without an assessment status is a registered
                # replication node; an explicit non-REPLICATED status blocks promotion.
                eligible_for_promotion=assessment_status in {None,"REPLICATED"}
                if eligible_for_promotion and bool(md.get("independent",False)):
                    req.add("independent_replication")
                if eligible_for_promotion and bool(md.get("criteria_registered",False)):
                    req.add("registered_replication_criteria")
            if node.node_type=="GENERALIZATION" and md.get("run_status")=="COMPLETED" and md.get("result_status")=="GENERALIZABLE":
                req.add("generalization_run")
            if node.node_type=="GENERALIZATION" and md.get("target_population_context"):
                req.add("target_population_context")
        if all(n.provenance_class and n.version and n.immutable_hash for n in all_nodes):
            req.add("complete_provenance")
        return req

    def indeterminate_requirements(self, claim_ids: set[str], result_id: str | None) -> set[str]:
        has_conflict=any(
            s.claim_id in claim_ids and s.resolution_status in {"OPEN","UNRESOLVED"}
            for s in self.contradiction_sets.values()
        )
        if result_id is not None:
            result = self.nodes.get(result_id)
            if result is None or result.node_type != "RESULT":
                raise ValueError("RESULT node is not registered")
        else:
            result = None
        has_insufficient=bool(result and result.metadata.get("insufficient_information",False))
        has_not_estimable=bool(result and result.metadata.get("qc_status")=="NOT_ESTIMABLE")
        return {"insufficient_or_conflicting_information"} if (has_conflict or has_insufficient or has_not_estimable) else set()

    def blocked_by_inference_rules(self, result_id: str, target_state: str) -> list[InferenceBlock]:
        if result_id not in self.nodes or self.nodes[result_id].node_type!="RESULT":
            raise ValueError("RESULT node is not registered")
        nodes=[self.nodes[result_id],*self._upstream_nodes(result_id)]
        blocked=[]
        for rule in self.inference_blocks.values():
            if rule.to_claim_level != target_state:
                continue
            for node in nodes:
                md=node.metadata or {}
                if node.node_type==rule.from_node_type or md.get("kind")==rule.from_node_type or md.get("inference_type")==rule.from_node_type:
                    blocked.append(rule)
                    break
        return blocked

    def register_claim(self, claim_id: str, result_id: str | None, current_state: str,
                       target_state: str, provenance_class: str, metadata: dict,
                       previous_claim_id: str | None = None) -> GraphNode:
        if claim_id in self.nodes:
            raise ValueError("claim node already registered")
        # A prior claim is recorded when supplied. Older API callers may still
        # submit a transition without a prior node; the transition is validated
        # from the declared current state and current result lineage.
        if previous_claim_id is not None:
            previous=self.nodes.get(previous_claim_id)
            if previous is None or previous.node_type!="CLAIM":
                raise ValueError("previous claim is not registered")
            stored_state=previous.metadata.get("state")
            if stored_state != current_state:
                raise ValueError("current_state does not match previous claim state")
            previous_result_id = previous.metadata.get("result_id")
            if result_id is None:
                result_id=previous_result_id
            elif previous_result_id is not None and result_id != previous_result_id:
                raise ValueError("result_id does not match previous claim lineage")
        if result_id is not None:
            result = self.nodes.get(result_id)
            if result is None or result.node_type != "RESULT":
                raise ValueError("RESULT node is not registered")
        terminal_state=target_state in {"CONTRADICTED","INDETERMINATE"}
        if not terminal_state and (target_state != "REGISTERED" or current_state != "HYPOTHESIS"):
            if not result_id:
                raise ValueError("result_id is required for result-backed claim transitions")
        linked_claim_ids={claim_id}
        if previous_claim_id:
            linked_claim_ids.add(previous_claim_id)
        requirements={"claim_registration"} if current_state=="HYPOTHESIS" and target_state=="REGISTERED" else set()
        if target_state=="CONTRADICTED":
            requirements |= self.contradiction_requirements(linked_claim_ids)
        if target_state=="INDETERMINATE":
            requirements |= self.indeterminate_requirements(linked_claim_ids,result_id)
        if result_id and not terminal_state:
            requirements=self.claim_requirements(result_id,linked_claim_ids) | requirements
        if result_id and terminal_state:
            requirements.add("RESULT")
        if result_id:
            blocked=self.blocked_by_inference_rules(result_id,target_state)
            if blocked:
                raise ValueError("inference block: "+",".join(x.rule_id for x in blocked))
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

    def require_transformation_lineage_for_result(self, result_id: str, execution_id: str) -> None:
        """Require an intact graph path from the result to its transformation execution."""
        self.require_lineage_for_result(result_id)
        transformation_ids = {
            node.node_id for node in self.nodes.values()
            if node.node_type == "TRANSFORMATION"
            and (
                node.metadata.get("execution_id") == execution_id
                or node.entity_id == execution_id
            )
        }
        if not transformation_ids:
            raise ValueError("RESULT requires TRANSFORMATION lineage")
        for run_node in self.nodes.values():
            if run_node.node_type != "ANALYSIS" or run_node.metadata.get("execution_id") != execution_id:
                continue
            reaches_result = any(
                edge.from_node_id == run_node.node_id
                and edge.to_node_id == result_id
                and edge.edge_type in {"RESULTS_IN", "DERIVED_FROM"}
                for edge in self.edges.values()
            )
            reaches_transformation = any(
                edge.from_node_id == run_node.node_id
                and edge.to_node_id in transformation_ids
                and edge.edge_type == "DERIVED_FROM"
                for edge in self.edges.values()
            )
            if reaches_result and reaches_transformation:
                return
        raise ValueError("RESULT transformation lineage is incomplete")

    def require_lineage_for_result(self, result_id: str) -> None:
        result=self.nodes.get(result_id)
        if result is None or result.node_type != "RESULT":
            raise ValueError("RESULT node is not registered")
        analysis_ids={e.from_node_id for e in self.edges.values() if e.to_node_id==result_id and e.edge_type=="RESULTS_IN"}
        if not analysis_ids:
            raise ValueError("RESULT requires ANALYSIS -> RESULT lineage")
        for analysis_id in analysis_ids:
            analysis = self.nodes.get(analysis_id)
            if analysis is None:
                raise ValueError("RESULT lineage references missing ANALYSIS node")
            if analysis.node_type != "ANALYSIS":
                raise ValueError("RESULT lineage source must be ANALYSIS")
            upstream={
                e.to_node_id for e in self.edges.values()
                if e.from_node_id==analysis_id and e.edge_type=="ANALYZED_FROM"
            }
            if not upstream:
                # Legacy persisted edge shape: tolerate DATASET/MEASUREMENT -> ANALYSIS.
                upstream={
                    e.from_node_id for e in self.edges.values()
                    if e.to_node_id==analysis_id and e.edge_type=="ANALYZED_FROM"
                }
            if any(node_id not in self.nodes for node_id in upstream):
                raise ValueError("ANALYSIS lineage references missing source node")
            if not any(self.nodes[node_id].node_type in {"DATASET","MEASUREMENT"} for node_id in upstream):
                raise ValueError("ANALYSIS requires DATASET or MEASUREMENT upstream")

def build_registry(store: SQLiteRuntimeStore | None = None) -> GraphRegistry:
    return GraphRegistry.empty(store)
