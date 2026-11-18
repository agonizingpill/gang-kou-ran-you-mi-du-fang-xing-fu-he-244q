import os,sys,random
os.environ['DATABASE_URL']='sqlite:////tmp/label_test.db'
os.environ['REDIS_URL']='redis://localhost:6379/0'
if os.path.exists('/tmp/label_test.db'):os.remove('/tmp/label_test.db')
sys.path.insert(0,'/workspace/backend')
from src.database import Base,engine,Session
from src import models,label_models,receipt_models,harbor_models
from src.models import Tank,FuelSample,Transfer
from src.label_models import LabelTray,LabelTrayBottle,LabelTrayCandidate
from src.label_schemas import TrayIn,BottleIn,CandidateIn,AdoptIn
from src import label_service as svc
from fastapi import HTTPException

Base.metadata.create_all(engine)
U={'email':'admin@chenggang.local','role':'admin'}
C={'email':'chemist@chenggang.local','role':'chemist'}
fails=[]
def check(name,cond):
    print(('PASS' if cond else 'FAIL'),name)
    if not cond:fails.append(name)
def expect409(name,fn,frag=''):
    try:fn();check(name+' [should 409]',False)
    except HTTPException as e:
        ok=e.status_code==409 and (not frag or frag in str(e.detail));check(name,ok)
        if not ok:print('   detail:',e.status_code,e.detail)

# seed tanks + references (mirrors seed_demo distributions)
with Session.begin() as s:
    for code,grade,liters in [('TK-06','VLSFO',50000),('TK-08','VLSFO',20000),('TK-M01','MGO',35000)]:
        s.add(Tank(code=code,grade=grade,liters=liters,status='active'))
    s.flush();tanks={x.code:x for x in s.query(Tank).all()};rng=random.Random(42)
    for grade,tank,mu,sigma in [('VLSFO','TK-06',975,8),('MGO','TK-M01',850,6)]:
        for i in range(60):
            s.add(FuelSample(code=f'REF-{grade}-{i:03}',tank_id=tanks[tank].id,density_15=round(rng.gauss(mu,sigma),3),viscosity=130,sulfur=.1,status='qualified',reference=True,evidence='',retest_note=''))
    # business samples: FS-A true VLSFO labeled TK-06; FS-B is MGO oil mislabeled TK-06; FS-C VLSFO in TK-08; FS-D way off
    for code,tank,d in [('FS-A','TK-06',980),('FS-B','TK-06',852),('FS-C','TK-08',976),('FS-D','TK-06',1200),('FS-E','TK-08',979),('FS-F','TK-08',977),('FS-G','TK-08',978)]:
        s.add(FuelSample(code=code,tank_id=tanks[tank].id,density_15=d,viscosity=130,sulfur=.3,status='qualified',reference=False,evidence='',retest_note=''))

def analyze_queued(tray_id):
    # worker-equivalent: lock, check queued, analyze
    with Session.begin() as s:
        tray=s.get(LabelTray,tray_id)
        assert tray.state=='queued',tray.state
        svc.analyze(s,tray)

# ---------- scenario 1: clear swap, adopt recalls requested transfer ----------
with Session.begin() as s:
    t=svc.register(s,TrayIn(code='LT-1',note='同盘疑签'),C)
    tid1=t['id']
with Session.begin() as s:
    svc.add_bottle(s,tid1,BottleIn(sample_id=s.query(FuelSample).filter_by(code='FS-A').one().id),C)
    svc.add_bottle(s,tid1,BottleIn(sample_id=s.query(FuelSample).filter_by(code='FS-B').one().id),C)
    svc.add_candidate(s,tid1,CandidateIn(tank_id=s.query(Tank).filter_by(code='TK-06').one().id),C)
    v=svc.add_candidate(s,tid1,CandidateIn(tank_id=s.query(Tank).filter_by(code='TK-M01').one().id),C)
    check('tray draft with 2 bottles 2 candidates',v['state']=='draft' and len(v['bottles'])==2 and len(v['candidates'])==2)
with Session.begin() as s:
    v=svc.queue_analysis(s,tid1,C)
    check('queued + bottles frozen + snapshot 2 grades',v['state']=='queued' and v['bottles_frozen'] and set(v['reference_snapshot']['grades'])=={'VLSFO','MGO'})
    snap_counts={g:v['reference_snapshot']['grades'][g]['count'] for g in v['reference_snapshot']['grades']}
    check('snapshot 60 refs per grade',snap_counts=={'VLSFO':60,'MGO':60})
with Session.begin() as s:
    expect409('bottle add blocked after analysis accepted',lambda:svc.add_bottle(s,tid1,BottleIn(sample_id=s.query(FuelSample).filter_by(code='FS-C').one().id),C),'固定')
