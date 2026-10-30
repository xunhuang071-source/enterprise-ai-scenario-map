#!/usr/bin/env python3
"""Bundled process frameworks -> tailored enterprise architecture -> scenario linkage.
Python 3.8+, standard library only. Industry corpus is read-only. Project writes
require an explicit output path and never overwrite an existing file.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

from process_contract import validate_architecture, validate_process_projection, framework_evidence_errors, text

HERE = Path(__file__).resolve().parent
DEFAULT_LIBRARY = HERE.parent / 'assets' / 'process-frameworks'
MODELS = {'platform': 'marketplace', '平台': 'marketplace', '平台型': 'marketplace',
          '自营': 'self_operated', '自营零售': 'self_operated', '代运营': 'agency',
          'marketplace': 'marketplace', 'self_operated': 'self_operated', 'agency': 'agency'}


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def readjson(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def lines(path):
    with Path(path).open(encoding='utf-8') as f:
        return [json.loads(s) for s in f if s.strip()]


def load_backend(name):
    spec = importlib.util.spec_from_file_location('_enterprise_' + name, HERE / 'backends' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def library_root(value=None):
    return Path(value or os.environ.get('ENTERPRISE_AI_FRAMEWORK_HOME') or DEFAULT_LIBRARY).resolve()


def resources(root):
    if not (root / 'registry.json').is_file():
        raise FileNotFoundError('技能内置资料注册表缺失。请恢复完整技能资源包或显式指定--library；不自动回退Downloads。')
    entries = readjson(root / 'registry.json')['resources']
    result = {}
    for entry in entries:
        path = (root / entry['path']).resolve()
        if root != path and root not in path.parents:
            raise ValueError('资源路径越出技能资料目录')
        result[entry['id']] = (entry, path)
    return result


def pcf_metadata(root):
    entries = []
    for item in readjson(root / 'catalog.json')['datasets']:
        directory = (root / item['directory']).resolve()
        if root not in directory.parents:
            raise ValueError('数据集路径越出资料目录')
        entries.append((item, readjson(directory / 'metadata.json'), directory))
    return entries


def choose_dataset(root, dataset=None, industry=None):
    entries = pcf_metadata(root)
    if dataset:
        entries = [e for e in entries if e[1]['dataset_id'] == dataset]
    if industry:
        term = industry.casefold()
        exact = [e for e in entries if any(term == a.casefold() for a in e[1]['aliases'])]
        entries = exact or [e for e in entries if any(term in a.casefold() for a in e[1]['aliases'])]
    if len(entries) != 1:
        raise ValueError('请通过catalog选定唯一数据集；不自动选择新版本或相近行业。候选: ' + ', '.join(e[1]['dataset_id'] for e in entries))
    return entries[0]


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(root):
    # Cache is never a second source of truth, including equal-node-count updates.
    paths = [root / 'catalog.json', root / '检索别名.json'] + [p for p in (root / '数据').rglob('*') if p.suffix in ('.json', '.jsonl')]
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode('utf-8'))
        digest.update(file_sha(path).encode('ascii'))
    return digest.hexdigest()


def cache_valid(root):
    db = root / '检索' / 'apqc.sqlite'
    receipt = root / '检索' / 'cache-receipt.json'
    try:
        info = readjson(receipt)
        return info['canonical_digest'] == canonical_digest(root) and info['sqlite_sha256'] == file_sha(db)
    except (OSError, ValueError, KeyError):
        return False


def open_pcf(root, force_memory=False):
    backend = load_backend('pcf_query')
    if not force_memory and (root / '检索' / 'apqc.sqlite').is_file() and cache_valid(root):
        q = backend.Query(root)
        # Cheap signature prevents a stale cache hiding a newly imported dataset.
        expected = {m['dataset_id']: m['statistics']['node_count'] for _, m, _ in pcf_metadata(root)}
        cached = {k: v['meta']['statistics']['node_count'] for k, v in q.datasets.items()}
        if cached == expected:
            return q, 'bundled_readonly_sqlite'
        q.c.close()
    q = backend.Query.__new__(backend.Query)
    q.root = root
    q.c = load_backend('pcf_index').memory_index(root)
    q.datasets = {r['dataset_id']: dict(r) for r in q.c.execute('select * from datasets')}
    for d in q.datasets.values():
        d['meta'] = json.loads(d['meta']); d['aliases'] = json.loads(d['aliases'])
    q.fts = q.c.execute("select value from build_info where key='fts5'").fetchone()[0] == 'True'
    q.ancestors = {}
    return q, 'memory_from_canonical_jsonl'


def identity(meta, resource='pcf'):
    return {'resource_id': resource, 'framework_family': meta.get('framework_family') or ('APQC' if resource == 'pcf' else 'SCOR'), 'dataset_id': meta['dataset_id'], 'version': meta['version'],
            'file_year': meta['file_year'], 'source_type': meta.get('source_type', 'apqc_excel'),
            'is_official': meta.get('is_official', True), 'date_type': meta.get('date_type'),
            'year_basis': meta.get('year_basis'), 'complete_catalog': meta.get('complete_catalog')}


def catalog(root, args):
    out = []
    for rid, (entry, path) in resources(root).items():
        if rid == 'pcf' and (path / 'catalog.json').exists():
            for _, m, _ in pcf_metadata(path):
                if args.dataset and m['dataset_id'] != args.dataset:
                    continue
                if args.industry and not any(args.industry.casefold() in a.casefold() for a in m['aliases']):
                    continue
                out.append(dict(identity(m), name=m['industry_zh'], node_count=m['statistics']['node_count'],
                                available=True, business_models=m.get('business_models', {})))
        elif rid == 'scor' and not args.dataset and (not args.industry or args.industry in ('供应链', 'SCOR', 'scor')):
            m = readjson(path / 'metadata.json') if (path / 'metadata.json').exists() else dict(entry['expected_scope'], dataset_id='scor-ds__v14.0__2025__en__introduction')
            out.append(dict(identity(m, 'scor'), name='SCOR-DS介绍册', available=(path / 'records.jsonl').is_file(),
                            is_official=True, complete_catalog=False, record_count=m['record_count'],
                            distribution=entry['distribution'], source_type='framework_introduction'))
    return page_result(out, args, scope_notice='行业底座用于企业裁剪，不是客户现状；未内置工程/EPC专版。')


def doctor(root, verify=False):
    checks = []
    for rid, (entry, path) in resources(root).items():
        needed = ['catalog.json'] if rid == 'pcf' else ['metadata.json', 'records.jsonl', 'pages.jsonl']
        missing = [name for name in needed if not (path / name).is_file()]
        if rid == 'pcf' and not missing:
            for item in readjson(path / 'catalog.json')['datasets']:
                for name in ('metadata.json', 'processes.jsonl'):
                    if not (path / item['directory'] / name).is_file():
                        missing.append(item['directory'] + '/' + name)
        checks.append({'resource_id': rid, 'available': not missing, 'missing': missing,
                       'distribution': entry.get('distribution'),
                       'hint': '受限SCOR资料未随Git同步；请将获准使用的完整AI版导入技能scor-intro目录。' if missing and rid == 'scor' else None})
    failures = []
    checked = 0
    if verify:
        items = readjson(root / 'manifest.json')['files']
        if (root / 'local-import-receipt.json').is_file():
            merged = {i['path']: i for i in items}
            for item in readjson(root / 'local-import-receipt.json')['files']:
                merged.setdefault(item['path'], item)
            items = list(merged.values())
        for item in items:
            p = (root / item['path']).resolve()
            if root not in p.parents:
                raise ValueError('校验清单路径越出资料目录')
            checked += 1
            if not p.is_file() or file_sha(p) != item['sha256']:
                failures.append(item['path'])
    return {'status': 'ok' if all(c['available'] for c in checks) and not failures else 'incomplete',
            'resources': checks, 'hash_check_requested': verify, 'hash_checked_files': checked, 'hash_failures': failures,
            'raw_pdf_excel_required_for_queries': False,
            'notice': '缺少资料不等于可以跳过企业流程建模；改用客户材料并明示框架缺口。'}


def page_result(rows, args, **extra):
    total = len(rows)
    selected = rows[args.offset:args.offset + args.limit]
    return {'status': 'ok' if total else 'not_found', 'total': total, 'offset': args.offset,
            'returned': len(selected), 'next_offset': args.offset + len(selected) if args.offset + len(selected) < total else None,
            'results': selected, **extra}


def query_framework(root, args):
    entries = resources(root)
    rid = args.framework
    if rid not in entries:
        raise ValueError('未知框架资源: ' + rid)
    _, path = entries[rid]
    if rid == 'pcf':
        if args.command == 'page':
            return {'status': 'unsupported_operation', 'message': 'PCF结构化包按节点及Excel出处查询；物理page查询仅适用于SCOR介绍册。'}
        backend = load_backend('pcf_query')
        a = backend.parser().parse_args(['--root', str(path), args.command])
        for key in ('industry', 'dataset', 'version', 'year', 'id', 'pcf_id', 'q', 'depth', 'limit', 'offset', 'max_chars', 'full', 'all_industries'):
            setattr(a, key, getattr(args, key))
        q, mode = open_pcf(path, args.memory)
        try:
            selected = q.resolve(a)
            result = q.run(a)
            if len(selected) == 1:
                result['selected_dataset'] = identity(selected[0]['meta'])
        finally:
            q.c.close()
        result['resource_id'] = rid
        result['index_mode'] = mode
        for r in result.get('results', []):
            if 'source' in r:
                r['source']['original_locator_only'] = r.get('source_type', 'apqc_excel') == 'apqc_excel'
                r['source']['raw_excel_bundled'] = False
            if r.get('node_id'):
                r['reference_key'] = r['node_id']
        result['usage'] = '行业底座；先裁剪成企业流程骨架，再做任务和AI目标流程设计。查询命中不证明客户事实。'
        return result
    if not (path / 'records.jsonl').exists():
        return {'status': 'resource_missing', 'resource_id': 'scor', 'results': [],
                'message': 'SCOR受限本地资料未安装；不联网补造，不假装有完整模型。'}
    command = args.command
    if command in ('children', 'subtree', 'compare'):
        return {'status': 'unsupported_operation', 'complete_catalog': False, 'message': '介绍册没有完整子过程树；请查询过程概念、示例或原页，不生成替代目录。'}
    mapped = 'list' if command in ('outline', 'metrics') else command
    cmd = [sys.executable, '-B', str(HERE / 'backends/scor_query.py'), mapped, '--root', str(path),
           '--limit', str(min(args.limit, 100)), '--offset', str(args.offset), '--max-chars', str(min(args.max_chars, 100000))]
    kind = args.kind or ('process_concept' if command == 'outline' else 'metric_reference' if command == 'metrics' else None)
    for flag, value in [('--q', args.q), ('--type', kind), ('--code', args.code), ('--id', args.id), ('--page', args.page)]:
        if value is not None:
            cmd.extend([flag, str(value)])
    if args.full:
        cmd.append('--full')
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if not result.stdout.strip():
        raise ValueError('SCOR查询失败: ' + result.stderr[:300])
    out = json.loads(result.stdout)
    out.update(resource_id='scor', source_type='framework_introduction', is_official=True,
               distribution='restricted_local_only', outline_kind='concepts_only' if command == 'outline' else None)
    return out


def normalize_model(value):
    if value is None:
        return None
    if value not in MODELS:
        raise ValueError('经营模式需明确为self_operated/marketplace/agency；B2B/B2C不足以区分此三类责任。')
    return MODELS[value]


def reference(meta, node):
    ref = identity(meta)
    ref.update(reference_key=node['node_id'], hierarchy_id=node['hierarchy_id'], pcf_id=node.get('pcf_id'),
               locator={'source_file': meta['source_file'], 'source_sheet': node.get('source_sheet'), 'source_row': node.get('source_row')})
    if node.get('reference_id'):
        ref['local_reference_id'] = node['reference_id']
        ref['source_references'] = node.get('source_references', [])
    return ref


def init_project(root, args):
    if args.framework == 'scor':
        return init_scor_project(root, args)
    path = resources(root)['pcf'][1]
    _, m, directory = choose_dataset(path, args.dataset, args.industry)
    if not 1 <= args.depth <= 3:
        raise ValueError('初稿depth范围1—3；先构建可调研骨架，细节按需深化。')
    model = normalize_model(args.model)
    all_nodes = lines(directory / 'processes.jsonl')
    selected = [n for n in all_nodes if n['level'] <= args.depth]
    if args.root_id:
        b = next((n for n in all_nodes if n['hierarchy_id'] == args.root_id or n['node_id'] == args.root_id), None)
        if b is None:
            raise ValueError('root-id不存在；顶层使用原始层级编号如10.0')
        prefix = b['hierarchy_id'][:-2] if b['level'] == 1 else b['hierarchy_id']
        selected = [n for n in all_nodes if (n['node_id'] == b['node_id'] or n['hierarchy_id'].startswith(prefix + '.')) and n['level'] < b['level'] + args.depth]
    if model:
        selected = [n for n in selected if not n.get('applicable_business_models') or model in n['applicable_business_models']]
    if not selected:
        raise ValueError('选定范围没有适用节点；请核对行业、模式和范围。')
    mapping = {n['node_id']: 'BP-{:04d}'.format(i + 1) for i, n in enumerate(selected)}
    processes = []
    for i, n in enumerate(selected):
        ref = reference(m, n)
        # Values imported from frameworks remain industry-suggested, not customer facts.
        processes.append({'id': mapping[n['node_id']], 'parent_id': mapping.get(n['parent_id']),
                          'kind': 'domain' if n['level'] == 1 else 'process' if n['level'] == 2 else 'task',
                          'perspective': 'current', 'name': n.get('name_zh') or n['name_original'], 'active': True,
                          'confirmation': 'hypothesis', 'ai_assessment': 'unknown', 'order': i,
                          'scope': n.get('description'), 'roles': n.get('roles', []), 'inputs': n.get('inputs', []),
                          'outputs': n.get('outputs', []), 'systems': n.get('related_systems', []),
                          'business_object': None, 'trigger': None, 'decision_points': [], 'exceptions': [],
                          'current_state': None, 'target_design': None,
                          'imported_field_status': 'industry_suggestion_not_customer_fact',
                          'industry_applicability': {'business_models': n.get('applicable_business_models', []), 'notes': n.get('applicability_notes')},
                          'source_refs': [ref], 'evidence': [],
                          'open_questions': ['本企业是否实际承担该过程？责任、对象、输入输出与上下游怎样调整？']})
    arch = {'schema_version': '1.0', 'company': {'name': args.company_name, 'business_model': model},
            'version': 1, 'status': 'draft', 'industry_baselines': [identity(m)], 'evidence': [],
            'source_notices': [{'dataset_id': m['dataset_id'], 'attribution_text': m.get('attribution_text', []),
                                'notice': '本地编制参考，非APQC行业标准。' if m.get('source_type') == 'analyst_compiled_reference' else 'This work is based in part on an APQC Process Classification Framework (PCF), including industry frameworks jointly developed by APQC and IBM. Preserve the original notices below. https://www.apqc.org/pcf'}],
            'processes': processes, 'relations': [],
            'tailoring_history': [{'version': 1, 'op': 'initialize', 'basis': '行业底座初稿，待按企业实际裁剪核验'}],
            'notice': '不是客户现状。父子分类不代表流转顺序；裁剪和真实关系需企业材料/访谈。'}
    return write_project(args.output, arch, root)


def init_scor_project(root, args):
    path = resources(root)['scor'][1]
    if not (path / 'records.jsonl').is_file():
        raise FileNotFoundError('SCOR受限本地资料未安装，不能初始化其概念骨架')
    m = readjson(path / 'metadata.json')
    if args.dataset and args.dataset != m['dataset_id']:
        raise ValueError('SCOR数据集不匹配；不会自动改用PCF')
    if not 1 <= args.depth <= 3:
        raise ValueError('初稿depth范围1—3；SCOR介绍册仅提供概念骨架')
    rs = [r for r in lines(path / 'records.jsonl') if r['record_type'] == 'process_concept']
    if args.root_id:
        rs = [r for r in rs if r['source_code_original'] == args.root_id or r['record_id'] == args.root_id]
    elif args.depth == 1:
        rs = [r for r in rs if r['source_code_original'] == 'OE']
    if not rs:
        raise ValueError('SCOR过程概念未找到')
    mapping = {r['source_code_original']: 'BP-{:04d}'.format(i + 1) for i, r in enumerate(rs)}
    nodes = []
    for r in rs:
        code = r['source_code_original']
        ref = identity(m, 'scor')
        ref.update(source_type='framework_introduction', complete_catalog=False, reference_key=r['record_id'],
                   original_code=code, locator={'source_pages': r['source_pages'], 'source_pdf': m['source_pdf']})
        n = tailorable_node(mapping[code], r.get('label_zh') or r['title_original'], mapping.get('OE') if code != 'OE' else None, [ref])
        n.update(kind='domain' if code == 'OE' else 'process', perspective='current',
                 scope='SCOR介绍册过程概念；中文为辅助译名，企业职责与子过程待裁剪深化。',
                 imported_field_status='industry_suggestion_not_customer_fact',
                 open_questions=['本企业供应链职责边界、子过程及上下游如何组织？'])
        nodes.append(n)
    arch = {'schema_version': '1.0', 'company': {'name': args.company_name, 'business_model': normalize_model(args.model)},
            'version': 1, 'status': 'draft', 'industry_baselines': [dict(identity(m, 'scor'), complete_catalog=False)],
            'evidence': [], 'processes': nodes, 'relations': [],
            'source_notices': [{'dataset_id': m['dataset_id'], 'licensing': m['licensing'], 'handling': '本地研究草稿；不自动发布或再分发SCOR资料。'}],
            'tailoring_history': [{'version': 1, 'op': 'initialize', 'basis': '仅SCOR介绍册七个过程概念，不是完整Level 2/3模型'}],
            'notice': '概念骨架待企业裁剪深化；OE是原册Level 0，其他主要过程为Level 1。父子不是执行顺序。'}
    return write_project(args.output, arch, root)


def write_project(path, arch, source_root=None):
    errors = validate_architecture(arch)
    if errors:
        return {'status': 'invalid', 'errors': errors, 'written': False}
    path = Path(path).resolve()
    if path.suffix.lower() != '.json':
        raise ValueError('内部机读项目底稿输出须为.json；客户文档由原交付工具生成')
    # Guard the whole skill, not just corpus. Project writes belong to an explicit project folder.
    skill = HERE.parent
    data_root = Path(source_root or library_root()).resolve()
    if path == skill or skill in path.parents or path == data_root or data_root in path.parents:
        raise ValueError('企业底稿不能写进技能或行业资料库，必须指定项目目录；底座和项目实例分离。')
    payload = json.dumps(arch, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if path.exists():
        raise FileExistsError('拒绝覆盖已有项目文件: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(payload); f.flush(); os.fsync(f.fileno())
        # Atomic, no-replace publish: a concurrent customer edit/new file also wins.
        os.link(temp, str(path))
    finally:
        os.unlink(temp)
    return {'status': 'ok', 'written': True, 'output': str(path), 'version': arch['version'],
            'active_processes': sum(p['active'] for p in arch['processes']), 'relations': len(arch['relations']),
            'confirmation': arch['status'], 'notice': '已保存项目骨架，不是自动确认客户事实或AI场景。'}


def project_data(path):
    data = readjson(path)
    arch = data.get('process_architecture', data)
    errors = validate_architecture(arch)
    if errors:
        raise ValueError('企业流程骨架非法: ' + '; '.join(errors))
    return arch


def tailorable_node(ident, name, parent=None, refs=None):
    return {'id': ident, 'name': name, 'parent_id': parent, 'kind': 'process', 'active': True,
            'confirmation': 'hypothesis', 'perspective': 'current', 'ai_assessment': 'unknown', 'order': 0,
            'roles': [], 'inputs': [], 'outputs': [], 'systems': [], 'source_refs': refs or [], 'evidence': [],
            'scope': None, 'current_state': None, 'target_design': None, 'open_questions': []}


def lookup_reference(root, op):
    rid = op.get('resource_id')
    if rid not in ('pcf', 'scor') or not text(op.get('dataset_id')) or not text(op.get('reference_key')):
        raise ValueError('attach_reference需resource_id、dataset_id、reference_key')
    path = resources(root)[rid][1]
    if rid == 'pcf':
        _, meta, directory = choose_dataset(path, dataset=op['dataset_id'])
        matches = [n for n in lines(directory / 'processes.jsonl') if op['reference_key'] in (n['node_id'], n.get('reference_id'), n['hierarchy_id'])]
        if len(matches) != 1:
            raise ValueError('行业参考节点不存在或不唯一，请先get明确定位')
        ref = reference(meta, matches[0])
        notice = {'dataset_id': meta['dataset_id'], 'attribution_text': meta.get('attribution_text', []), 'notice': '保留原归属；编制参考不是APQC官方行业标准。' if meta.get('source_type') == 'analyst_compiled_reference' else 'This work is based in part on an APQC PCF, including industry frameworks jointly developed by APQC and IBM. https://www.apqc.org/pcf'}
    else:
        meta = readjson(path / 'metadata.json')
        if meta['dataset_id'] != op['dataset_id']:
            raise ValueError('SCOR数据集不匹配')
        matches = [r for r in lines(path / 'records.jsonl') if op['reference_key'] in (r['record_id'], r.get('source_code_original'))]
        if len(matches) != 1:
            raise ValueError('SCOR参考不存在或同代码多条，请用明确record_id')
        r = matches[0]; ref = identity(meta, 'scor')
        ref.update(reference_key=r['record_id'], original_code=r.get('source_code_original'), complete_catalog=False,
                   locator={'source_pages': r['source_pages'], 'source_pdf': meta['source_pdf']})
        notice = {'dataset_id': meta['dataset_id'], 'licensing': meta['licensing'], 'handling': '本地参考，不自动发布或再分发'}
    purpose = op.get('purpose', 'architecture')
    if purpose not in ('architecture', 'task_scope', 'metric_hint'):
        raise ValueError('参考purpose非法')
    ref.update(purpose=purpose, attachment_basis=op['reason'])
    return ref, identity(meta, rid), notice


def apply_operations(original, operations, root=None):
    if not isinstance(operations, list) or not operations:
        raise ValueError('operations须为非空数组')
    arch = copy.deepcopy(original)
    arch['version'] += 1
    # Any modification invalidates the previous whole-architecture approval, not historical evidence.
    arch['status'] = 'draft'
    by_id = {p['id']: p for p in arch['processes']}

    def get(ident):
        if not isinstance(ident, str) or ident not in by_id or not by_id[ident]['active']:
            raise ValueError('企业流程不存在或已退出: ' + str(ident))
        return by_id[ident]

    def add(p):
        if not text(p.get('id')) or p['id'] in by_id:
            raise ValueError('新增ID缺失或已存在，退出节点ID也不能复用')
        by_id[p['id']] = p; arch['processes'].append(p)

    safe_details = {'name', 'scope', 'roles', 'inputs', 'outputs', 'systems', 'business_object', 'trigger',
                    'decision_points', 'exceptions', 'current_state', 'target_design', 'open_questions',
                    'ai_assessment', 'order', 'kind', 'perspective'}
    for op in operations:
        if not isinstance(op, dict) or not text(op.get('reason')):
            raise ValueError('每项裁剪操作须为对象并有reason依据')
        kind = op.get('op')
        evidence = op.get('evidence', [])
        if not isinstance(evidence, list):
            raise ValueError('裁剪evidence须为数组')
        if kind in ('keep', 'rename', 'drop', 'reparent', 'update', 'split'):
            p = get(op.get('id'))
            # A changed node is no longer silently customer-confirmed.
            if kind != 'keep':
                p['confirmation'] = 'hypothesis'
            p['evidence'].extend(copy.deepcopy(evidence))
        if kind == 'keep':
            p['tailoring_decision'] = 'keep'
        elif kind == 'rename':
            if not text(op.get('name')):
                raise ValueError('rename缺name')
            p['name'] = op['name']
        elif kind == 'drop':
            descendants = {p['id']}
            while True:
                extra = {n['id'] for n in arch['processes'] if n['active'] and n.get('parent_id') in descendants}
                if extra <= descendants:
                    break
                descendants |= extra
            if len(descendants) > 1 and op.get('cascade') is not True:
                raise ValueError('排除有子项的流程需显式cascade:true，或先逐项调整')
            for ident in descendants:
                by_id[ident].update(active=False, confirmation='excluded', tailoring_decision='drop', disposition_reason=op['reason'])
        elif kind == 'reparent':
            parent = op.get('parent_id')
            if parent is not None:
                get(parent)
            p['parent_id'] = parent
        elif kind == 'update':
            changes = op.get('changes')
            if not isinstance(changes, dict) or set(changes) - safe_details:
                raise ValueError('update只允许业务字段；ID、来源、确认和父级使用专用操作')
            p.update(copy.deepcopy(changes))
        elif kind == 'add':
            node = op.get('node')
            if not isinstance(node, dict):
                raise ValueError('add需node对象')
            if set(node) - safe_details - {'id', 'parent_id'}:
                raise ValueError('add不得伪造来源或确认状态')
            n = tailorable_node(node.get('id'), node.get('name'), node.get('parent_id'))
            n.update(copy.deepcopy(node)); n['evidence'] = copy.deepcopy(evidence)
            n['addition_basis'] = op['reason']; add(n)
        elif kind == 'merge':
            ids = op.get('ids', [])
            if not isinstance(ids, list) or len(ids) < 2 or any(not text(i) for i in ids) or len(set(ids)) != len(ids):
                raise ValueError('merge需至少两个不同企业流程ID')
            old = [get(i) for i in ids]
            parents = {p.get('parent_id') for p in old}
            if 'parent_id' not in op and len(parents) != 1:
                raise ValueError('跨父级合并需显式指定parent_id')
            parent = op.get('parent_id', old[0].get('parent_id'))
            if parent in ids:
                raise ValueError('合并父级不能是被合并节点')
            refs = []; seen = set()
            for p in old:
                for r in p['source_refs']:
                    key = encode(r)
                    if key not in seen:
                        refs.append(copy.deepcopy(r)); seen.add(key)
            n = tailorable_node(op.get('new_id'), op.get('name'), parent, refs)
            n['perspective'] = op.get('perspective', old[0].get('perspective', 'current'))
            n['evidence'] = copy.deepcopy(evidence)
            n['derived_from'] = ids; add(n)
            for p in old:
                p.update(active=False, confirmation='excluded', merged_into=n['id'])
            for p in arch['processes']:
                if p['active'] and p.get('parent_id') in ids:
                    p['parent_id'] = n['id']; p['confirmation'] = 'hypothesis'
        elif kind == 'split':
            items = op.get('items', [])
            if not isinstance(items, list) or len(items) < 2 or any(not isinstance(n, dict) for n in items):
                raise ValueError('split需至少两个items对象')
            child_ids = {n['id'] for n in arch['processes'] if n['active'] and n.get('parent_id') == p['id']}
            child_map = op.get('children_map', {})
            if not isinstance(child_map, dict) or set(child_map) != child_ids:
                raise ValueError('拆分有子项的流程须用children_map逐项指明新归属')
            new_ids = []
            for item in items:
                if set(item) - safe_details - {'id'}:
                    raise ValueError('split items仅支持新ID与业务字段')
                n = tailorable_node(item.get('id'), item.get('name'), p.get('parent_id'), copy.deepcopy(p['source_refs']))
                n['perspective'] = p.get('perspective', 'current')
                n.update(copy.deepcopy(item)); n['derived_from'] = [p['id']]
                n['evidence'] = copy.deepcopy(evidence); add(n); new_ids.append(n['id'])
            for child, parent in child_map.items():
                if parent not in new_ids:
                    raise ValueError('children_map指向非本次拆分节点')
                by_id[child]['parent_id'] = parent; by_id[child]['confirmation'] = 'hypothesis'
            p.update(active=False, confirmation='excluded', split_into=new_ids)
        elif kind == 'relate':
            r = copy.deepcopy(op.get('relation'))
            if not isinstance(r, dict) or set(r) - {'id', 'type', 'from', 'to', 'condition', 'perspective'}:
                raise ValueError('relate需relation，字段为id/type/from/to/condition/perspective')
            r.update(basis=op['reason'], confirmation='hypothesis', evidence=copy.deepcopy(evidence))
            arch['relations'].append(r)
        elif kind == 'remove_relation':
            matches = [r for r in arch['relations'] if r['id'] == op.get('id')]
            if not matches:
                raise ValueError('关系ID不存在')
            arch['relations'] = [r for r in arch['relations'] if r['id'] != op['id']]
        elif kind == 'attach_reference':
            p = get(op.get('id'))
            ref, meta, notice = lookup_reference(root or library_root(), op)
            if not any(r.get('dataset_id') == ref['dataset_id'] and r.get('reference_key') == ref['reference_key'] and r.get('purpose') == ref['purpose'] for r in p['source_refs']):
                p['source_refs'].append(ref)
            if not any(m.get('dataset_id') == meta['dataset_id'] for m in arch.setdefault('industry_baselines', [])):
                arch['industry_baselines'].append(dict(meta, role='supplemental'))
            if not any(n.get('dataset_id') == meta['dataset_id'] for n in arch.setdefault('source_notices', [])):
                arch['source_notices'].append(notice)
        elif kind == 'update_company':
            changes = op.get('changes')
            if not isinstance(changes, dict) or set(changes) - {'name', 'business_model', 'business_models'}:
                raise ValueError('update_company仅更新企业名称或经营模式；不能靠换名复用其他客户事实')
            arch['company'].update(copy.deepcopy(changes))
            for p in arch['processes']:
                if p['active']:
                    p['confirmation'] = 'hypothesis'
        elif kind == 'confirm_node':
            p = get(op.get('id'))
            if not any(isinstance(e, dict) and e.get('kind') == 'customer_confirmation' and text(e.get('locator')) for e in evidence):
                raise ValueError('confirm_node需客户确认定位，框架/模拟证据不能替代')
            p['evidence'].extend(copy.deepcopy(evidence)); p['confirmation'] = 'confirmed'
        elif kind == 'confirm_architecture':
            if not any(isinstance(e, dict) and e.get('kind') == 'customer_confirmation' and text(e.get('locator')) for e in evidence):
                raise ValueError('confirm_architecture需客户确认定位')
            arch['evidence'].extend(copy.deepcopy(evidence)); arch['status'] = 'customer_confirmed'
        else:
            raise ValueError('未知裁剪操作: ' + str(kind))
        arch['tailoring_history'].append(dict(copy.deepcopy(op), version=arch['version']))
    if arch['status'] == 'customer_confirmed' and operations[-1].get('op') != 'confirm_architecture':
        raise ValueError('整体确认必须是本次裁剪最后一项，不能确认后再静默修改')
    errors = validate_architecture(arch)
    if errors:
        raise ValueError('裁剪后校验未通过，未写文件: ' + '; '.join(errors))
    return arch


def project_query(args):
    arch = project_data(args.project)
    ps = [p for p in arch['processes'] if p['active']]
    if args.command == 'project-get':
        ps = [p for p in ps if p['id'] == args.id]
    elif args.root_id:
        wanted = {args.root_id}
        while True:
            new = {p['id'] for p in ps if p.get('parent_id') in wanted}
            if new <= wanted:
                break
            wanted |= new
        ps = [p for p in ps if p['id'] in wanted]
    if args.command == 'project-outline' and not args.full:
        ps = [{k: p.get(k) for k in ('id', 'parent_id', 'kind', 'name', 'perspective', 'confirmation', 'ai_assessment', 'order')} for p in ps]
    selected_ids = {p['id'] for p in ps[args.offset:args.offset + args.limit]}
    rels = [r for r in arch['relations'] if r['from'] in selected_ids or r['to'] in selected_ids] if args.full or args.command == 'project-get' else []
    return page_result(ps, args, company=arch['company'], architecture_version=arch['version'],
                       architecture_status=arch['status'], relations=rels, relation_total=len(rels))


def coverage(args):
    arch = project_data(args.project)
    scenarios = readjson(args.scenarios)
    combined = dict(scenarios, process_architecture=arch)
    errors = validate_process_projection(combined)
    refs = {}
    for u in scenarios.get('use_cases', []):
        if isinstance(u, dict) and u.get('confirmation') != 'excluded':
            for ref in u.get('business_process_refs', []) if isinstance(u.get('business_process_refs'), list) else []:
                if isinstance(ref, str):
                    refs.setdefault(ref, []).append(u.get('id'))
    nodes = [p for p in arch['processes'] if p['active']]
    by_id = {p['id']: p for p in nodes}
    ancestor_mapped = set()
    for ref in refs:
        parent = by_id.get(ref, {}).get('parent_id'); seen = set()
        while parent in by_id and parent not in seen:
            seen.add(parent); ancestor_mapped.add(parent); parent = by_id[parent].get('parent_id')
    rows = []
    for p in nodes:
        if p['id'] in refs:
            state = 'mapped_to_use_cases'
        elif p['id'] in ancestor_mapped:
            state = 'contains_mapped_tasks_not_full_coverage'
        elif p['ai_assessment'] in ('no_ai_needed', 'out_of_scope', 'existing_capability'):
            state = p['ai_assessment']
        else:
            state = 'needs_assessment_not_missing_AI'
        rows.append({'process_id': p['id'], 'name': p['name'], 'assessment': state,
                     'use_case_ids': refs.get(p['id'], []), 'confirmation': p['confirmation']})
    out = page_result(rows, args, valid=not errors, errors=errors,
                      notice='未挂用例不是强制补AI；归属有效不证明语义合理、客户现状或AI收益。')
    if errors:
        out['status'] = 'invalid'
    return out


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, help='默认技能内置资源；环境变量ENTERPRISE_AI_FRAMEWORK_HOME可用于可移植联调')
    sub = p.add_subparsers(dest='command', required=True)
    for name in ('catalog', 'doctor', 'outline', 'search', 'get', 'children', 'subtree', 'metrics', 'compare', 'page',
                 'init-project', 'tailor', 'project-outline', 'project-get', 'coverage', 'validate'):
        s = sub.add_parser(name)
        s.add_argument('--framework', choices=('pcf', 'scor'), default='pcf')
        s.add_argument('--industry'); s.add_argument('--dataset'); s.add_argument('--version')
        s.add_argument('--year', type=int); s.add_argument('--id'); s.add_argument('--pcf-id')
        s.add_argument('--q'); s.add_argument('--code'); s.add_argument('--type', dest='kind'); s.add_argument('--page', type=int)
        s.add_argument('--depth', type=int, default=2); s.add_argument('--root-id')
        s.add_argument('--limit', type=int, default=20); s.add_argument('--offset', type=int, default=0)
        s.add_argument('--max-chars', type=int, default=12000); s.add_argument('--full', action='store_true')
        s.add_argument('--all-industries', action='store_true'); s.add_argument('--memory', action='store_true')
        s.add_argument('--verify', action='store_true'); s.add_argument('--company-name'); s.add_argument('--model')
        s.add_argument('--project', type=Path); s.add_argument('--operations', type=Path)
        s.add_argument('--output', type=Path); s.add_argument('--scenarios', type=Path)
    return p


def run(args):
    if not 1 <= args.limit <= 200 or args.offset < 0 or not 2000 <= args.max_chars <= 200000 or args.depth < 0:
        raise ValueError('limit须1—200，offset/depth须非负，max-chars须2000—200000')
    if args.command in ('project-outline', 'project-get', 'tailor', 'coverage', 'validate') and not args.project:
        raise ValueError('需显式--project；不会自行寻找并改写客户底稿')
    if args.command in ('init-project', 'tailor') and not args.output:
        raise ValueError('写入操作需显式--output，且不覆盖已有文件')
    if args.command == 'validate':
        data = readjson(args.project)
        errors = validate_process_projection(data) if 'process_architecture' in data else validate_architecture(data)
        return {'status': 'ok' if not errors else 'invalid', 'valid': not errors, 'errors': errors,
                'notice': '结构有效不代表内容已获客户确认。'}
    if args.command in ('project-outline', 'project-get'):
        if args.command == 'project-get' and not args.id:
            raise ValueError('project-get需--id企业流程ID')
        return project_query(args)
    if args.command == 'tailor':
        if not args.operations:
            raise ValueError('tailor需--operations JSON文件')
        return write_project(args.output, apply_operations(project_data(args.project), readjson(args.operations), library_root(args.library)), library_root(args.library))
    if args.command == 'coverage':
        if not args.scenarios:
            raise ValueError('coverage需--scenarios场景投影')
        return coverage(args)
    root = library_root(args.library)
    if args.command == 'doctor':
        return doctor(root, args.verify)
    if args.command == 'catalog':
        return catalog(root, args)
    if args.command == 'init-project':
        if not text(args.company_name):
            raise ValueError('init-project需--company-name，不填历史客户')
        return init_project(root, args)
    return query_framework(root, args)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        out = run(args)
        # Envelope included in the same output budget. No half-record truncation.
        if 'candidates' in out:
            total_candidates = len(out['candidates'])
            while out['candidates'] and len(encode(out)) > args.max_chars - 150:
                out['candidates'].pop()
            if len(out['candidates']) < total_candidates:
                out.update(candidate_total=total_candidates, candidates_truncated=True, hint='候选受预算限制；用catalog分页或缩小选择条件。')
        while out.get('relations') and len(encode(out)) > args.max_chars - 250:
            out['relations'].pop()
            out['relations_truncated'] = True
            out['relation_hint'] = '关系摘要受预算限制；用project-get限定节点或提高预算。'
        original = len(out.get('results', []))
        while out.get('results') and len(encode(out)) > args.max_chars:
            out['results'].pop(); out['returned'] = len(out['results'])
            out['next_offset'] = args.offset + out['returned'] if args.offset + out['returned'] < out.get('total', 0) else None
        if 'results' in out:
            out['truncated'] = out.get('next_offset') is not None
            if original > len(out['results']):
                out['output_budget_applied'] = True
                if not out['results']:
                    out['hint'] = '单条记录超出预算；提高--max-chars重试，未静默截断原文。'
        print(encode(out))
        return 0 if out.get('status') not in ('error', 'invalid', 'incomplete', 'resource_missing') else 2
    except (ValueError, OSError, KeyError, TypeError, AttributeError, sqlite3.Error) as e:
        print(encode({'status': 'error', 'message': str(e), 'written': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
