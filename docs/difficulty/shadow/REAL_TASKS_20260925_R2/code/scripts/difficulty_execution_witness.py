"""Bounded interpreter for this one manually encoded binary-search exercise; no eval/exec."""
import hashlib
KNOWN_CODE='''l = 0
r = len(a) - 1
while l < r:
    m = (l + r) // 2
    if a[m] < t:
        l = m
    else:
        r = m
return l'''

def trace(a,t):
    if not a or sorted(a)!=a:raise ValueError('Sorted nonempty input required')
    l,r=0,len(a)-1;seen=set();steps=[]
    expected=next((i for i,x in enumerate(a) if x>=t),len(a))
    while l<r:
        if (l,r) in seen:
            return dict(a=a,t=t,expected_return=expected,status='nontermination_repeated_state',actual_return=None,trace=steps)
        seen.add((l,r));m=(l+r)//2;steps.append(dict(l=l,r=r,m=m,value=a[m]))
        if a[m]<t:l=m
        else:r=m
    return dict(a=a,t=t,expected_return=expected,status='returned',actual_return=l,trace=steps)

def witness(question):
    if KNOWN_CODE not in question:raise ValueError('Witness supports only the exact known program')
    return dict(question_sha256=hashlib.sha256(question.encode()).hexdigest(),
        scope='Exact supplied program; examples only, not execution of model code or full repair verification',
        examples=[trace([1,2],2),trace([1],2),trace([2,3],2)])