analyze_queued(tid1)
with Session() as s:
    v=svc.tray_view(s,s.get(LabelTray,tid1))
    check('state suggested (clear margin)',v['state']=='suggested')
    best=v['suggestion']['schemes'][0]
    amap={a['sample_code']:a['tank_code'] for a in best['assignments']}
    check('FS-A->TK-06 FS-B->TK-M01',amap=={'FS-A':'TK-06','FS-B':'TK-M01'})
    check('both assigned, none unassigned',best['count']==2 and not best['unassigned'])
    check('matrix present with eligibility',v['suggestion']['matrix'] and all('eligible' in c for row in v['suggestion']['matrix'].values() for c in row.values()))
    fsb=s.query(FuelSample).filter_by(code='FS-B').one()
    check('analysis does not mutate sample tank',fsb.tank_id==s.query(Tank).filter_by(code='TK-06').one().id)
# requested transfer on FS-B, then adopt -> recalled
with Session.begin() as s:
    fsb=s.query(FuelSample).filter_by(code='FS-B').one()
    s.add(Transfer(code='TR-PEND',sample_id=fsb.id,liters=100,vessel='澄海17',status='requested',grade_snapshot='VLSFO',density_snapshot=852,viscosity_snapshot=130,sulfur_snapshot=.3,released_by=''))
with Session.begin() as s:
    v=svc.adopt(s,tid1,AdoptIn(),U)
    check('adopted',v['state']=='adopted')
    check('snapshot: 1 change FS-B 06->M01',len(v['adopted_snapshot']['changes'])==1 and v['adopted_snapshot']['changes'][0]['sample_code']=='FS-B' and v['adopted_snapshot']['changes'][0]['to_tank']=='TK-M01')
    check('snapshot: TR-PEND recalled',v['adopted_snapshot']['recalled_transfers']==['TR-PEND'])
    fsb=s.query(FuelSample).filter_by(code='FS-B').one()
    check('FS-B tank now TK-M01',fsb.tank_id==s.query(Tank).filter_by(code='TK-M01').one().id)
    check('FS-B density untouched',float(fsb.density_15)==852)
    tr=s.query(Transfer).filter_by(code='TR-PEND').one()
    check('transfer recalled',tr.status=='recalled')
with Session.begin() as s:
    v=svc.adopt(s,tid1,AdoptIn(),U)
    check('adopt retry idempotent, still 1 change',v['state']=='adopted' and len(v['adopted_snapshot']['changes'])==1)
with Session.begin() as s:
    expect409('adopted tray frozen for candidates',lambda:svc.add_candidate(s,tid1,CandidateIn(tank_id=s.query(Tank).filter_by(code='TK-08').one().id),C),'冻结')
    expect409('adopted tray cannot re-analyze',lambda:svc.queue_analysis(s,tid1,C),'冻结')

# ---------- scenario 2: candidate change invalidates suggestion ----------
with Session.begin() as s:
    t=svc.register(s,TrayIn(code='LT-2'),C);tid2=t['id']
    svc.add_bottle(s,tid2,BottleIn(sample_id=s.query(FuelSample).filter_by(code='FS-C').one().id),C)
    svc.add_candidate(s,tid2,CandidateIn(tank_id=s.query(Tank).filter_by(code='TK-06').one().id),C)
    svc.queue_analysis(s,tid2,C)
analyze_queued(tid2)
with Session() as s:
    check('LT-2 suggested',s.get(LabelTray,tid2).state=='suggested')
with Session.begin() as s:
    v=svc.add_candidate(s,tid2,CandidateIn(tank_id=s.query(Tank).filter_by(code='TK-08').one().id),C)
    check('candidate change invalidates old suggestion',v['state']=='draft' and v['suggestion'] is None)
    check('bottles stay frozen after invalidation',v['bottles_frozen'])
with Session.begin() as s:
    expect409('bottle still frozen after candidate change',lambda:svc.add_bottle(s,tid2,BottleIn(sample_id=s.query(FuelSample).filter_by(code='FS-E').one().id),C),'固定')

# ---------- scenario 3: near-tie same-grade candidates -> review -> manual sign ----------
# LT-2 now has FS-C (VLSFO ~976) and candidates TK-06 + TK-08 (both VLSFO): equal scores -> tie
with Session.begin() as s:
    svc.queue_analysis(s,tid2,C)
analyze_queued(tid2)
with Session() as s:
    v=svc.tray_view(s,s.get(LabelTray,tid2))
    check('same-grade candidates -> near tie review',v['state']=='review' and v['suggestion']['near_tie'])
    check('two schemes offered',len(v['suggestion']['schemes'])==2)
with Session.begin() as s:
    expect409('review adopt needs scheme pick',lambda:svc.adopt(s,tid2,AdoptIn(),U),'人工核签')
