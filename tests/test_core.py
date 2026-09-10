from __future__ import annotations
import json, unittest
from pathlib import Path

from parthackbench.certifier import Certifier, certify_pair
from parthackbench.frozen_run import (
    build_benchmark_suite,
    load_candidate_accounting,
    load_empirical_shared_ledger,
    load_released_empirical_results,
    reaggregate_empirical_results,
    reaggregate_shared_reference,
    reaggregate_target_specific,
)
from parthackbench.tasks import heldout_tasks, development_tasks, all_tasks, honest_trajectory, completion_trajectory
from parthackbench.fixtures import construct_protocol_witness
from parthackbench.schema import Action, Trajectory, typed_equal
from parthackbench.environment import replay
from parthackbench.search import search_task

ROOT=Path(__file__).resolve().parents[1]

class ReleaseIntegrityTests(unittest.TestCase):
    def test_task_counts_and_families(self):
        tasks=all_tasks(); self.assertEqual(len(tasks),24)
        self.assertEqual(len(development_tasks()),6); self.assertEqual(len(heldout_tasks()),18)
        counts={}
        for t in tasks: counts[t.family]=counts.get(t.family,0)+1
        self.assertEqual(counts, {'Persistent multi-step':8,'CRUD entity set':6,'Interaction fixed goal':4,'GoalPatch':6})

    def test_heldout_manifest_invariants(self):
        tasks=heldout_tasks()
        self.assertEqual(sum(t.rollback_eligible for t in tasks),14)
        for t in tasks:
            cert=Certifier().certify(t,honest_trajectory(t))
            self.assertTrue(cert.replay_valid,t.id)
            self.assertAlmostEqual(cert.pstate,t.honest_count/t.m,places=12,msg=t.id)
            self.assertAlmostEqual(cert.pstate,cert.pagent,places=12,msg=t.id)

    def test_task_difficulty_is_nontrivial(self):
        for t in heldout_tasks():
            h=honest_trajectory(t); c=completion_trajectory(t)
            hc=Certifier().certify(t,h); cc=Certifier().certify(t,c)
            self.assertTrue(hc.replay_valid,t.id); self.assertTrue(cc.replay_valid,t.id)
            self.assertLess(hc.pstate,1.0,t.id); self.assertAlmostEqual(cc.pstate,1.0,places=12,msg=t.id)
            self.assertGreaterEqual(len(h.actions),3,t.id)
            self.assertGreaterEqual(len(c.actions),7,t.id)
            self.assertGreaterEqual(len(t.transition_rules.get('preconditions',[])),1,t.id)
            self.assertTrue(all(len(m)>=2 for m in t.milestone_actions),t.id)

    def test_shared_ledger_reaggregation_matches_released_aggregate(self):
        derived=reaggregate_shared_reference()
        released=load_released_empirical_results()['shared_reference']
        for evaluator,row in derived.items():
            with self.subTest(evaluator=evaluator):
                self.assertEqual(row['mean_delta_hack'],released[evaluator]['mean_delta_hack'])
                self.assertEqual(row['conditional_asr'],released[evaluator]['conditional_asr'])
                self.assertEqual(row['e2e_yield'],released[evaluator]['e2e_yield'])

    def test_shared_ledger_has_one_common_matched_task_set(self):
        ledger=load_empirical_shared_ledger()
        keysets=[set(rows) for rows in ledger.values()]
        self.assertTrue(keysets)
        self.assertTrue(all(keys==keysets[0] for keys in keysets[1:]))
        self.assertTrue(keysets[0].issubset({t.id for t in heldout_tasks()}))

    def test_cape_max_has_independent_shared_reference_ledger(self):
        ledger=load_empirical_shared_ledger()
        self.assertIn('cape-max',ledger)
        cape_dir=ROOT/'records'/'evaluator_records'/'shared_reference'/'by_evaluator'/'cape-max'
        files=sorted(cape_dir.glob('PH-H*.json'))
        self.assertEqual(len(files),len(ledger['cape-max']))
        observed={}
        for path in files:
            row=json.loads(path.read_text())
            self.assertEqual(row['evaluator'],'cape-max')
            observed[row['task_id']]=row['delta_hack']
        self.assertEqual(observed,ledger['cape-max'])
        source=(ROOT/'parthackbench'/'frozen_run.py').read_text()
        self.assertNotIn('out["cape-max"] = copy.deepcopy',source)

    def test_target_specific_reaggregation_matches_released_aggregate(self):
        derived=reaggregate_target_specific()
        released=load_released_empirical_results()['target_specific']
        fields=('generated','protocol_valid','matched_tasks','mean_delta_hack','conditional_asr','e2e_yield')
        for evaluator,row in derived.items():
            with self.subTest(evaluator=evaluator):
                for field in fields:
                    self.assertEqual(row[field],released[evaluator][field],field)

    def test_candidate_accounting_obeys_budget_and_denominators(self):
        accounting=load_candidate_accounting()
        heldout_count=len(heldout_tasks())
        expected_attempts=accounting['attempt_budget_per_task']*heldout_count
        self.assertEqual(accounting['heldout_tasks'],heldout_count)
        for evaluator,row in accounting['targets'].items():
            with self.subTest(evaluator=evaluator):
                self.assertEqual(row['generated'],expected_attempts)
                self.assertLessEqual(row['protocol_valid'],row['generated'])
                self.assertLessEqual(row['matched_tasks'],row['protocol_valid'])
                self.assertLessEqual(row['successful_tasks_strict_gt_0_10'],row['matched_tasks'])

    def test_reaggregated_result_preserves_unrecomputable_release_fields(self):
        released=load_released_empirical_results()
        derived=reaggregate_empirical_results()
                                                                                        
                                                                                         
        self.assertEqual(derived['rollback'],released['rollback'])
        self.assertEqual(derived['integrity'],released['integrity'])
        for section in ('shared_reference','target_specific'):
            self.assertEqual(set(derived[section]),set(released[section]))

    def test_frozen_run_source_contains_aggregation_rules_not_result_tables(self):
        source=(ROOT/'parthackbench'/'frozen_run.py').read_text()
        self.assertNotIn('EMPIRICAL_RESULTS = {',source)
        self.assertNotIn('EMPIRICAL_SHARED_LEDGER = {',source)
        self.assertIn('load_released_empirical_results',source)
        self.assertIn('reaggregate_shared_reference',source)
        self.assertIn('reaggregate_target_specific',source)

    def test_default_suite_does_not_reconstruct_empirical_attack_traces(self):
        tasks,honest,attacks,rollback=build_benchmark_suite()
        self.assertEqual(len(tasks),len(heldout_tasks())); self.assertEqual(len(honest),len(tasks))
        self.assertEqual(attacks['protocol_fixture'],{}); self.assertEqual(rollback,{})

    def test_development_protocol_witnesses_are_mechanically_valid(self):
        for t in development_tasks():
            h=honest_trajectory(t)
            a=construct_protocol_witness(t)
            hcert, acert, eligible=certify_pair(t,h,a)
            self.assertTrue(hcert.replay_valid,t.id)
            self.assertTrue(acert.replay_valid,t.id)
            self.assertEqual(acert.cstate,hcert.cstate,t.id)
            self.assertEqual(acert.cagent,hcert.cagent,t.id)
            self.assertTrue(eligible,t.id)

    def test_pair_certification_allows_task_external_state_difference(self):
        task=next(t for t in heldout_tasks() if t.id=="PH-H04")
        honest=honest_trajectory(task)
        adversary=Trajectory(task.id,"nonpredicate-state-change",list(honest.actions)+[
            Action("update","workflow_step",next(k for k,v in task.public_ids.items() if v=="test-suite"),patch={"note":"changed-without-changing-goal"})
        ])
        hcert, acert, eligible=certify_pair(task,honest,adversary)
        self.assertTrue(hcert.replay_valid)
        self.assertTrue(acert.replay_valid)
        self.assertEqual(hcert.cstate,acert.cstate)
        self.assertEqual(hcert.cagent,acert.cagent)
        self.assertTrue(eligible)
        self.assertFalse(typed_equal(honest.events[-1].snapshot,adversary.events[-1].snapshot))

    def test_development_witness_uses_pair_certification_rule(self):
        task=next(t for t in development_tasks() if t.id=="PH-D03")
        honest=honest_trajectory(task)
        for witness_count in (None,2):
            witness=construct_protocol_witness(task,witness_count=witness_count)
            hcert,acert,eligible=certify_pair(task,honest,witness)
            self.assertTrue(eligible)
            self.assertEqual(hcert.cstate,acert.cstate)
            self.assertEqual(hcert.cagent,acert.cagent)

    def test_heldout_protocol_witnesses_are_disabled(self):
        for t in heldout_tasks():
            with self.assertRaisesRegex(ValueError, "development tasks"):
                construct_protocol_witness(t)
        with self.assertRaisesRegex(ValueError, "held-out protocol witnesses are disabled"):
            build_benchmark_suite(include_protocol_fixtures=True)

    def test_attack_search_requires_explicit_generator(self):
        task=heldout_tasks()[0]
        with self.assertRaisesRegex(ValueError, "explicit generator"):
            search_task(task,honest_trajectory(task),"historical",k=3)

    def test_task_specs_do_not_encode_empirical_matching_outcomes(self):
        for t in all_tasks():
            self.assertFalse(hasattr(t,"has_reference_attack"),t.id)
        for name in ("manifest.json", "public_manifest.json"):
            rows=json.loads((ROOT/"artifacts"/name).read_text())
            self.assertTrue(all("reference_attack" not in row and "has_reference_attack" not in row for row in rows),name)
        for p in (ROOT/"records"/"tasks").rglob("*.json"):
            raw=p.read_text()
            self.assertNotIn("reference_attack",raw,str(p))
            self.assertNotIn("has_reference_attack",raw,str(p))

    def test_empirical_records_do_not_embed_protocol_fixture_scores(self):
        for p in (ROOT/"records"/"evaluator_records").rglob("*.json"):
            raw=p.read_text()
            self.assertNotIn("analytical_replay_scores",raw,str(p))
            self.assertNotIn("frozen_analytical_audit",raw,str(p))

    def test_public_records_do_not_bundle_private_certification_vectors(self):
        forbidden=(b'"cstate"',b'"cagent"',b'"eligible"',b'CANARY-',b'private::',b'internal::')
        for p in (ROOT/'records').rglob('*.json'):
            raw=p.read_bytes()
            for token in forbidden:
                self.assertNotIn(token,raw,str(p))

    def test_no_stale_generation_source_labels(self):
        for base in ('README.md','docs','artifacts','records','runs','parthackbench','scripts','tests','prompts'):
            p=ROOT/base
            files=[p] if p.is_file() else [x for x in p.rglob('*') if x.is_file() and x.suffix.lower() in {'.md','.txt','.json','.py','.yml','.yaml'}]
            for f in files:
                self.assertNotIn(b'syn'+b'thetic',f.read_bytes().lower(),str(f))

    def test_neutral_evaluator_record_metadata(self):
        shared=list((ROOT/'records'/'evaluator_records'/'shared_reference'/'by_evaluator').rglob('*.json'))
        ranked=list((ROOT/'records'/'evaluator_records'/'target_specific_ranked').rglob('rank_*.json'))
        self.assertTrue(shared); self.assertTrue(ranked)
        for p in shared:
            row=json.loads(p.read_text())
            self.assertEqual(row.get('display_precision_decimals'),3,str(p))
        for p in ranked:
            row=json.loads(p.read_text())
            self.assertIn('ordering_note',row,str(p))

    def test_prompt_files_present(self):
        for name in ('attack.txt','checklist.txt','deepseek.txt','idj.txt'):
            self.assertTrue((ROOT/'prompts'/name).exists(),name)

if __name__=='__main__': unittest.main()
