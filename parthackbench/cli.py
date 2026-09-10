                                                                     
from __future__ import annotations
import argparse, json
from pathlib import Path
from .certifier import Certifier
from .serialization import serialize_public
from .frozen_run import reaggregate_empirical_results
from .tasks import all_tasks, heldout_tasks, development_tasks, get_task, honest_trajectory
from .fixtures import construct_protocol_witness, construct_rollback_fixture


def _j(x):
    return json.dumps(x, indent=2, sort_keys=True, ensure_ascii=False)


def _tasks(split):
    return heldout_tasks() if split == "heldout" else development_tasks() if split == "development" else all_tasks()


def main(argv=None):
    p=argparse.ArgumentParser(prog="parthackbench")
    sub=p.add_subparsers(dest="command", required=True)
    m=sub.add_parser("manifest", help="print public task metadata"); m.add_argument("--split", choices=("all","heldout","development"), default="all")
    e=sub.add_parser("aggregate-results", help="re-aggregate released empirical records from available lower-level inputs"); e.add_argument("--evaluator", default=None); e.add_argument("--json", action="store_true")
    r=sub.add_parser("replay-honest", help="replay a bundled honest benchmark trajectory"); r.add_argument("--task", required=True); r.add_argument("--json", action="store_true")
    f=sub.add_parser("protocol-fixture", help="build a development-only mechanics witness; excluded from empirical metrics"); f.add_argument("--task", required=True); f.add_argument("--kind", choices=("adversary","rollback"), required=True); f.add_argument("--json", action="store_true")
    x=sub.add_parser("export-honest-public", help="serialize a bundled honest trajectory to public JSON"); x.add_argument("--task", required=True); x.add_argument("--out", required=True)
    a=p.parse_args(argv)
    if a.command=="manifest":
        rows=[]
        for t in _tasks(a.split):
            rows.append({"id":t.id,"split":t.split,"family":t.family,"m":t.m,"tags":list(t.tags),"rollback_eligible":t.rollback_eligible,"honest_count":t.honest_count})
        print(_j(rows)); return 0
    if a.command=="aggregate-results":
        out=reaggregate_empirical_results()
        if a.evaluator:
            key={"historical":"historical/predicate-max","predicate-max":"historical/predicate-max","terminal":"terminal-outcome"}.get(a.evaluator.lower(),a.evaluator.lower())
            out={"provenance":out["provenance"],"evaluator":key,"shared_reference":out["shared_reference"].get(key),"target_specific":out["target_specific"].get(key),"rollback":out["rollback"].get(key)}
        print(_j(out)); return 0
    task=get_task(a.task)
    if a.command=="replay-honest":
        print(_j(Certifier().certify(task,honest_trajectory(task)).as_dict())); return 0
    if a.command=="protocol-fixture":
        tr=construct_protocol_witness(task) if a.kind=="adversary" else construct_rollback_fixture(task)
        out={"warning":"development mechanics fixture; excluded from frozen empirical metrics and unrelated to frozen model-run matching","certification":Certifier().certify(task,tr).as_dict(),"trajectory":tr.to_dict()}
        print(_j(out)); return 0
    path=Path(a.out); path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(serialize_public(task,honest_trajectory(task))); print(path); return 0

if __name__=="__main__": raise SystemExit(main())
