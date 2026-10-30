#!/usr/bin/env python3
"""Synthetic deterministic tests + clearly labelled bundled-data integration.
No real customer facts, business baselines, or model-effectiveness claims.
"""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))
try:
    import process_framework_tools as F
    import process_contract as C
finally:
    sys.path.pop(0)


def architecture():
    a = F.tailorable_node('BP-001', '合成业务域')
    b = F.tailorable_node('BP-002', '合成任务甲', 'BP-001')
    c = F.tailorable_node('BP-003', '合成任务乙', 'BP-001')
    return {'schema_version': '1.0', 'version': 1, 'status': 'draft', 'company': {'name': '合成企业'},
            'processes': [a, b, c], 'relations': [], 'evidence': [], 'industry_baselines': [], 'tailoring_history': []}


def operation(kind, **fields):
    return dict(op=kind, reason='合成设计依据，不是客户事实', **fields)


def cli(*args, script=None, cwd=None):
    p = subprocess.run([sys.executable, '-B', str(script or SCRIPTS / 'process_framework_tools.py'), *map(str, args)],
                       capture_output=True, text=True, cwd=cwd)
    try:
        return p, json.loads(p.stdout)
    except ValueError:
        raise AssertionError((p.stdout, p.stderr))


class TailoringTests(unittest.TestCase):
    def test_rename_keeps_id_and_input_immutable(self):
        a = architecture(); old = copy.deepcopy(a)
        b = F.apply_operations(a, [operation('rename', id='BP-002', name='新任务名')])
        self.assertEqual(a, old)
        self.assertEqual(b['processes'][1]['id'], 'BP-002')
        self.assertEqual(b['version'], 2)
        self.assertEqual(b['processes'][1]['name'], '新任务名')

    def test_drop_requires_explicit_cascade(self):
        with self.assertRaises(ValueError):
            F.apply_operations(architecture(), [operation('drop', id='BP-001')])
        b = F.apply_operations(architecture(), [operation('drop', id='BP-001', cascade=True)])
        self.assertTrue(all(not p['active'] for p in b['processes']))

    def test_merge_keeps_history_and_reparents_children(self):
        a = architecture()
        a['processes'].append(F.tailorable_node('BP-004', '合成子任务', 'BP-002'))
        b = F.apply_operations(a, [operation('merge', ids=['BP-002', 'BP-003'], new_id='BP-005', name='合并任务')])
        nodes = {p['id']: p for p in b['processes']}
        self.assertFalse(nodes['BP-002']['active'])
        self.assertEqual(nodes['BP-004']['parent_id'], 'BP-005')
        self.assertEqual(nodes['BP-005']['derived_from'], ['BP-002', 'BP-003'])
        self.assertFalse(C.validate_architecture(b))

    def test_cross_parent_merge_needs_parent(self):
        a = architecture(); a['processes'].append(F.tailorable_node('BP-004', '另一业务域'))
        with self.assertRaises(ValueError):
            F.apply_operations(a, [operation('merge', ids=['BP-002', 'BP-004'], new_id='BP-005', name='合并')])

    def test_split_leaves_and_id_not_reused(self):
        b = F.apply_operations(architecture(), [operation('split', id='BP-002', items=[{'id': 'BP-004', 'name': '拆分甲'}, {'id': 'BP-005', 'name': '拆分乙'}])])
        self.assertFalse(b['processes'][1]['active'])
        with self.assertRaises(ValueError):
            F.apply_operations(b, [operation('add', node={'id': 'BP-002', 'name': '不能重用'})])

    def test_split_children_need_explicit_map(self):
        op = operation('split', id='BP-001', items=[{'id': 'BP-004', 'name': '甲域'}, {'id': 'BP-005', 'name': '乙域'}])
        with self.assertRaises(ValueError):
            F.apply_operations(architecture(), [op])
        op['children_map'] = {'BP-002': 'BP-004', 'BP-003': 'BP-005'}
        b = F.apply_operations(architecture(), [op])
        self.assertEqual(b['processes'][1]['parent_id'], 'BP-004')

    def test_add_target_task_does_not_claim_current_fact(self):
        b = F.apply_operations(architecture(), [operation('add', node={'id': 'BP-004', 'name': '目标任务', 'parent_id': 'BP-001', 'perspective': 'target', 'kind': 'task'})])
        p = b['processes'][-1]
        self.assertEqual(p['perspective'], 'target')
        self.assertEqual(p['confirmation'], 'hypothesis')
        self.assertEqual(p['source_refs'], [])

    def test_add_cannot_forge_confirmation_or_source(self):
        for extra in [{'confirmation': 'confirmed'}, {'source_refs': [{'pcf_id': 'made-up'}]}]:
            with self.assertRaises(ValueError):
                F.apply_operations(architecture(), [operation('add', node=dict(id='BP-004', name='假造', **extra))])

    def test_reparent_cycle_rejected(self):
        with self.assertRaises(ValueError):
            F.apply_operations(architecture(), [operation('reparent', id='BP-001', parent_id='BP-002')])

    def test_flow_feedback_cycle_allowed(self):
        ops = [operation('relate', relation={'id': 'R1', 'type': 'sequence', 'from': 'BP-002', 'to': 'BP-003', 'perspective': 'target'}),
               operation('relate', relation={'id': 'R2', 'type': 'feedback', 'from': 'BP-003', 'to': 'BP-002', 'perspective': 'target'})]
        b = F.apply_operations(architecture(), ops)
        self.assertFalse(C.validate_architecture(b))

    def test_flow_not_inferred_from_classification(self):
        self.assertEqual(architecture()['relations'], [])
        a = architecture(); a['relations'] = [{'id': 'R', 'type': 'sequence', 'from': 'BP-002', 'to': 'BP-003', 'perspective': 'current', 'confirmation': 'hypothesis'}]
        self.assertTrue(any('依据' in e for e in C.validate_architecture(a)))

    def test_merge_requires_explicit_relation_repair(self):
        a = architecture(); a['relations'] = [{'id': 'R', 'type': 'sequence', 'from': 'BP-002', 'to': 'BP-003', 'perspective': 'current', 'confirmation': 'hypothesis', 'basis': '合成'}]
        with self.assertRaises(ValueError):
            F.apply_operations(a, [operation('merge', ids=['BP-002', 'BP-003'], new_id='BP-004', name='合并')])

    def test_confirmation_requires_customer_locator(self):
        with self.assertRaises(ValueError):
            F.apply_operations(architecture(), [operation('confirm_node', id='BP-002')])
        b = F.apply_operations(architecture(), [operation('confirm_node', id='BP-002', evidence=[{'kind': 'customer_confirmation', 'locator': '合成记录，仅测结构'}])])
        self.assertEqual(b['processes'][1]['confirmation'], 'confirmed')

    def test_edit_resets_previous_confirmation(self):
        evidence = [{'kind': 'customer_confirmation', 'locator': '合成记录，仅测试'}]
        a = F.apply_operations(architecture(), [operation('confirm_node', id='BP-002', evidence=evidence), operation('confirm_architecture', evidence=evidence)])
        b = F.apply_operations(a, [operation('rename', id='BP-002', name='改名后待确认')])
        self.assertEqual(b['status'], 'draft')
        self.assertEqual(b['processes'][1]['confirmation'], 'hypothesis')

    def test_arch_confirmation_must_be_last(self):
        with self.assertRaises(ValueError):
            F.apply_operations(architecture(), [operation('confirm_architecture', evidence=[{'kind': 'customer_confirmation', 'locator': '合成'}]), operation('rename', id='BP-002', name='后改')])

    def test_update_order_and_target_design(self):
        b = F.apply_operations(architecture(), [operation('update', id='BP-002', changes={'order': 4, 'target_design': {'ai_work': '合成研判', 'human_work': '复核', 'handoff': '超限转人工'}})])
        self.assertEqual(b['processes'][1]['order'], 4)
        self.assertIn('human_work', b['processes'][1]['target_design'])

    def test_no_silent_id_changes(self):
        with self.assertRaises(ValueError):
            F.apply_operations(architecture(), [operation('update', id='BP-002', changes={'id': 'X'})])

    def test_write_requires_new_project_path(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / '企业 流程.json'
            self.assertEqual(F.write_project(p, architecture())['status'], 'ok')
            with self.assertRaises(FileExistsError):
                F.write_project(p, architecture())
        with self.assertRaises(ValueError):
            F.write_project(ROOT / 'assets/process-frameworks/forbidden-project.json', architecture())

    def test_attach_reference_is_verified_not_handwritten_identity(self):
        op = operation('attach_reference', id='BP-002', resource_id='pcf', dataset_id='ecommerce-practice-reference__v0.1__2026__zh', reference_key='ECOM-10.3')
        a = F.apply_operations(architecture(), [op])
        ref = a['processes'][1]['source_refs'][0]
        self.assertFalse(ref['is_official'])
        self.assertIsNone(ref['pcf_id'])
        self.assertEqual(a['processes'][1]['confirmation'], 'hypothesis')
        op['reference_key'] = 'NONEXISTENT'
        with self.assertRaises(ValueError):
            F.apply_operations(architecture(), [op])

    def test_company_profile_change_resets_node_confirmation(self):
        a = architecture()
        a['processes'][1]['confirmation'] = 'confirmed'
        a['processes'][1]['evidence'] = [{'kind': 'customer_confirmation', 'locator': '合成'}]
        b = F.apply_operations(a, [operation('update_company', changes={'business_models': ['self_operated', 'marketplace']})])
        self.assertEqual(b['processes'][1]['confirmation'], 'hypothesis')
        self.assertEqual(b['company']['business_models'], ['self_operated', 'marketplace'])

    def test_non_json_number_does_not_leave_partial_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'bad.json'; a = architecture()
            a['processes'][0]['target_design'] = {'bad_value': float('nan')}
            with self.assertRaises(ValueError):
                F.write_project(p, a)
            self.assertFalse(p.exists())

    def test_custom_library_also_cannot_receive_project(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'custom-source'; root.mkdir()
            with self.assertRaises(ValueError):
                F.write_project(root / 'customer.json', architecture(), root)

    def test_invalid_typed_parent_returns_errors(self):
        a = architecture(); a['processes'][1]['parent_id'] = []
        self.assertTrue(C.validate_architecture(a))

    def test_unknown_operations_rejected(self):
        with self.assertRaises(ValueError):
            F.apply_operations(architecture(), [operation('invent_ai_for_every_node')])


class ProjectionTests(unittest.TestCase):
    def fixture(self):
        return json.loads((ROOT / 'tests/fixtures/project.json').read_text())

    def test_old_projection_compatible(self):
        self.assertEqual(C.validate_process_projection(self.fixture()), [])

    def test_enterprise_refs_not_external_ids(self):
        d = self.fixture(); d['process_architecture'] = architecture()
        d['use_cases'][0]['business_process_refs'] = ['ECOM-10.3']
        self.assertTrue(any('无效' in e for e in C.validate_process_projection(d)))
        d['use_cases'][0]['business_process_refs'] = ['BP-002']
        self.assertEqual(C.validate_process_projection(d), [])

    def test_new_projection_needs_process_position(self):
        d = self.fixture(); d['process_architecture'] = architecture()
        self.assertTrue(any('缺本企业' in e for e in C.validate_process_projection(d)))

    def test_links_without_architecture_not_falsely_validated(self):
        d = self.fixture(); d['use_cases'][0]['business_process_refs'] = ['BP-002']
        self.assertTrue(C.validate_process_projection(d))

    def test_framework_evidence_cannot_prove_customer(self):
        e = {'kind': 'framework_reference', 'dataset_id': 'SYNTHETIC', 'version': '0', 'source_type': 'analyst_compiled_reference',
             'locator': 'synthetic', 'purpose': 'architecture', 'is_official': False, 'proves_customer_fact': False}
        self.assertFalse(C.framework_evidence_errors([e]))
        e['is_official'] = True
        self.assertTrue(C.framework_evidence_errors([e]))
        e['is_official'] = False; e['proves_customer_fact'] = True
        self.assertTrue(C.framework_evidence_errors([e]))

    def test_coverage_is_not_ai_quota(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); a = architecture(); a['processes'][2]['ai_assessment'] = 'no_ai_needed'
            (d / 'a.json').write_text(json.dumps(a))
            s = self.fixture(); s['use_cases'][0]['business_process_refs'] = ['BP-002']
            (d / 's.json').write_text(json.dumps(s))
            r, out = cli('coverage', '--project', d / 'a.json', '--scenarios', d / 's.json')
            self.assertEqual(r.returncode, 0)
            states = {p['process_id']: p['assessment'] for p in out['results']}
            self.assertEqual(states['BP-003'], 'no_ai_needed')
            self.assertEqual(states['BP-001'], 'contains_mapped_tasks_not_full_coverage')

    def test_excluded_process_cannot_support_case(self):
        d = self.fixture(); a = architecture(); a['processes'][1].update(active=False, confirmation='excluded')
        d['process_architecture'] = a; d['use_cases'][0]['business_process_refs'] = ['BP-002']
        self.assertTrue(C.validate_process_projection(d))

    def test_malformed_scenario_list_rejected(self):
        self.assertTrue(C.validate_process_projection({'use_cases': {}}))
        self.assertTrue(C.validate_process_projection({'use_cases': ['not an object']}))

    def test_combined_scenario_validator(self):
        with tempfile.TemporaryDirectory() as d:
            data = self.fixture(); data['process_architecture'] = architecture()
            data['use_cases'][0]['business_process_refs'] = ['BP-002']
            path = Path(d) / 'projection.json'; path.write_text(json.dumps(data))
            result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'scenario_tools.py'), 'validate', str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class BundledIntegrationTests(unittest.TestCase):
    def test_doctor_hashes(self):
        _, o = cli('doctor', '--verify')
        self.assertEqual(o['hash_failures'], [])
        self.assertTrue(o['resources'][0]['available'])
        self.assertFalse(o['raw_pdf_excel_required_for_queries'])

    def test_catalog_has_12_pcf_and_scor_descriptor(self):
        _, o = cli('catalog')
        self.assertEqual(o['total'], 13)
        e = next(x for x in o['results'] if x['source_type'] == 'analyst_compiled_reference')
        self.assertFalse(e['is_official']); self.assertEqual(e['node_count'], 193)
        s = next(x for x in o['results'] if x['resource_id'] == 'scor')
        self.assertFalse(s['complete_catalog'])

    def test_pcf_query_preserves_source_identity(self):
        p, o = cli('get', '--industry', '电商', '--id', '10.3')
        self.assertEqual(p.returncode, 0)
        n = o['results'][0]
        self.assertFalse(n['is_official']); self.assertIsNone(n['pcf_id'])
        self.assertEqual(n['applicable_business_models'], ['marketplace'])
        self.assertFalse(n['source']['raw_excel_bundled'])

    def test_memory_index_equivalent_no_disk_cache_needed(self):
        _, a = cli('search', '--industry', '电商', '--q', '商家结算')
        _, b = cli('search', '--industry', '电商', '--q', '商家结算', '--memory')
        self.assertEqual([n['node_id'] for n in a['results']], [n['node_id'] for n in b['results']])
        self.assertEqual(b['index_mode'], 'memory_from_canonical_jsonl')

    def test_no_fake_pcf_identifier(self):
        _, o = cli('get', '--industry', '电商', '--pcf-id', '10002')
        self.assertEqual(o['status'], 'unsupported_identifier')

    def test_pagination_and_budget(self):
        _, o = cli('outline', '--industry', '公用事业', '--depth', '2', '--limit', '3', '--max-chars', '6000')
        self.assertLessEqual(len(json.dumps(o, ensure_ascii=False, separators=(',', ':'))), 6000)
        self.assertIsNotNone(o['next_offset'])
        self.assertLessEqual(o['returned'], 3)

    def test_init_draft_has_no_inferred_flow(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / '中文 空格.json'
            r, o = cli('init-project', '--industry', '电商', '--model', 'platform', '--company-name', '合成平台企业', '--output', p)
            self.assertEqual(r.returncode, 0, o)
            a = json.loads(p.read_text())
            self.assertEqual(a['relations'], [])
            self.assertTrue(all(n['confirmation'] == 'hypothesis' for n in a['processes']))
            self.assertTrue(all(n['source_refs'][0]['source_type'] == 'analyst_compiled_reference' for n in a['processes']))
            hids = {n['source_refs'][0]['hierarchy_id'] for n in a['processes']}
            self.assertIn('10.3', hids); self.assertNotIn('10.4', hids)

    def test_business_modes_and_unknown_b2c(self):
        with tempfile.TemporaryDirectory() as d:
            a = F.parser().parse_args(['init-project', '--industry', '电商', '--model', 'B2C', '--company-name', '合成', '--output', str(Path(d) / 'a.json')])
            with self.assertRaises(ValueError):
                F.run(a)
            for model in ('self_operated', 'agency'):
                p = Path(d) / (model + '.json')
                _, o = cli('init-project', '--industry', '电商', '--model', model, '--company-name', '合成', '--output', p)
                self.assertEqual(o['status'], 'ok')
                nodes = json.loads(p.read_text())['processes']
                ids = {n['source_refs'][0]['hierarchy_id'] for n in nodes}
                self.assertNotIn('10.3', ids)
                if model == 'agency': self.assertIn('10.4', ids)

    def test_official_export_keeps_original_attribution(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'a.json'
            _, o = cli('init-project', '--industry', '公用事业', '--company-name', '合成企业', '--depth', '1', '--output', p)
            self.assertEqual(o['status'], 'ok')
            self.assertIn('royalty-free', json.dumps(json.loads(p.read_text())['source_notices']))

    def test_scor_scope_and_no_formula(self):
        _, out = cli('get', '--framework', 'scor', '--code', 'RS.1.1')
        if out['status'] == 'resource_missing':
            self.assertIn('未安装', out['message']); return
        self.assertFalse(out['complete_catalog'])
        self.assertIsNone(out['results'][0]['formula'])
        _, out = cli('subtree', '--framework', 'scor', '--code', 'F')
        self.assertEqual(out['status'], 'unsupported_operation')

    def test_scor_initializes_concepts_not_75_processes(self):
        if not (F.DEFAULT_LIBRARY / 'scor-intro/records.jsonl').exists():
            self.skipTest('SCOR restricted local payload is intentionally not Git distributed')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'a.json'
            _, o = cli('init-project', '--framework', 'scor', '--company-name', '合成供应链企业', '--output', p)
            self.assertEqual(o['status'], 'ok', o)
            a = json.loads(p.read_text())
            self.assertEqual(len(a['processes']), 7)
            self.assertFalse(a['industry_baselines'][0]['complete_catalog'])
            self.assertEqual(a['relations'], [])

    def test_relocation_without_cache_scor_or_downloads(self):
        with tempfile.TemporaryDirectory(prefix='流程 中文 空格 ') as d:
            k = Path(d) / '技能副本'; k.mkdir()
            shutil.copytree(ROOT / 'scripts', k / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
            dst = k / 'assets/process-frameworks'; dst.mkdir(parents=True)
            for name in ('registry.json', 'manifest.json'):
                shutil.copy2(F.DEFAULT_LIBRARY / name, dst / name)
            shutil.copytree(F.DEFAULT_LIBRARY / 'pcf-and-ecommerce', dst / 'pcf-and-ecommerce', ignore=shutil.ignore_patterns('检索'))
            script = k / 'scripts/process_framework_tools.py'
            r, o = cli('get', '--industry', '电商', '--id', '10.3', script=script, cwd=d)
            self.assertEqual(r.returncode, 0, o)
            self.assertEqual(o['index_mode'], 'memory_from_canonical_jsonl')
            self.assertEqual(o['results'][0]['reference_id'], 'ECOM-10.3')
            _, health = cli('doctor', script=script, cwd=d)
            self.assertEqual(health['status'], 'incomplete')
            self.assertFalse(next(x for x in health['resources'] if x['resource_id'] == 'scor')['available'])
            _, missing = cli('get', '--framework', 'scor', '--code', 'F', script=script, cwd=d)
            self.assertEqual(missing['status'], 'resource_missing')
            self.assertFalse((dst / 'pcf-and-ecommerce/检索').exists())

    def test_equal_count_changed_corpus_invalidates_cache(self):
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / 'pcf-copy'
            shutil.copytree(F.DEFAULT_LIBRARY / 'pcf-and-ecommerce', dst)
            p = next((dst / '数据').glob('电商*/processes.jsonl'))
            rows = F.lines(p)
            row = next(n for n in rows if n['hierarchy_id'] == '10.3')
            row['name_original'] = '隔离测试改名，不更改节点数量'
            p.write_text(''.join(F.encode(n) + '\n' for n in rows))
            self.assertFalse(F.cache_valid(dst))
            q, mode = F.open_pcf(dst)
            try:
                self.assertEqual(mode, 'memory_from_canonical_jsonl')
                self.assertEqual(q.c.execute('select name from nodes where node_id=?', (row['node_id'],)).fetchone()[0], row['name_original'])
            finally:
                q.c.close()

    def test_reproducible_target_process_demo(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / '合成目标流程'
            p = subprocess.run([sys.executable, '-B', str(ROOT / 'tests/process_backbone_demo.py'), '--output-dir', str(out)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            summary = json.loads(p.stdout)
            self.assertTrue(summary['combined_valid'])
            self.assertFalse(summary['real_customer_facts_validated'])
            self.assertFalse(summary['real_ai_effect_tested'])
            self.assertEqual(summary['use_cases'], 1)
            a = json.loads((out / '企业流程骨架_v1.json').read_text())
            b = json.loads((out / '企业流程骨架_v2.json').read_text())
            self.assertEqual(a['relations'], [])
            self.assertEqual(len(b['relations']), 3)
            self.assertTrue(all(r['perspective'] == 'target' for r in b['relations']))
            self.assertTrue(all(n['confirmation'] == 'hypothesis' for n in b['processes']))

    def test_new_python_syntax_compatible(self):
        for p in (SCRIPTS / 'process_framework_tools.py', SCRIPTS / 'process_contract.py', SCRIPTS / 'backends/pcf_index.py'):
            ast.parse(p.read_text(), feature_version=(3, 8))


if __name__ == '__main__':
    unittest.main()
