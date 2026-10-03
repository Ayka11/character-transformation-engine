"""Executable Evidence Graph boundary.

In-memory runtime contract for immutable graph nodes and typed provenance edges.
Persistence is intentionally left to the database layer.
"""
from __future__ import annotations
from dataclasses import dataclass
from copy import deepcopy
from .provenance import Provenance, ProvenanceTag, content_hash

NODE_TYPES={"OBSERVATION","MEASUREMENT","DATASET","ANALYSIS","RESULT","REPLICATION","GENERALIZATION","CLAIM","PROTOCOL","REPORT","SOURCE","TRANSFORMATION"}
EDGE_TYPES={"MEASURED_FROM","DERIVED_FROM","ANALYZED_FROM","RESULTS_IN","REPLICATES","GENERALIZES","SUPPORTS","CONTRADICTS","QUALIFIES","LIMITS","BLOCKS","DOCUMENTS","USES_PROTOCOL","CITES_SOURCE"}

class _FrozenDict(dict):
    """A JSON-compatible dictionary that prevents mutation of registered metadata."""
    def _immutable(self, *args, **kwargs):
        raise TypeError("registered graph metadata is immutable")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _immutable

    def __deepcopy__(self, memo):
        from copy import deepcopy
        return deepcopy(dict(self), memo)


class _FrozenList(list):
    """A list-compatible sequence that prevents mutation of registered metadata."""
    def _immutable(self, *args, **kwargs):
        raise TypeError("registered graph metadata is immutable")

    __setitem__ = __delitem__ = append = clear = extend = insert = pop = remove = reverse = sort = __iadd__ = __imul__ = _immutable

    def __deepcopy__(self, memo):
        from copy import deepcopy
        return deepcopy(list(self), memo)


def _freeze_metadata(value):
    if isinstance(value, dict):
        return _FrozenDict({key: _freeze_metadata(item) for key, item in value.items()})
    if isinstance(value, list):
        return _FrozenList(_freeze_metadata(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_metadata(item) for item in value)
    return value


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: str
    entity_id: str
    provenance_class: str
    version: str
    immutable_hash: str
    metadata: dict
    # Added separately so provenance/version envelope tampering can be detected
    # without changing the legacy content hash used by existing graph records.
    envelope_hash: str | None = None

@dataclass(frozen=True)
class GraphEdge:
    edge_id: str
    from_node_id: str
    to_node_id: str
    edge_type: str
    relation_status: str
    input_hash: str
    rationale: str

def register_node(node_id: str, node_type: str, entity_id: str, provenance_class: str, version: str, metadata: dict) -> GraphNode:
    for field_name, value in (
        ("node_id", node_id),
        ("node_type", node_type),
        ("entity_id", entity_id),
        ("provenance_class", provenance_class),
        ("version", version),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
    if not isinstance(metadata, dict):
        raise ValueError("node metadata must be an object")
    # Graph nodes are immutable records: detach nested metadata from caller-owned
    # dictionaries before hashing and retaining it on the dataclass.
    metadata = deepcopy(metadata)
    if node_type not in NODE_TYPES:
        raise ValueError("unsupported graph node type")
    if provenance_class not in {x.value for x in ProvenanceTag}:
        raise ValueError("unsupported provenance class")
    payload={"node_id":node_id,"node_type":node_type,"entity_id":entity_id,"metadata":metadata}
    immutable_hash = content_hash(payload)
    envelope_hash = content_hash({
        "immutable_hash": immutable_hash,
        "provenance_class": provenance_class,
        "version": version,
    })
    # Keep the public node metadata JSON-compatible but deeply immutable.
    # Frozen dict/list subclasses preserve normal read and equality behavior.
    metadata = _freeze_metadata(metadata)
    return GraphNode(
        node_id, node_type, entity_id, provenance_class, version,
        immutable_hash, metadata, envelope_hash,
    )

def register_edge(edge_id: str, from_node: GraphNode, to_node: GraphNode, edge_type: str, *, rationale: str="") -> GraphEdge:
    if not isinstance(edge_id, str) or not edge_id.strip():
        raise ValueError("edge_id must be a non-empty string")
    if not isinstance(from_node, GraphNode) or not isinstance(to_node, GraphNode):
        raise ValueError("edge endpoints must be registered graph nodes")
    if not isinstance(edge_type, str) or not edge_type.strip():
        raise ValueError("edge_type must be a non-empty string")
    if not isinstance(rationale, str):
        raise ValueError("edge rationale must be a string")
    if edge_type not in EDGE_TYPES:
        raise ValueError("unsupported graph edge type")
    if edge_type=="RESULTS_IN" and not (from_node.node_type=="ANALYSIS" and to_node.node_type=="RESULT"):
        raise ValueError("RESULTS_IN requires ANALYSIS -> RESULT")
    if edge_type=="ANALYZED_FROM":
        # Canonical lineage is ANALYSIS -> DATASET/MEASUREMENT. Accept the
        # legacy reversed call shape and normalize it at registration time.
        if from_node.node_type=="ANALYSIS":
            pass
        elif from_node.node_type in {"DATASET","MEASUREMENT"} and to_node.node_type=="ANALYSIS":
            from_node, to_node = to_node, from_node
        else:
            raise ValueError("ANALYZED_FROM requires ANALYSIS -> DATASET/MEASUREMENT")
    if edge_type=="SUPPORTS" and not (from_node.node_type=="RESULT" and to_node.node_type=="CLAIM"):
        raise ValueError("SUPPORTS requires RESULT -> CLAIM")
    payload={"edge_id":edge_id,"from":from_node.node_id,"to":to_node.node_id,"type":edge_type,"rationale":rationale}
    return GraphEdge(edge_id,from_node.node_id,to_node.node_id,edge_type,"ACTIVE",content_hash(payload),rationale)
