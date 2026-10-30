#!/usr/bin/env python3
"""Optional scoring and projection validation. Python 3.8+, no third-party packages."""
import argparse
import importlib.util
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path
import sys

WEIGHTS = {'value': Decimal('0.4'), 'feasibility': Decimal('0.3'), 'data': Decimal('0.3')}
GATES = ('compliance', 'owner', 'data_access', 'dependencies')
PHASES = {'近期', '中期', '远期'}

# Works both as a CLI and when existing tests load this module by file path.
_spec = importlib.util.spec_from_file_location('_scenario_process_contract', Path(__file__).with_name('process_contract.py'))
_process_contract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_process_contract)


def score(assessment, readiness=None):
    if not isinstance(assessment, dict):
        raise ValueError('assessment 必须为对象')
    values = {}
    missing = []
    for key in WEIGHTS:
        value = assessment.get(key)
        if value is None:
            missing.append(key)
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError('{} 须为数字或 null'.format(key))
        try:
            value = Decimal(str(value))
        except InvalidOperation:
            raise ValueError('非法评分')
        if not value.is_finite() or not Decimal(1) <= value <= Decimal(5):
            raise ValueError('{} 须为 1 至 5'.format(key))
        values[key] = value
    if readiness is None:
        readiness = {}
    if not isinstance(readiness, dict):
        raise ValueError('readiness 必须为对象')
    for key in GATES:
        value = readiness.get(key)
        if value is not None and type(value) is not bool:
            raise ValueError('{} 就绪状态须为 true/false/null'.format(key))
    held = [k for k in GATES if readiness.get(k) is False]
    unknown = [k for k in GATES if readiness.get(k) is None]
    state = 'held' if held else 'pending' if unknown else 'ready_for_decision'
    if missing:
        raw, display, priority = None, None, '待评估'
    else:
        total = sum(values[k] * w for k, w in WEIGHTS.items())
        raw = float(total)
        display = format(total.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP), '.1f')
        priority = 'P0' if total >= 4 else 'P1' if total >= 3 else 'P2'
    return {'raw_score': raw, 'display_score': display, 'priority': priority,
            'missing': missing, 'readiness': state, 'held_gates': held,
            'unknown_gates': unknown, 'schedule': '由客户另行确认；评分不推定月份或年度'}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate(data):
    """Validate deterministic structure; not a replacement for evidence/semantic review."""
    errors = []
    if not isinstance(data, dict):
        return ['顶层必须为对象']
    mode = data.get('mode')
    if mode not in ('opportunity', 'action_plan'):
        errors.append('mode 须为 opportunity 或 action_plan')
    bigs, uses = data.get('big_scenarios'), data.get('use_cases')
    if not isinstance(bigs, list) or not isinstance(uses, list):
        return errors + ['big_scenarios、use_cases 须为数组']
    by_big, by_use, seen = {}, {}, set()
    for label, items, target in [('大场景', bigs, by_big), ('用例', uses, by_use)]:
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append('{} {} 须为对象'.format(label, i)); continue
            ident = item.get('id')
            if not nonempty(ident):
                errors.append('{} ID 缺失'.format(label)); continue
            if ident in seen:
                errors.append('重复 ID: ' + ident)
            seen.add(ident)
            target[ident] = item
            if not nonempty(item.get('name')):
                errors.append(ident + ' 名称缺失')
    referenced = set()
    for ident, big in by_big.items():
        for key in ('scope', 'current_state', 'future_mode'):
            if not nonempty(big.get(key)):
                errors.append('{} 缺 {}'.format(ident, key))
        if big.get('focus') not in ('main', 'appendix'):
            errors.append(ident + ' 缺主副表标记')
        kpis = big.get('kpis')
        if not isinstance(kpis, list) or not kpis:
            errors.append(ident + ' 缺业务 KPI')
        else:
            for kpi in kpis:
                if not isinstance(kpi, dict) or any(not nonempty(kpi.get(k)) for k in ('metric', 'definition', 'unit', 'baseline_method')):
                    errors.append(ident + ' KPI 口径／单位／基线方法不完整')
        states = big.get('states')
        if not isinstance(states, list) or len(states) != 3:
            errors.append(ident + ' 须有三期状态'); continue
        if any(not isinstance(s, dict) for s in states):
            errors.append(ident + ' 状态须为对象'); continue
        if {s.get('phase') for s in states if isinstance(s.get('phase'), str)} != PHASES:
            errors.append(ident + ' 阶段须为近期／中期／远期各一项')
        for state in states:
            if not nonempty(state.get('goal')):
                errors.append(ident + ' 缺目标态')
            refs = state.get('use_case_ids')
            if not isinstance(refs, list) or not refs:
                errors.append(ident + ' 目标态无用例支撑'); continue
            if any(not isinstance(r, str) for r in refs):
                errors.append(ident + ' 用例引用须为字符串'); continue
            if len(set(refs)) != len(refs):
                errors.append(ident + ' 同一期重复引用用例')
            for ref in refs:
                referenced.add(ref)
                if ref not in by_use:
                    errors.append('孤儿任务／引用: ' + ref)
                elif by_use[ref].get('confirmation') == 'excluded':
                    errors.append('引用已排除用例: ' + ref)
                elif mode == 'action_plan' and by_use[ref].get('confirmation') != 'confirmed':
                    errors.append('正式任务未确认: ' + ref)
    for ident, use in by_use.items():
        if use.get('parent_id') not in by_big:
            errors.append(ident + ' 无大场景主归属')
        if use.get('form') not in ('assistant', 'digital_employee', 'agent'):
            errors.append(ident + ' 载体类型非法')
        if use.get('source_line') not in ('pain', 'trend', 'both'):
            errors.append(ident + ' 缺来源主线')
        if use.get('confirmation') not in ('hypothesis', 'supported', 'confirmed', 'excluded'):
            errors.append(ident + ' 确认状态非法')
        if use.get('build_status') not in ('existing', 'in_progress', 'proposed'):
            errors.append(ident + ' 建设现状非法')
        if use.get('confirmation') != 'excluded' and ident not in referenced:
            errors.append(ident + ' 未挂到任何目标态')
        if not isinstance(use.get('evidence'), list):
            errors.append(ident + ' 证据须为数组，可为空但不能伪造')
        for key in ('business_task', 'input', 'ai_work', 'human_work', 'handoff', 'output', 'user'):
            if not nonempty(use.get(key)):
                errors.append('{} 缺 {}'.format(ident, key))
        test = use.get('test')
        if not isinstance(test, dict):
            errors.append(ident + ' 缺测试基准'); continue
        for key in ('kpi', 'definition', 'unit', 'sample', 'test_method', 'failure'):
            if not nonempty(test.get(key)):
                errors.append('{} 测试缺 {}'.format(ident, key))
        baseline = test.get('baseline')
        if not isinstance(baseline, dict) or not nonempty(baseline.get('method')):
            errors.append(ident + ' 缺获取基线的方法')
        threshold = test.get('threshold')
        if not isinstance(threshold, dict) or threshold.get('status') not in ('confirmed', 'hypothesis', 'pending'):
            errors.append(ident + ' 缺阈值与性质')
        if not isinstance(test.get('iterations'), list):
            errors.append(ident + ' iterations 须为数组，未测可空')
        try:
            score(use.get('assessment'), use.get('readiness'))
        except ValueError as e:
            errors.append('{}: {}'.format(ident, e))
        assessment = use.get('assessment', {})
        basis = assessment.get('basis') if isinstance(assessment, dict) else None
        if isinstance(assessment, dict):
            for key in WEIGHTS:
                if assessment.get(key) is not None and (not isinstance(basis, dict) or not nonempty(basis.get(key))):
                    errors.append('{} 评分 {} 缺依据／假设'.format(ident, key))
    errors.extend(_process_contract.validate_process_projection(data))
    return errors


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['score', 'validate'])
    p.add_argument('input', type=Path)
    a = p.parse_args(argv)
    try:
        data = json.loads(a.input.read_text(encoding='utf-8'))
        if a.command == 'score':
            result = score(data.get('assessment', data), data.get('readiness'))
            code = 0
        else:
            errors = validate(data)
            result, code = {'valid': not errors, 'errors': errors}, int(bool(errors))
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return code
    except (OSError, ValueError, TypeError, AttributeError) as e:
        print(str(e), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
