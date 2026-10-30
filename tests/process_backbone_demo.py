#!/usr/bin/env python3
"""Reproducible SYNTHETIC enterprise-tailoring demo using bundled ecommerce data.
Not customer research, a live LLM test, or a claim of realized business benefit.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'scripts/process_framework_tools.py'


def save(path, data):
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def run(output):
    output = output.resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('演示产物写项目/临时目录，不写回技能')
    output.mkdir(parents=True, exist_ok=False)
    log = []

    def call(*args, tool=TOOL):
        p = subprocess.run([sys.executable, '-B', str(tool), *map(str, args)], capture_output=True, text=True)
        if p.returncode:
            raise ValueError(p.stdout + p.stderr)
        value = json.loads(p.stdout)
        log.append({'tool': tool.name, 'arguments': list(map(str, args)), 'exit_code': p.returncode,
                    'status': value.get('status'), 'valid': value.get('valid'), 'total': value.get('total')})
        return value

    a = output / '企业流程骨架_v1.json'
    call('init-project', '--industry', '电商', '--model', 'marketplace', '--company-name', '合成平台企业（非真实客户）',
         '--root-id', '10.3', '--depth', '2', '--output', a)
    arch = json.loads(a.read_text(encoding='utf-8'))
    nodes = {n['source_refs'][0]['hierarchy_id']: n for n in arch['processes']}
    root, task = nodes['10.3']['id'], nodes['10.3.1']['id']
    synthetic = [{'kind': 'synthetic', 'locator': 'tests/process_backbone_demo.py', 'note': '合成假设，不是真实访谈或客户确认'}]
    ops = [
        {'op': 'rename', 'id': root, 'name': '管理本平台商家结算与异常处置', 'reason': '合成模式：第三方商家平台，裁剪企业业务命名', 'evidence': synthetic},
        {'op': 'update', 'id': task, 'reason': '合成假设：部分差异涉及非结构化条款和退补说明，不仅是固定算术', 'evidence': synthetic,
         'changes': {'name': '研判结算差异与核验依据', 'perspective': 'both', 'ai_assessment': 'candidate',
                     'current_state': '合成假设：财务人员人工查阅多源记录，实际频次、耗时及差错未知。',
                     'target_design': {'ai_work': '解释差异、引用证据、列待核验事项，不直接算定付款授权',
                                       'human_work': '复核证据、解释合同适用性并决定处置',
                                       'handoff': '低置信或证据冲突转人工；任何资金动作由获授权人员及原支付系统执行',
                                       'feedback': '记录人审修改原因，补充获准知识并回归验证'}}},
        {'op': 'add', 'reason': '合成目标流程：保留人工授权，不把研判等同于划款', 'evidence': synthetic,
         'node': {'id': 'BP-T-REVIEW', 'name': '人工复核并批准异常处置', 'parent_id': root, 'kind': 'task', 'perspective': 'target',
                  'roles': ['获授权财务复核岗位（合成假设）'], 'inputs': ['差异与证据清单'], 'outputs': ['复核结论及处置意见'], 'ai_assessment': 'no_ai_needed'}},
        {'op': 'add', 'reason': '合成目标流程：把复核反馈接回知识与测试，不自动改变付款规则', 'evidence': synthetic,
         'node': {'id': 'BP-T-FEEDBACK', 'name': '记录反馈并维护回归样本', 'parent_id': root, 'kind': 'task', 'perspective': 'target',
                  'inputs': ['复核修改与原因'], 'outputs': ['获准知识修订及回归样本'], 'ai_assessment': 'no_ai_needed'}},
        {'op': 'relate', 'reason': '合成目标交接：AI给依据，人负责复核', 'relation': {'id': 'REL-T-01', 'type': 'handoff', 'from': task, 'to': 'BP-T-REVIEW', 'perspective': 'target'}},
        {'op': 'relate', 'reason': '合成目标交接：处置后记录反馈', 'relation': {'id': 'REL-T-02', 'type': 'sequence', 'from': 'BP-T-REVIEW', 'to': 'BP-T-FEEDBACK', 'perspective': 'target'}},
        {'op': 'relate', 'reason': '合成目标闭环：反馈修订需重新验证', 'relation': {'id': 'REL-T-03', 'type': 'feedback', 'from': 'BP-T-FEEDBACK', 'to': task, 'perspective': 'target'}}]
    operation_file = output / '裁剪操作.json'; save(operation_file, ops)
    b = output / '企业流程骨架_v2.json'
    call('tailor', '--project', a, '--operations', operation_file, '--output', b)
    final = json.loads(b.read_text(encoding='utf-8'))
    ref = nodes['10.3.1']['source_refs'][0]
    framework_evidence = {'kind': 'framework_reference', 'dataset_id': ref['dataset_id'], 'version': ref['version'],
                          'source_type': ref['source_type'], 'is_official': ref['is_official'],
                          'locator': ref['reference_key'], 'purpose': 'architecture', 'proves_customer_fact': False}
    s = {'mode': 'opportunity', 'process_architecture': final,
         'big_scenarios': [{'id': 'SYN-S01', 'name': '商家结算差异人机协同闭环', 'focus': 'main',
                            'scope': '合成平台商家结算差异研判、复核和反馈，不自动划款',
                            'current_state': '仅合成假设，真实处理方式与基线待调研',
                            'future_mode': 'AI提出证据化差异意见，财务复核处置，反馈驱动知识和测试迭代',
                            'business_process_refs': [root, task, 'BP-T-REVIEW', 'BP-T-FEEDBACK'],
                            'kpis': [{'metric': '人审后差异处理活跃工时', 'definition': '同一差异从人工查阅/AI辅助开始到完成复核，累计人工操作、复核及返工分钟；等待时间另报',
                                      'unit': '分钟/差异项', 'baseline_method': '获准历史样本同任务人工对照，按差异类型分组计时；当前未测'}],
                            'states': [{'phase': '近期', 'goal': '小样本受控研判及人工复核，取得质量与工时对照', 'use_case_ids': ['SYN-U01']},
                                       {'phase': '中期', 'goal': '在结算岗位受控复用，保留人工授权与例外接管', 'use_case_ids': ['SYN-U01']},
                                       {'phase': '远期', 'goal': '形成研判—复核—反馈—回归的稳定业务闭环', 'use_case_ids': ['SYN-U01']}]}],
         'use_cases': [{'id': 'SYN-U01', 'parent_id': 'SYN-S01', 'name': '商家结算差异研判数字员工', 'form': 'digital_employee',
                        'business_process_refs': [task], 'business_task': '解释非结构化条款、退补说明与账单差异，形成待复核意见',
                        'input': '获准订单/履约/退补记录、账单和合同规则；当前未接入真实资料',
                        'ai_work': '语义判读差异原因，引用原证据，标明缺项和不确定性',
                        'human_work': '核对合同适用性、金额和证据，决定异常处置与付款授权',
                        'handoff': '证据冲突、低置信与所有资金动作转人工及原授权系统',
                        'output': '带证据定位及不确定项的差异研判清单', 'user': '财务结算岗位（合成假设）',
                        'source_line': 'both', 'evidence': [framework_evidence] + synthetic,
                        'confirmation': 'hypothesis', 'build_status': 'proposed',
                        'test': {'kpi': '关键差异原因识别召回率', 'definition': '正确识别的关键差异项/人工金标准关键差异项', 'unit': '比例',
                                 'sample': '待取获准历史差异样本，按类型分组、双人标注仲裁；当前未接入真实数据',
                                 'baseline': {'value': None, 'method': '同样本人工独立处理，记录核验、复核和返工时间及遗漏'},
                                 'threshold': {'value': None, 'status': 'pending'},
                                 'test_method': '按原证据金标准评估原因识别、证据正确性及含人审返工的业务工时',
                                 'failure': '关键依据错误、遗漏或证据冲突不得自动放行；不得自动划款', 'iterations': []},
                        'assessment': {'value': None, 'feasibility': None, 'data': None, 'basis': {}},
                        'readiness': {'compliance': None, 'owner': None, 'data_access': None, 'dependencies': None}}]}
    scenario_file = output / '场景投影.json'; save(scenario_file, s)
    coverage = call('coverage', '--project', b, '--scenarios', scenario_file)
    save(output / '挂接检查.json', coverage)
    validation = call('validate', scenario_file, tool=ROOT / 'scripts/scenario_tools.py')
    save(output / '联合校验.json', validation)
    call('project-get', '--project', b, '--id', task)
    save(output / '调用记录.json', log)
    return {'status': 'ok', 'company': '合成平台企业（非真实客户）', 'original_processes': len(arch['processes']),
            'tailored_processes': len(final['processes']), 'target_relations': len(final['relations']),
            'big_scenarios': 1, 'use_cases': 1, 'combined_valid': validation['valid'],
            'real_customer_facts_validated': False, 'real_ai_effect_tested': False, 'output': str(output)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args()
    try:
        print(json.dumps(run(a.output_dir), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as e:
        print(json.dumps({'status': 'error', 'message': str(e)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    sys.exit(main())
