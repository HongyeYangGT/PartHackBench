\
\
\
   
from __future__ import annotations
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from parthackbench.serialization import public_record,idj_projection
from parthackbench.tasks import all_tasks,heldout_tasks,honest_trajectory
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'records'

def dump(path,obj): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False)+'\n')

def task_public(t):
    return {'_record':{'record_origin':'public_task_spec','empirical_metric_eligible':False,'task_id':t.id},'task':{'id':t.id,'split':t.split,'family':t.family,'instruction':t.instruction,'m':t.m,'tags':list(t.tags),'active_goal_version':t.active_goal_version,'rollback_eligible':t.rollback_eligible,'entity_schema':t.entity_schema,'public_goal_schema':t.public_predicates}}

def main():
    for t in all_tasks(): dump(OUT/'tasks'/t.split/f'{t.id}.json',task_public(t))
    for t in heldout_tasks():
        h=honest_trajectory(t)
        payload=public_record(t,h)
        dump(OUT/'public_payloads'/'honest'/f'{t.id}.json',{'_record':{'record_origin':'public_honest_payload','empirical_metric_eligible':False,'task_id':t.id},'payload':payload})
        dump(OUT/'idj_projections'/'honest'/f'{t.id}.json',{'_record':{'record_origin':'public_honest_projection','empirical_metric_eligible':False,'task_id':t.id},'projection':json.loads(idj_projection(t,h))})
    files=sorted(str(p.relative_to(OUT)) for p in OUT.rglob('*.json') if p.name not in {'RECORD_INDEX.json','PUBLIC_RELEASE_MANIFEST.json'})
    dump(OUT/'RECORD_INDEX.json',{'public_record_files':files,'count':len(files)})
    dump(OUT/'PUBLIC_RELEASE_MANIFEST.json',{'release':'PartHackBench public release','policy':{'frozen_empirical_records_immutable':True,'missing_frozen_traces_not_regenerated':True,'private_certification_material_exposed':False},'public_record_count':len(files)})
    print(json.dumps({'status':'ok','public_record_count':len(files)},indent=2))
if __name__=='__main__': main()
