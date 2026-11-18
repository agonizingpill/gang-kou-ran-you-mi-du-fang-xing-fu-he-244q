from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy import select,func
from .models import Tank,FuelSample,Transfer
from .label_models import LabelTray,LabelTrayBottle,LabelTrayCandidate
from .transfer_service import obj,get,audit
from .density_model import fit_kde
from .tray_assignment import best_and_second
from .constants import TRAY_MAX_BOTTLES,TRAY_MAX_CANDIDATES,TRAY_TIE_EPSILON

def now():return datetime.now(timezone.utc).isoformat()
def effective_density(x):return float(x.retest_density if x.retest_density is not None else x.density_15)
def bottles_of(s,tray):return s.scalars(select(LabelTrayBottle).where(LabelTrayBottle.tray_id==tray.id).order_by(LabelTrayBottle.id)).all()
def candidates_of(s,tray):return s.scalars(select(LabelTrayCandidate).where(LabelTrayCandidate.tray_id==tray.id).order_by(LabelTrayCandidate.id)).all()
def tray_view(s,tray):
    bv=[]
    for b in bottles_of(s,tray):
        x=s.get(FuelSample,b.sample_id);ot=s.get(Tank,b.original_tank_id);at=s.get(Tank,b.assigned_tank_id)if b.assigned_tank_id else None
        bv.append({**obj(b),'sample_code':x.code,'sample_status':x.status,'original_tank_code':ot.code,'original_grade':ot.grade,'density_15':float(x.density_15),'retest_density':float(x.retest_density)if x.retest_density is not None else None,'effective_density':effective_density(x),'assigned_tank_code':at.code if at else None})
    cv=[]
    for c in candidates_of(s,tray):
        t=s.get(Tank,c.tank_id);cv.append({**obj(c),'tank_code':t.code,'grade':t.grade})
    return{**obj(tray),'bottles':bv,'candidates':cv}

def register(s,p,u):
    x=LabelTray(code=p.code,note=p.note,state='draft');s.add(x);s.flush();audit(s,u,'tray_registered',x.code);return tray_view(s,x)
def editable(tray):
    if tray.state!='draft'or tray.bottles_frozen:raise HTTPException(409,'分析受理后瓶样与参考依据已固定，不能再调整瓶样')
def add_bottle(s,id,p,u):
    tray=get(s,LabelTray,id,True);editable(tray)
    x=get(s,FuelSample,p.sample_id)
    if x.reference:raise HTTPException(409,'参考样是固定比对基准，不能作为复核瓶样')
    if s.scalar(select(LabelTrayBottle.id).where(LabelTrayBottle.sample_id==x.id)):raise HTTPException(409,'该油样已登记在复核盘，一瓶只属一盘')
    if s.scalar(select(func.count()).select_from(LabelTrayBottle).where(LabelTrayBottle.tray_id==tray.id))>=TRAY_MAX_BOTTLES:raise HTTPException(409,f'每盘最多登记{TRAY_MAX_BOTTLES}瓶')
    s.add(LabelTrayBottle(tray_id=tray.id,sample_id=x.id,original_tank_id=x.tank_id));s.flush();audit(s,u,'tray_bottle_added',f'{tray.code}:{x.code}');return tray_view(s,tray)
def remove_bottle(s,id,bid,u):
    tray=get(s,LabelTray,id,True);editable(tray)
    b=get(s,LabelTrayBottle,bid,True)
    if b.tray_id!=tray.id:raise HTTPException(404,'记录不存在')
    x=s.get(FuelSample,b.sample_id);s.delete(b);audit(s,u,'tray_bottle_removed',f'{tray.code}:{x.code}');s.flush();return tray_view(s,tray)
def invalidate(tray):
    # 改候选罐后旧建议失效，须重新整盘分析；瓶样保持固定
    if tray.state!='draft':tray.state='draft';tray.suggestion=None;tray.last_error=''
