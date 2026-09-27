from collections import deque
class TraitGraph:
    def __init__(self,edges:dict[str,list[str]]):
        self.edges=edges
    def downstream(self,node_id:str)->list[str]:
        seen=set(); q=deque([node_id])
        while q:
            n=q.popleft()
            for child in self.edges.get(n,[]):
                if child not in seen: seen.add(child); q.append(child)
        return list(seen)
    def find_intervention_target(self,target_id:str,blockers:dict[str,float],threshold=.4)->str|None:
        candidates=[(n,s) for n,s in blockers.items() if s<threshold and (n==target_id or n in self.downstream(target_id))]
        return min(candidates,key=lambda x:x[1])[0] if candidates else None
