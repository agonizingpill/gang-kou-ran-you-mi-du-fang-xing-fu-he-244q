"""Tray label-swap review: candidate tanks, frozen reference basis, whole-tray attribution."""
from sqlalchemy import String,Float,Boolean,ForeignKey,JSON,CheckConstraint,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
class LabelTray(Base):
    __tablename__='label_trays'
    __table_args__=(CheckConstraint("state IN ('draft','queued','suggested','review','adopted','failed')"),)
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(70),unique=True)
    note:Mapped[str]=mapped_column(String(600),default='')
    state:Mapped[str]=mapped_column(String(20),default='draft')
    bottles_frozen:Mapped[bool]=mapped_column(Boolean,default=False)
    reference_snapshot:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    suggestion:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    adopted_snapshot:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    adopted_by:Mapped[str|None]=mapped_column(String(120),nullable=True)
    last_error:Mapped[str]=mapped_column(String(600),default='')
class LabelTrayBottle(Base):
    __tablename__='label_tray_bottles'
    id:Mapped[int]=mapped_column(primary_key=True)
    tray_id:Mapped[int]=mapped_column(ForeignKey('label_trays.id'))
    sample_id:Mapped[int]=mapped_column(ForeignKey('fuel_samples.id'),unique=True)
    original_tank_id:Mapped[int]=mapped_column(ForeignKey('tanks.id'))
    assigned_tank_id:Mapped[int|None]=mapped_column(ForeignKey('tanks.id'),nullable=True)
    score:Mapped[float|None]=mapped_column(Float,nullable=True)
class LabelTrayCandidate(Base):
    __tablename__='label_tray_candidates'
    __table_args__=(UniqueConstraint('tray_id','tank_id'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    tray_id:Mapped[int]=mapped_column(ForeignKey('label_trays.id'))
    tank_id:Mapped[int]=mapped_column(ForeignKey('tanks.id'))
