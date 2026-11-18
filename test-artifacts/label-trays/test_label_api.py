import os,sys
os.environ['DATABASE_URL']='sqlite:////tmp/label_api.db'
os.environ['REDIS_URL']='redis://localhost:6379/0'
os.environ['SEED_DEMO']='true'
os.environ['JWT_SECRET']='test-secret'
if os.path.exists('/tmp/label_api.db'):os.remove('/tmp/label_api.db')
sys.path.insert(0,'/workspace/backend')
class FakeRedis:
    def __init__(self):self.q={}
    def rpush(self,k,v):self.q.setdefault(k,[]).append(v)
    def ping(self):return True
import src.main as main
import src.label_routes as lr
main.r=FakeRedis();lr.r=main.r
from fastapi.testclient import TestClient
from src.label_models import LabelTray
from src.database import Session
from src import label_service as svc

fails=[]
def check(name,cond):
    print(('PASS' if cond else 'FAIL'),name)
    if not cond:fails.append(name)

with TestClient(main.app) as c:
    def tok(email):
        r=c.post('/auth/login',json={'email':email,'password':'Harbor2026!'})
        assert r.status_code==200,r.text
        return{'Authorization':'Bearer '+r.json()['token']}
    admin=tok('admin@chenggang.local');chem=tok('chemist@chenggang.local');view=tok('viewer@chenggang.local')
    r=c.get('/label-trays',headers=view);check('viewer can list trays',r.status_code==200 and r.json()==[])
    r=c.post('/label-trays',json={'code':'LT-API-1','note':'同盘疑签测试'},headers=view);check('viewer cannot create tray',r.status_code==403)
    r=c.post('/label-trays',json={'code':'LT-API-1','note':'同盘疑签测试'},headers=chem);check('chemist creates tray',r.status_code==200 and r.json()['state']=='draft');tid=r.json()['id']
    r=c.post('/label-trays',json={'code':'LT-API-1'},headers=chem);check('duplicate tray code 409',r.status_code==409)
    samples=c.get('/samples',headers=chem).json()
    tanks=c.get('/tanks',headers=chem).json()
    s1=next(x for x in samples if x['code']=='FS-20261117-01');s2=next(x for x in samples if x['code']=='FS-MGO-01')
    tk06=next(x for x in tanks if x['code']=='TK-06');tkm=next(x for x in tanks if x['code']=='TK-M01')
    r=c.post(f'/label-trays/{tid}/bottles',json={'sample_id':s1['id']},headers=chem);check('add bottle 1',r.status_code==200 and len(r.json()['bottles'])==1)
    r=c.post(f'/label-trays/{tid}/bottles',json={'sample_id':s2['id']},headers=chem);check('add bottle 2',r.status_code==200)
    r=c.post(f'/label-trays/{tid}/bottles',json={'sample_id':s2['id']},headers=chem);check('duplicate bottle 409',r.status_code==409)
    r=c.post(f'/label-trays/{tid}/candidates',json={'tank_id':tk06['id']},headers=chem);check('add candidate TK-06',r.status_code==200)
    r=c.post(f'/label-trays/{tid}/candidates',json={'tank_id':tkm['id']},headers=chem);check('add candidate TK-M01',r.status_code==200)
    r=c.post(f'/label-trays/{tid}/candidates',json={'tank_id':tkm['id']},headers=chem);check('duplicate candidate 409',r.status_code==409)
    r=c.post(f'/label-trays/{tid}/analyze',headers=chem);check('analyze queued',r.status_code==200 and r.json()['status']=='queued')
    check('redis queue got tray id',main.r.q.get('tray-analysis')==[tid])
    # worker equivalent
    with Session.begin() as s:
        tray=s.get(LabelTray,tid);svc.analyze(s,tray)
    r=c.get('/label-trays',headers=admin);tray=r.json()[0]
    check('tray suggested after worker',tray['state']=='suggested')
    best=tray['suggestion']['schemes'][0]
    amap={a['sample_code']:a['tank_code'] for a in best['assignments']}
    check('API: FS-20261117-01->TK-06, FS-MGO-01->TK-M01',amap=={'FS-20261117-01':'TK-06','FS-MGO-01':'TK-M01'})
    r=c.post(f'/label-trays/{tid}/adopt',json={},headers=chem);check('chemist cannot adopt',r.status_code==403)
    r=c.post(f'/label-trays/{tid}/adopt',json={},headers=admin);check('admin adopts',r.status_code==200 and r.json()['state']=='adopted')
    r=c.post(f'/label-trays/{tid}/adopt',json={},headers=admin);check('adopt retry idempotent',r.status_code==200 and r.json()['state']=='adopted')
    # FS-MGO-01 was labeled TK-M01 already; FS-20261117-01 stays TK-06 -> zero changes expected
    check('no label changes needed',r.json()['adopted_snapshot']['changes']==[])
    # audit recorded
    acts=[a['action'] for a in c.get('/audit',headers=admin).json()]
    check('audit has tray actions','tray_registered' in acts and 'tray_analysis_queued' in acts and 'tray_adopted' in acts)
    # unauthenticated
    r=c.get('/label-trays');check('unauthenticated 401',r.status_code==401)
print('FAILURES:',fails if fails else 'none')
sys.exit(1 if fails else 0)
