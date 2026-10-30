#!/usr/bin/env python3
import ast
import copy
from datetime import date
from decimal import Decimal
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S = load('scenario_tools', 'scripts/scenario_tools.py')
W = load('prepare_workbook', 'scripts/prepare_workbook.py')
D = load('demo_iteration', 'tests/demo_iteration.py')
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def cli(script, *args):
    return subprocess.run([sys.executable, str(ROOT / script)] + list(args), capture_output=True, text=True)


class ResearchTests(unittest.TestCase):
    def test_old_interface_json_clean(self):
        r = cli('scripts/deep_research_wrapper.py', '--company-name', '合成企业', '--format', 'json')
        self.assertEqual(r.returncode, 0)
        value = json.loads(r.stdout)
        self.assertEqual(value['company_name'], '合成企业')
        self.assertIn('并非已完成调研', r.stderr)
        self.assertIsNone(value['company_overview']['team_size'])

    def test_markdown(self):
        r = cli('scripts/deep_research_wrapper.py', '--company-name', '示例')
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.startswith('# 示例'))

    def test_industry_and_historical_year(self):
        r = cli('scripts/deep_research_wrapper.py', '--company-name', '示例', '--industry', '制造业', '--research-year', '2019', '--format', 'json')
        data = json.loads(r.stdout)
        self.assertEqual(data['time_window'], '2019')
        self.assertTrue(all('制造业' in q['query'] and '2019' in q['query'] for q in data['industry_research_queries']))

    def test_explicit_window(self):
        r = cli('scripts/deep_research_wrapper.py', '--company-name', '示例', '--time-window', '2018-2020', '--format', 'json')
        self.assertEqual(json.loads(r.stdout)['time_window'], '2018-2020')

    def test_default_year_dynamic(self):
        r = cli('scripts/deep_research_wrapper.py', '--company-name', '示例', '--format', 'json')
        self.assertEqual(json.loads(r.stdout)['time_window'], '{} {}'.format(date.today().year - 1, date.today().year))

    def test_invalid_arguments(self):
        for args in [[], ['--company-name', ' '], ['--company-name', 'x', '--research-year', '0'], ['--company-name', 'x', '--research-year', '2019', '--time-window', '2020']]:
            self.assertNotEqual(cli('scripts/deep_research_wrapper.py', *args).returncode, 0)


class ScoreTests(unittest.TestCase):
    def test_formula(self):
        v = S.score({'value': 5, 'feasibility': 4, 'data': 3})
        self.assertEqual(v['raw_score'], 4.1)
        self.assertEqual(v['priority'], 'P0')
        self.assertEqual(v['readiness'], 'pending')

    def test_unknown_is_not_low_score(self):
        v = S.score({'value': 5, 'feasibility': 4, 'data': None})
        self.assertIsNone(v['raw_score'])
        self.assertEqual(v['priority'], '待评估')

    def test_boundaries_use_unrounded_score(self):
        for mark in [Decimal('3'), Decimal('4')]:
            at = S.score(dict.fromkeys(S.WEIGHTS, mark))
            below = S.score(dict.fromkeys(S.WEIGHTS, mark - Decimal('0.01')))
            self.assertNotEqual(at['priority'], below['priority'])
            self.assertEqual(at['display_score'], below['display_score'])

    def test_half_up(self):
        self.assertEqual(S.score(dict.fromkeys(S.WEIGHTS, Decimal('3.45')))['display_score'], '3.5')

    def test_invalid(self):
        for bad in [True, 0, 6, float('nan'), float('inf'), '5']:
            with self.assertRaises(ValueError):
                S.score({'value': bad, 'feasibility': 3, 'data': 3})

    def test_high_score_does_not_override_gate(self):
        r = S.score(dict.fromkeys(S.WEIGHTS, 5), dict.fromkeys(S.GATES, False))
        self.assertEqual(r['priority'], 'P0')
        self.assertEqual(r['readiness'], 'held')
        self.assertNotIn('立即上线', r['schedule'])

    def test_ready_is_only_decision(self):
        self.assertEqual(S.score(dict.fromkeys(S.WEIGHTS, 4), dict.fromkeys(S.GATES, True))['readiness'], 'ready_for_decision')
        with self.assertRaises(ValueError):
            S.score(dict.fromkeys(S.WEIGHTS, 4), {'owner': 1})


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'tests/fixtures/project.json').read_text())

    def test_valid_and_same_id_across_periods(self):
        self.assertEqual(S.validate(self.data), [])
        self.assertEqual(len(self.data['use_cases']), 1)
        self.assertEqual(len(self.data['big_scenarios'][0]['states']), 3)

    def test_orphan_reference(self):
        self.data['big_scenarios'][0]['states'][0]['use_case_ids'] = ['missing']
        self.assertTrue(any('孤儿' in e for e in S.validate(self.data)))

    def test_duplicate_id(self):
        self.data['use_cases'].append(copy.deepcopy(self.data['use_cases'][0]))
        self.assertTrue(any('重复 ID' in e for e in S.validate(self.data)))

    def test_no_kpi_fails(self):
        del self.data['use_cases'][0]['test']['definition']
        self.assertTrue(any('definition' in e for e in S.validate(self.data)))

    def test_no_baseline_value_allowed_with_method(self):
        self.assertIsNone(self.data['use_cases'][0]['test']['baseline']['value'])
        self.assertEqual(S.validate(self.data), [])
        self.data['use_cases'][0]['test']['baseline']['method'] = ''
        self.assertTrue(any('基线' in e for e in S.validate(self.data)))

    def test_formal_plan_needs_confirmation(self):
        self.data['mode'] = 'action_plan'
        self.assertTrue(any('未确认' in e for e in S.validate(self.data)))
        self.data['use_cases'][0]['confirmation'] = 'confirmed'
        self.assertEqual(S.validate(self.data), [])

    def test_unmapped_confirmed_use_fails(self):
        u = copy.deepcopy(self.data['use_cases'][0]);u['id'] = 'U02';u['confirmation'] = 'confirmed'
        self.data['use_cases'].append(u)
        self.assertTrue(any('U02 未挂' in e for e in S.validate(self.data)))

    def test_scored_dimension_needs_basis(self):
        del self.data['use_cases'][0]['assessment']['basis']['value']
        self.assertTrue(any('缺依据' in e for e in S.validate(self.data)))