def add_candidate(s,id,p,u):
    tray=get(s,LabelTray,id,True)
    if tray.state=='adopted':raise HTTPException(409,'已采纳归属冻结，候选罐不可再改')
    get(s,Tank,p.tank_id)
    if s.scalar(select(LabelTrayCandidate.id).where(LabelTrayCandidate.tray_id==tray.id,LabelTrayCandidate.tank_id==p.tank_id)):raise HTTPException(409,'候选罐已在盘内')
    if s.scalar(select(func.count()).select_from(LabelTrayCandidate).where(LabelTrayCandidate.tray_id==tray.id))>=TRAY_MAX_CANDIDATES:raise HTTPException(409,f'每盘最多{TRAY_MAX_CANDIDATES}个候选罐')
    s.add(LabelTrayCandidate(tray_id=tray.id,tank_id=p.tank_id));invalidate(tray);s.flush();audit(s,u,'tray_candidates_updated',tray.code);return tray_view(s,tray)
def remove_candidate(s,id,cid,u):
    tray=get(s,LabelTray,id,True)
    if tray.state=='adopted':raise HTTPException(409,'已采纳归属冻结，候选罐不可再改')
    c=get(s,LabelTrayCandidate,cid,True)
    if c.tray_id!=tray.id:raise HTTPException(404,'记录不存在')
    s.delete(c);invalidate(tray);s.flush();audit(s,u,'tray_candidates_updated',tray.code);return tray_view(s,tray)

def queue_analysis(s,id,u):
    tray=get(s,LabelTray,id,True)
    if tray.state=='adopted':raise HTTPException(409,'已采纳归属冻结，不能重新核算')
    if tray.state not in('draft','queued','failed'):raise HTTPException(409,'请先调整候选罐使旧建议失效，再重新受理分析')
    bottles=bottles_of(s,tray);candidates=candidates_of(s,tray)
    if not bottles:raise HTTPException(409,'复核盘至少登记一瓶油样')
    if not candidates:raise HTTPException(409,'复核盘至少登记一个候选储罐')
    snap={'grades':{}}
    for g in sorted({s.get(Tank,c.tank_id).grade for c in candidates}):
        refs=s.scalars(select(FuelSample).join(Tank,FuelSample.tank_id==Tank.id).where(FuelSample.reference==True,Tank.grade==g).order_by(FuelSample.id)).all()
        if len(refs)<20:raise HTTPException(409,f'{g}等级合格参考样不足20条，不能受理整盘分析')
        snap['grades'][g]={'codes':[x.code for x in refs],'values':[float(x.density_15)for x in refs],'count':len(refs)}
    snap.update({'bandwidth':.3,'kernel':'gaussian','threshold_quantile':.05,'standardized':True,'accepted_by':u['email'],'at':now(),'fit_scope':'reference=True且同燃油等级；瓶样不参与拟合'})
    tray.reference_snapshot=snap;tray.suggestion=None;tray.last_error='';tray.state='queued';tray.bottles_frozen=True
    audit(s,u,'tray_analysis_queued',tray.code);return tray_view(s,tray)

def analyze(s,tray):
    snap=tray.reference_snapshot
    if not snap:raise ValueError('复核盘缺少参考依据快照，不能核算')
    bottles=bottles_of(s,tray);candidates=candidates_of(s,tray)
    if not bottles or not candidates:raise ValueError('复核盘瓶样或候选罐为空')
    models={g:dict(zip(('scaler','model','threshold'),fit_kde(gs['values'])))for g,gs in snap['grades'].items()}
    tanks={c.tank_id:s.get(Tank,c.tank_id)for c in candidates}
    samples={b.sample_id:s.get(FuelSample,b.sample_id)for b in bottles}
    scores=[];eligible=[];matrix={}
    for b in bottles:
        d=effective_density(samples[b.sample_id]);rs=[];re_=[];mrow={}
        for c in candidates:
            t=tanks[c.tank_id];m=models[t.grade]
            score=float(m['model'].score_samples(m['scaler'].transform([[d]]))[0])
            rs.append(score);re_.append(score>=m['threshold'])
            mrow[str(t.id)]={'score':round(score,6),'threshold':round(m['threshold'],6),'eligible':score>=m['threshold']}
        scores.append(rs);eligible.append(re_);matrix[str(b.sample_id)]=mrow
    best,second=best_and_second(scores,eligible)
    def scheme_dict(sol):
        assigns=[{'sample_id':bottles[i].sample_id,'sample_code':samples[bottles[i].sample_id].code,'tank_id':tanks[candidates[j].tank_id].id,'tank_code':tanks[candidates[j].tank_id].code,'grade':tanks[candidates[j].tank_id].grade,'score':round(scores[i][j],6)}for i,j in sorted(sol['assign'].items())]
        un=[{'sample_id':bottles[i].sample_id,'sample_code':samples[bottles[i].sample_id].code}for i in range(len(bottles))if i not in sol['assign']]
        return{'assignments':assigns,'unassigned':un,'count':sol['count'],'total_score':round(sol['total'],6)}
    schemes=[scheme_dict(best)];near=False
    if second is not None:
        schemes.append(scheme_dict(second));near=second['count']==best['count']and abs(best['total']-second['total'])<=TRAY_TIE_EPSILON
    for i,b in enumerate(bottles):
        j=best['assign'].get(i);b.assigned_tank_id=candidates[j].tank_id if j is not None else None;b.score=scores[i][j]if j is not None else None
    tray.suggestion={'schemes':schemes,'matrix':matrix,'thresholds':{g:round(m['threshold'],6)for g,m in models.items()},'tie_epsilon':TRAY_TIE_EPSILON,'near_tie':near,'computed_at':now()}
    tray.state='review'if near else'suggested';return tray.suggestion

