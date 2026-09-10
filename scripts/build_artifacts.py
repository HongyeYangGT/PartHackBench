                                                                                       
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from parthackbench.certifier import Certifier
from parthackbench.serialization import serialize_public,payload_hash
from parthackbench.tasks import all_tasks,honest_trajectory,completion_trajectory
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'artifacts'; OUT.mkdir(exist_ok=True)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    tasks=all_tasks()
    manifest=[]; public_manifest=[]; hashes={}; difficulty=[]
    for t in tasks:
        h=honest_trajectory(t); hc=Certifier().certify(t,h); c=completion_trajectory(t); cc=Certifier().certify(t,c)
        manifest.append({'id':t.id,'split':t.split,'family':t.family,'m':t.m,'honest_pstate':hc.pstate,'tags':list(t.tags),'rollback_eligible':t.rollback_eligible,'provenance':'frozen-benchmark'})
        public_manifest.append({'id':t.id,'split':t.split,'family':t.family,'m':t.m,'honest_pstate':hc.pstate,'tags':list(t.tags),'rollback_eligible':t.rollback_eligible,'instruction':t.instruction,'public_predicates':t.public_predicates})
        hashes[t.id]=payload_hash(serialize_public(t,h))
        difficulty.append({'task_id':t.id,'split':t.split,'family':t.family,'m':t.m,'honest_actions':len(h.actions),'full_actions':len(c.actions),'honest_pstate':hc.pstate,'full_pstate':cc.pstate,'milestone_action_lengths':[len(x) for x in t.milestone_actions],'preconditions':len(t.transition_rules.get('preconditions',[])),'active_goal_version':t.active_goal_version})
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    (OUT/'public_manifest.json').write_text(json.dumps(public_manifest,indent=2,sort_keys=True)+'\n')
    (OUT/'public_payload_hashes.json').write_text(json.dumps(hashes,indent=2,sort_keys=True)+'\n')
    (OUT/'difficulty_audit.json').write_text(json.dumps(difficulty,indent=2,sort_keys=True)+'\n')
    integrity_names=['empirical_shared_ledger.json','empirical_results.json','candidate_accounting_k3.json','manifest.json','public_manifest.json','public_payload_hashes.json','difficulty_audit.json']
    integrity={'hash_algorithm':'SHA-256','files':{name:sha(OUT/name) for name in integrity_names if (OUT/name).exists()}}
    (OUT/'release_integrity.json').write_text(json.dumps(integrity,indent=2,sort_keys=True)+'\n')
    index={p.name:sha(p) for p in sorted(OUT.glob('*.json')) if p.name!='artifact_index.json'}
    (OUT/'artifact_index.json').write_text(json.dumps(index,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'ok','tasks':len(tasks),'artifacts':len(index)},indent=2))
if __name__=='__main__': main()
