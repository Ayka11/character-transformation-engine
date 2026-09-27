from math import sqrt
from statistics import mean

def _rank(v):
    order=sorted(range(len(v)),key=lambda i:v[i]); r=[0]*len(v)
    for i,idx in enumerate(order,1): r[idx]=i
    return r
def _corr(a,b):
    if len(a)<2:return None
    ma,mb=mean(a),mean(b); da=[x-ma for x in a]; db=[y-mb for y in b]
    den=sqrt(sum(x*x for x in da)*sum(y*y for y in db))
    return None if den==0 else sum(x*y for x,y in zip(da,db))/den
def spearman(a,b):
    return None if len(a)!=len(b) or len(a)<2 else _corr(_rank(a),_rank(b))
def compatibility_v1(a,b):
    k=sorted(set(a)&set(b))
    return {"status":"UNKNOWN","dimensions":{}} if not k else {"status":"ESTIMATED","dimensions":{x:abs(a[x]-b[x]) for x in k}}
def compatibility_v2(a,b):
    k=sorted(set(a)&set(b))
    rho=spearman([a[x] for x in k],[b[x] for x in k]) if len(k)>=2 else None
    return {"status":"ESTIMATED" if rho is not None else "UNKNOWN","spearman":rho,"dimensions":k}
def compatibility_v3(a,b,synergy):
    pairs=[(x,y,synergy.get((x,y),synergy.get((y,x)))) for x in a for y in b]
    return {"status":"ESTIMATED" if any(p[2] is not None for p in pairs) else "UNKNOWN","pairs":[p for p in pairs if p[2] is not None]}