class WorkbookTests(unittest.TestCase):
    def setUp(self):
        self.raw = W.DEFAULT_TEMPLATE.read_bytes()

    def test_three_sheets_images_freezes_headers(self):
        with zipfile.ZipFile(io.BytesIO(self.raw)) as z:
            workbook = ET.fromstring(z.read('xl/workbook.xml'))
            self.assertEqual(len(workbook.findall('s:sheets/s:sheet', NS)), 3)
            self.assertEqual(len([n for n in z.namelist() if n.startswith('xl/media/')]), 2)
            sheet = ET.fromstring(z.read('xl/worksheets/sheet3.xml'))
            self.assertEqual(len(sheet.findall('s:sheetData/s:row', NS)[0].findall('s:c', NS)), 12)
            for name, expected in [('sheet2.xml', 'D2'), ('sheet3.xml', 'F2')]:
                el = ET.fromstring(z.read('xl/worksheets/' + name))
                self.assertEqual(el.find('s:sheetViews/s:sheetView/s:pane', NS).get('topLeftCell'), expected)

    def test_parameterization_preserves_other_parts(self):
        result = W.parameterize(self.raw, [2029, 2030, 2031])
        with zipfile.ZipFile(io.BytesIO(self.raw)) as a, zipfile.ZipFile(io.BytesIO(result)) as b:
            for name in a.namelist():
                if name not in ('xl/worksheets/sheet1.xml', 'xl/worksheets/sheet3.xml'):
                    self.assertEqual(a.read(name), b.read(name), name)
            self.assertIn('2029年'.encode(), b.read('xl/worksheets/sheet1.xml'))
            self.assertIn('已完成,待确认,2029年,2030年,2031年'.encode(), b.read('xl/worksheets/sheet3.xml'))
            for name in b.namelist():
                if name.endswith('.xml'):
                    ET.fromstring(b.read(name))

    def test_no_client_or_year_in_active_template(self):
        with zipfile.ZipFile(io.BytesIO(self.raw)) as z:
            for name in z.namelist():
                if name.startswith('xl/') and name.endswith('.xml'):
                    text = z.read(name).decode()
                    self.assertNotRegex(text, '宁波|2026|2027|2028')

    def test_invalid_years(self):
        for years in [[2029, 2029, 2031], [2030, 2029, 2031], [100, 2029, 2030]]:
            with self.assertRaises(ValueError):
                W.parameterize(self.raw, years)

    def test_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'copy.xlsx';p.write_bytes(b'keep')
            r = cli('scripts/prepare_workbook.py', '--output', str(p), '--years', '2029', '2030', '2031')
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(p.read_bytes(), b'keep')


class StaticTests(unittest.TestCase):
    def test_local_markdown_links(self):
        errors = []
        files = list(ROOT.rglob('*.md'))
        for p in files:
            for href in re.findall(r'(?<!!)\[[^\]]+\]\(([^)]+)\)', p.read_text()):
                if '://' in href or href.startswith('#'):
                    continue
                if not (p.parent / unquote(href.split('#')[0])).exists():
                    errors.append('{}: {}'.format(p.relative_to(ROOT.parent), href))
        self.assertEqual(errors, [])

    def test_no_transplanted_brand(self):
        forbidden = ['源子', 'Metainflow', '838000702', '联系人：Neil']
        for p in list(ROOT.rglob('*.md')) + list(ROOT.rglob('*.html')) + list(ROOT.rglob('*.py')):
            if p == Path(__file__).resolve():
                continue
            for word in forbidden:
                self.assertNotIn(word, p.read_text(), str(p))

    def test_primary_entry_and_template_reachable(self):
        self.assertTrue((ROOT / 'SKILL.md').is_file())
        self.assertTrue((ROOT / 'assets/templates/确认表模板.xlsx').is_file())
        self.assertFalse((ROOT / 'references/profiles/power-grid').exists())
        self.assertFalse((ROOT / 'assets/power-grid').exists())
        self.assertNotIn('power-grid', (ROOT / 'SKILL.md').read_text())

    def test_python_38_syntax(self):
        for p in list((ROOT / 'scripts').glob('*.py')) + list((ROOT / 'tests').glob('*.py')):
            ast.parse(p.read_text(), feature_version=(3, 8))


class DemoTests(unittest.TestCase):
    def test_two_actual_rounds(self):
        result = D.run()
        self.assertEqual(result['data_kind'], 'synthetic')
        first, second = result['rounds']
        self.assertEqual(first['metrics']['development']['recall'], .25)
        self.assertEqual(second['metrics']['holdout']['recall'], 1.0)
        self.assertEqual(len(first['rows']), 32)
        self.assertEqual([r['gold_risk'] for r in first['rows']], [r['gold_risk'] for r in second['rows']])
        self.assertIsNone(result['business_kpi']['value'])


if __name__ == '__main__':
    unittest.main()
