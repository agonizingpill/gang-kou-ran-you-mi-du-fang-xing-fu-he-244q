import sys
sys.path.insert(0,'/workspace/backend/src')
from tray_assignment import solve,best_and_second

fails=[]
def check(name,cond):
    print(('PASS' if cond else 'FAIL'),name)
    if not cond:fails.append(name)

# 1. clear 2x2 assignment: bottle0->tank1, bottle1->tank0
s=[[-1.0,-0.5],[-0.4,-3.0]];e=[[True,True],[True,True]]
r=solve(s,e)
check('clear assignment',r['assign']=={0:1,1:0} and r['count']==2 and abs(r['total']+0.9)<1e-9)

# 2. ineligible bottle stays unassigned (no force-match)
s=[[-5.0,-0.5],[-0.4,-3.0]];e=[[False,True],[True,False]]
r=solve(s,e)
check('unassignable kept',r['assign']=={0:1,1:0} and r['count']==2)
s=[[-5.0,-5.0],[-0.4,-3.0]];e=[[False,False],[True,True]]
r=solve(s,e)
check('fully ineligible bottle unassigned',r['assign']=={1:0} and r['count']==1)

# 3. global beats greedy: greedy per-bottle max would both pick tank0
s=[[-0.1,-0.9],[-0.2,-2.0]];e=[[True,True],[True,True]]
r=solve(s,e)
check('global not greedy',r['assign']=={0:1,1:0} and abs(r['total']+1.1)<1e-9)

# 4. fewer tanks than bottles: one left unassigned
s=[[-0.1],[-0.2]];e=[[True],[True]]
r=solve(s,e)
check('rectangular one unassigned',r['count']==1 and r['assign']=={0:0})

# 5. second best distinct scheme
s=[[-1.0,-1.2],[-0.9,-3.0]];e=[[True,True],[True,True]]
b,sec=best_and_second(s,e)
check('best',b['assign']=={0:1,1:0})
check('second exists',sec is not None and sec['count']==2 and sec['assign']!={0:1,1:0})
check('second is swap',sec['assign']=={0:0,1:1} and abs(sec['total']+4.0)<1e-9)

# 6. no eligible edges: empty scheme, no second
b,sec=best_and_second([[1.0]],[[False]])
check('empty best',b['count']==0 and b['assign']=={})
check('no second',sec is None)

# 7. determinism on exact ties
s=[[-1.0,-1.0],[-1.0,-1.0]];e=[[True,True],[True,True]]
r1=solve(s,e);r2=solve(s,e)
check('deterministic',r1==r2)

# 8. 8x8 scale performance sanity + correctness
import random,time
rng=random.Random(1)
s=[[rng.uniform(-3,0)for _ in range(8)]for _ in range(8)];e=[[True]*8 for _ in range(8)]
t=time.time();r=solve(s,e);dt=time.time()-t
check('8x8 count',r['count']==8)
check('8x8 fast',dt<2)
# brute force verify
import itertools
best=None
for perm in itertools.permutations(range(8)):
    tot=sum(s[i][perm[i]]for i in range(8))
    if best is None or tot>best:best=tot
check('8x8 optimal',abs(r['total']-best)<1e-9)

# 9. second-best via forbidden edges matches brute force (4x4 with skips allowed)
rng=random.Random(7)
s=[[rng.uniform(-3,0)for _ in range(4)]for _ in range(4)];e=[[rng.random()>.2 for _ in range(4)]for _ in range(4)]
b,sec=best_and_second(s,e)
schemes={}
for mask_bits in itertools.product(range(5),repeat=4):
    # each bottle: skip or take tank 0..3
    assign={};used=set();ok=True
    for i,j in enumerate(mask_bits):
        if j==4:continue
        if j in used or not e[i][j]:ok=False;break
        assign[i]=j;used.add(j)
    if not ok:continue
    key=tuple(sorted(assign.items()))
    schemes[key]=(len(assign),sum(s[i][j]for i,j in assign.items()))
ranked=sorted(schemes.items(),key=lambda kv:(-kv[1][0],-kv[1][1]))
top1,top2=ranked[0],ranked[1]
check('bf best count',b['count']==top1[1][0] and abs(b['total']-top1[1][1])<1e-9)
check('bf best shape',tuple(sorted(b['assign'].items()))==top1[0])
if len(ranked)>1:
    check('bf second',sec is not None and sec['count']==top2[1][0] and abs(sec['total']-top2[1][1])<1e-9 and tuple(sorted(sec['assign'].items()))==top2[0])

print('FAILURES:',fails if fails else 'none')
sys.exit(1 if fails else 0)