def adopt(s,id,p,u):
    tray=get(s,LabelTray,id,True)
    if tray.state=='adopted':return tray_view(s,tray)
    if tray.state not in('suggested','review'):raise HTTPException(409,'仅核算完成待采纳的复核盘可由主管采纳')
    sug=tray.suggestion
    if not sug or not sug.get('schemes'):raise HTTPException(409,'旧建议已失效，请重新整盘分析')
    if tray.state=='review':
        if p.scheme_index is None:raise HTTPException(409,'近似并列须人工核签选择归属方案')
        if len(p.sign_note.strip())<8:raise HTTPException(409,'人工核签须填写至少8字核签依据')
        idx=p.scheme_index
    else:
        if p.scheme_index not in(None,0):raise HTTPException(409,'唯一最优方案直接采纳，不能改选其他方案')
        idx=0
    if idx>=len(sug['schemes']):raise HTTPException(409,'方案序号超出候选范围')
    scheme=sug['schemes'][idx]
    bottles=bottles_of(s,tray);sample_ids=[b.sample_id for b in bottles]
    samples={x.id:x for x in s.scalars(select(FuelSample).where(FuelSample.id.in_(sample_ids)).order_by(FuelSample.id).with_for_update().execution_options(populate_existing=True))}
    used=s.scalars(select(Transfer).where(Transfer.sample_id.in_(sample_ids),Transfer.status=='released').order_by(Transfer.id).with_for_update().execution_options(populate_existing=True)).all()
    if used:raise HTTPException(409,'瓶样已用于放行调拨 '+','.join(x.code for x in used)+'，整盘拒绝归属变更')
    recalled=[]
    for tr in s.scalars(select(Transfer).where(Transfer.sample_id.in_(sample_ids),Transfer.status=='requested').order_by(Transfer.id).with_for_update().execution_options(populate_existing=True)):
        tr.status='recalled';recalled.append(tr.code)
    amap={a['sample_id']:a for a in scheme['assignments']};changes=[]
    for b in bottles:
        a=amap.get(b.sample_id);b.assigned_tank_id=a['tank_id']if a else None;b.score=a['score']if a else None
        x=samples[b.sample_id]
        if a and x.tank_id!=a['tank_id']:
            old=s.get(Tank,x.tank_id);x.tank_id=a['tank_id'];changes.append({'sample_code':x.code,'from_tank':old.code,'to_tank':a['tank_code'],'score':a['score']})
    tray.state='adopted';tray.adopted_by=u['email']
    tray.adopted_snapshot={'tray_code':tray.code,'scheme_index':idx,'scheme':scheme,'changes':changes,'recalled_transfers':recalled,'sign_note':p.sign_note,'adopted_by':u['email'],'at':now()}
    audit(s,u,'tray_adopted',f"{tray.code} 方案{idx+1} 换签{len(changes)}瓶 撤回{len(recalled)}单");return tray_view(s,tray)
