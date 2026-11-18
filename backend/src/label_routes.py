import os
from fastapi import APIRouter,Depends
from redis import Redis
from sqlalchemy import select
from .database import Session
from .security import current,allow
from .label_models import LabelTray
from .label_schemas import TrayIn,BottleIn,CandidateIn,AdoptIn
from . import label_service as svc
router=APIRouter()
r=Redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'),decode_responses=True)
@router.get('/label-trays')
def trays(u=Depends(current)):
    with Session() as s:return [svc.tray_view(s,x)for x in s.scalars(select(LabelTray).order_by(LabelTray.id.desc()))]
@router.post('/label-trays')
def create(p:TrayIn,u=Depends(current)):
    allow(u,'admin','chemist')
    with Session.begin() as s:return svc.register(s,p,u)
@router.post('/label-trays/{id}/bottles')
def bottle_add(id:int,p:BottleIn,u=Depends(current)):
    allow(u,'admin','chemist')
    with Session.begin() as s:return svc.add_bottle(s,id,p,u)
@router.delete('/label-trays/{id}/bottles/{bid}')
def bottle_remove(id:int,bid:int,u=Depends(current)):
    allow(u,'admin','chemist')
    with Session.begin() as s:return svc.remove_bottle(s,id,bid,u)
@router.post('/label-trays/{id}/candidates')
def candidate_add(id:int,p:CandidateIn,u=Depends(current)):
    allow(u,'admin','chemist')
    with Session.begin() as s:return svc.add_candidate(s,id,p,u)
@router.delete('/label-trays/{id}/candidates/{cid}')
def candidate_remove(id:int,cid:int,u=Depends(current)):
    allow(u,'admin','chemist')
    with Session.begin() as s:return svc.remove_candidate(s,id,cid,u)
@router.post('/label-trays/{id}/analyze')
def analyze(id:int,u=Depends(current)):
    allow(u,'admin','chemist')
    with Session.begin() as s:svc.queue_analysis(s,id,u)
    r.rpush('tray-analysis',id);return {'status':'queued'}
@router.post('/label-trays/{id}/adopt')
def adopt(id:int,p:AdoptIn,u=Depends(current)):
    allow(u,'admin')
    with Session.begin() as s:return svc.adopt(s,id,p,u)
