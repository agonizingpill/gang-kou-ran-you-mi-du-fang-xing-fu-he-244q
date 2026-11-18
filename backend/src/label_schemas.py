from pydantic import BaseModel,Field,ConfigDict
class Clean(BaseModel):model_config=ConfigDict(str_strip_whitespace=True)
class TrayIn(Clean):
    code:str=Field(min_length=2,max_length=70)
    note:str=Field(default='',max_length=600)
class BottleIn(Clean):sample_id:int=Field(gt=0)
class CandidateIn(Clean):tank_id:int=Field(gt=0)
class AdoptIn(Clean):
    scheme_index:int|None=Field(default=None,ge=0,le=1)
    sign_note:str=Field(default='',max_length=600)