with Session.begin() as s:
    expect409('review adopt needs >=8 char note',lambda:svc.adopt(s,tid2,AdoptIn(scheme_index=1,sign_note='短'),U),'至少8字')
with Session.begin() as s:
    v=svc.adopt(s,tid2,AdoptIn(scheme_index=1,sign_note='已核对罐区取样位置与班次记录'),U)
    check('manual sign adopts scheme 2',v['state']=='adopted' and v['adopted_snapshot']['scheme_index']==1)

# ---------- scenario 4: unassignable bottle kept, no force-match ----------
with Session.begin() as s:
    t=svc.register(s,TrayIn(code='LT-3'),C);tid3=t['id']
    svc.add_bottle(s,tid3,BottleIn(sample_id=s.query(FuelSample).filter_by(code='FS-D').one().id),C)  # density 1200, off every grade
    svc.add_candidate(s,tid3,CandidateIn(tank_id=s.query(Tank).filter_by(code='TK-06').one().id),C)
    svc.add_candidate(s,tid3,CandidateIn(tank_id=s.query(Tank).filter_by(code='TK-M01').one().id),C)
    svc.queue_analysis(s,tid3,C)
analyze_queued(tid3)
with Session() as s:
    v=svc.tray_view(s,s.get(LabelTray,tid3))
    best=v['suggestion']['schemes'][0]
    check('off-distribution bottle unassigned',best['count']==0 and best['unassigned'][0]['sample_code']=='FS-D')
    check('bottle keeps original label in view',v['bottles'][0]['assigned_tank_code'] is None)

# ---------- scenario 5: any released bottle rejects whole tray ----------
with Session.begin() as s:
    fse=s.query(FuelSample).filter_by(code='FS-E').one()
    s.add(Transfer(code='TR-DONE',sample_id=fse.id,liters=50,vessel='澄海18',status='released',grade_snapshot='VLSFO',density_snapshot=979,viscosity_snapshot=130,sulfur_snapshot=.3,released_by='admin@chenggang.local'))
with Session.begin() as s:
    t=svc.register(s,TrayIn(code='LT-4'),C);tid4=t['id']
    svc.add_bottle(s,tid4,BottleIn(sample_id=s.query(FuelSample).filter_by(code='FS-E').one().id),C)
    svc.add_bottle(s,tid4,BottleIn(sample_id=s.query(FuelSample).filter_by(code='FS-F').one().id),C)
    svc.add_candidate(s,tid4,CandidateIn(tank_id=s.query(Tank).filter_by(code='TK-06').one().id),C)
    svc.queue_analysis(s,tid4,C)
analyze_queued(tid4)
with Session.begin() as s:
    expect409('released bottle rejects whole tray',lambda:svc.adopt(s,tid4,AdoptIn(scheme_index=0,sign_note='罐区班次复核确认'),U),'整盘拒绝')
with Session() as s:
    fsf=s.query(FuelSample).filter_by(code='FS-F').one()
    check('no bottle changed after rejection',fsf.tank_id==s.query(Tank).filter_by(code='TK-08').one().id)
    check('tray not adopted',s.get(LabelTray,tid4).state=='review')

# ---------- scenario 6: integrity guards ----------
with Session.begin() as s:
    t=svc.register(s,TrayIn(code='LT-6'),C)
    expect409('reference sample cannot be bottle',lambda:svc.add_bottle(s,t['id'],BottleIn(sample_id=s.query(FuelSample).filter_by(code='REF-VLSFO-000').one().id),C),'参考样')
with Session.begin() as s:
    t=svc.register(s,TrayIn(code='LT-5'),C);tid5=t['id']
    expect409('one sample one tray',lambda:svc.add_bottle(s,tid5,BottleIn(sample_id=s.query(FuelSample).filter_by(code='FS-F').one().id),C),'一瓶只属一盘')
with Session.begin() as s:
    expect409('analyze needs bottles',lambda:svc.queue_analysis(s,tid5,C),'至少登记一瓶')
with Session.begin() as s:
    svc.add_bottle(s,tid5,BottleIn(sample_id=s.query(FuelSample).filter_by(code='FS-G').one().id),C)
with Session.begin() as s:
    expect409('analyze needs candidates',lambda:svc.queue_analysis(s,tid5,C),'至少登记一个候选')
# failed -> recover from original tray
with Session.begin() as s:
    tray=s.get(LabelTray,tid5);tray.state='failed';tray.last_error='模拟中断'
with Session.begin() as s:
    svc.add_candidate(s,tid5,CandidateIn(tank_id=s.query(Tank).filter_by(code='TK-06').one().id),C)
with Session.begin() as s:
    v=svc.queue_analysis(s,tid5,C)
    check('recover from failed re-queues',v['state']=='queued')

print('FAILURES:',fails if fails else 'none')
sys.exit(1 if fails else 0)
