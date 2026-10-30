#!/usr/bin/env python3
"""Two-round synthetic test-double demo, NOT a real LLM or production benchmark."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def dataset():
    terms = ['付款期限', '结算周期', '账期', '支付期限']
    rows = []
    for term_index, term in enumerate(terms):
        for j in range(8):
            days = 90 if j % 2 == 0 else 30
            # The fixed split contains both positive and negative examples for all terms.
            rows.append({'id': 'T{:02d}'.format(term_index * 8 + j + 1),
                         'split': 'development' if j < 4 else 'holdout',
                         'text': '合成合同：货物验收后，{}为{}天。'.format(term, days),
                         'gold_risk': days > 45})
    return rows


def predict(text, version):
    alternatives = '付款期限' if version == 1 else '付款期限|结算周期|账期|支付期限'
    match = re.search('(?:' + alternatives + r')为(\d+)天', text)
    return bool(match and int(match.group(1)) > 45)


def evaluate(rows, version):
    results = [dict(row, predicted_risk=predict(row['text'], version)) for row in rows]
    metrics = {}
    for split in ('development', 'holdout'):
        group = [r for r in results if r['split'] == split]
        tp = sum(r['gold_risk'] and r['predicted_risk'] for r in group)
        fn = sum(r['gold_risk'] and not r['predicted_risk'] for r in group)
        fp = sum(not r['gold_risk'] and r['predicted_risk'] for r in group)
        tn = sum(not r['gold_risk'] and not r['predicted_risk'] for r in group)
        metrics[split] = {'tp': tp, 'fn': fn, 'fp': fp, 'tn': tn,
                          'recall': tp / (tp + fn) if tp + fn else None,
                          'precision': tp / (tp + fp) if tp + fp else None}
    return {'version': 'rule-test-double-v{}'.format(version), 'metrics': metrics, 'rows': results}


def run():
    rows = dataset()
    rounds = [evaluate(rows, v) for v in (1, 2)]
    return {'data_kind': 'synthetic', 'engine': 'rule test double, not LLM',
            'dataset_sha256': hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            'protocol': 'fixed 16-development/16-holdout; constructed by author, not independent production blind test',
            'use_case_id': 'U01', 'kpi': '关键账期风险召回率', 'hypothesis_threshold': 0.9,
            'rounds': rounds, 'diagnosis_round_1': '同义账期表达漏检',
            'change_round_2': '扩展语义表达覆盖，维持同一金标准和评测协议',
            'technical_decision': '测试替身流程可继续，不代表真实LLM通过',
            'business_kpi': {'name': '人审后总耗时', 'value': None,
                             'baseline_method': '获准真实样本由审核员计时，纳入复核与返工'},
            'next': ['取得真实合同授权与业务负责人', '双人标注及仲裁',
                     '受控真实模型Demo及留出测试', '测量人审后总耗时', '客户确认阈值再决定扩围']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    # Exclusive create so previous round evidence cannot be silently replaced.
    with a.output.open('x', encoding='utf-8') as handle:
        json.dump(run(), handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(str(a.output))


if __name__ == '__main__':
    main()
