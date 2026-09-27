from collections import deque
from dataclasses import dataclass

@dataclass(frozen=True)
class InterventionTarget:
    requested_trait: str
    selected_target: str | None
    reason: str
    score: float | None

class TraitGraph:
    def __init__(self, edges: dict[str, list[str]]):
        self.edges = edges

    def downstream(self, node_id: str) -> list[str]:
        seen = set()
        q = deque([node_id])
        while q:
            n = q.popleft()
            for child in self.edges.get(n, []):
                if child not in seen:
                    seen.add(child)
                    q.append(child)
        return list(seen)

    def find_intervention_target(
        self,
        target_id: str,
        blockers: dict[str, float],
        threshold: float = 4.0,
    ) -> str | None:
        candidates = [
            (n, s) for n, s in blockers.items()
            if s < threshold and (n == target_id or n in self.downstream(target_id))
        ]
        return min(candidates, key=lambda x: x[1])[0] if candidates else None

    def resolve_intervention_target(
        self,
        target_id: str,
        blockers: dict[str, float],
        threshold: float = 4.0,
    ) -> InterventionTarget:
        selected = self.find_intervention_target(target_id, blockers, threshold)
        if selected is None:
            return InterventionTarget(
                target_id, None,
                "No eligible low-scoring target found in requested trait graph",
                None,
            )
        return InterventionTarget(
            target_id, selected,
            "Selected lowest-scoring eligible node in target/downstream graph",
            blockers[selected],
        )
