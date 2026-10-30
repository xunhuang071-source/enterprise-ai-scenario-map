"""Optional enterprise process architecture contract; Python 3.8+, stdlib only.
Structural checks are not proof of customer facts or semantic correctness.
"""

RELATION_TYPES = {'sequence', 'decision', 'handoff', 'feedback', 'data_dependency'}
CONFIRMATIONS = {'hypothesis', 'supported', 'confirmed', 'excluded'}
AI_ASSESSMENTS = {'unknown', 'candidate', 'no_ai_needed', 'out_of_scope', 'existing_capability'}


def text(value):
    return isinstance(value, str) and bool(value.strip())


def framework_evidence_errors(evidence, prefix=''):
    errors = []
    if not isinstance(evidence, list):
        return [prefix + ' evidence须为数组']
    for e in evidence:
        if not isinstance(e, dict) or e.get('kind') != 'framework_reference':
            continue
        for k in ('dataset_id', 'version', 'source_type', 'locator', 'purpose'):
            if not text(e.get(k)):
                errors.append(prefix + ' framework_reference缺' + k)
        if e.get('purpose') not in ('architecture', 'task_scope', 'metric_hint'):
            errors.append(prefix + ' 框架引用purpose非法')
        if type(e.get('is_official')) is not bool:
            errors.append(prefix + ' 框架引用须标is_official')
        if e.get('source_type') == 'analyst_compiled_reference' and e.get('is_official') is not False:
            errors.append(prefix + ' 编制参考不能标为官方')
        if e.get('proves_customer_fact') is not False:
            errors.append(prefix + ' 框架引用不能证明客户事实，proves_customer_fact须为false')
    return errors


def validate_architecture(arch):
    errors = []
    if not isinstance(arch, dict):
        return ['process_architecture须为对象']
    if arch.get('schema_version') != '1.0':
        errors.append('流程架构schema_version须为1.0')
    if arch.get('status') not in ('draft', 'customer_confirmed'):
        errors.append('流程架构status须为draft或customer_confirmed')
    if not isinstance(arch.get('version'), int) or isinstance(arch.get('version'), bool) or arch.get('version', 0) < 1:
        errors.append('流程架构version须为正整数')
    if not isinstance(arch.get('company'), dict) or not text(arch.get('company', {}).get('name')):
        errors.append('流程架构缺企业名称')
    nodes = arch.get('processes')
    if not isinstance(nodes, list) or not nodes:
        return errors + ['processes须为非空数组']
    by_id = {}
    for p in nodes:
        if not isinstance(p, dict) or not text(p.get('id')):
            errors.append('流程节点须有字符串id'); continue
        ident = p['id']
        if ident in by_id:
            errors.append('流程ID重复: ' + ident)
        by_id[ident] = p
        if not text(p.get('name')):
            errors.append(ident + ' 缺流程名称')
        if p.get('kind') not in ('domain', 'process', 'task'):
            errors.append(ident + ' kind非法')
        if p.get('perspective') not in ('current', 'target', 'both'):
            errors.append(ident + ' perspective须区分current/target/both')
        if p.get('confirmation') not in CONFIRMATIONS:
            errors.append(ident + ' 确认状态非法')
        if type(p.get('active')) is not bool:
            errors.append(ident + ' active须为布尔值')
        if p.get('confirmation') == 'excluded' and p.get('active') is True:
            errors.append(ident + ' 排除节点不能active')
        if p.get('ai_assessment') not in AI_ASSESSMENTS:
            errors.append(ident + ' ai_assessment非法')
        for k in ('roles', 'inputs', 'outputs', 'systems', 'source_refs', 'evidence'):
            if not isinstance(p.get(k), list):
                errors.append(ident + ' ' + k + '须为数组')
        errors.extend(framework_evidence_errors(p.get('evidence'), ident))
        if p.get('confirmation') == 'confirmed':
            es = p.get('evidence') or []
            if not any(isinstance(e, dict) and e.get('kind') == 'customer_confirmation' and text(e.get('locator')) for e in es):
                errors.append(ident + ' confirmed须有客户确认定位；行业引用不代替确认')
        for r in p.get('source_refs', []) if isinstance(p.get('source_refs'), list) else []:
            if not isinstance(r, dict) or any(not text(r.get(k)) for k in ('resource_id', 'dataset_id', 'reference_key', 'version', 'source_type')):
                errors.append(ident + ' source_refs不完整'); continue
            if type(r.get('is_official')) is not bool:
                errors.append(ident + ' 来源性质缺失')
            if r.get('source_type') == 'analyst_compiled_reference' and (r.get('is_official') is not False or r.get('pcf_id') is not None):
                errors.append(ident + ' 电商参考不能伪造官方身份/PCF ID')
    for ident, p in by_id.items():
        parent = p.get('parent_id')
        if parent is not None and not text(parent):
            errors.append(ident + ' parent_id须为字符串或null'); continue
        if parent is not None and parent not in by_id:
            errors.append(ident + ' 父流程不存在')
        if p.get('active') is not True:
            continue
        if parent in by_id and by_id[parent].get('active') is not True:
            errors.append(ident + ' 活跃节点不能挂在已排除/合并节点下')
        seen = {ident}
        while parent in by_id:
            if parent in seen:
                errors.append(ident + ' 分类父子关系存在环'); break
            seen.add(parent); parent = by_id[parent].get('parent_id')
    rels = arch.get('relations')
    if not isinstance(rels, list):
        errors.append('relations须为数组'); rels = []
    seen = set()
    for r in rels:
        if not isinstance(r, dict) or not text(r.get('id')):
            errors.append('流转关系须有id'); continue
        if r['id'] in seen:
            errors.append('流转关系ID重复: ' + r['id'])
        seen.add(r['id'])
        if r.get('type') not in RELATION_TYPES:
            errors.append(r['id'] + ' 关系类型非法')
        if r.get('perspective') not in ('current', 'target'):
            errors.append(r['id'] + ' 流转关系须区分现状或目标')
        for k in ('from', 'to'):
            endpoint = r.get(k)
            if not text(endpoint) or endpoint not in by_id or by_id[endpoint].get('active') is not True:
                errors.append(r['id'] + ' 关系端点不存在或已退出: ' + str(endpoint))
        if not text(r.get('basis')):
            errors.append(r['id'] + ' 流转关系须有依据，不从分类编号推定顺序')
        if r.get('confirmation') not in CONFIRMATIONS - {'excluded'}:
            errors.append(r['id'] + ' 关系确认状态非法')
        if r.get('confirmation') == 'confirmed' and not any(isinstance(e, dict) and e.get('kind') == 'customer_confirmation' and text(e.get('locator')) for e in r.get('evidence', [])):
            errors.append(r['id'] + ' 关系confirmed缺客户确认定位')
    # Business flows may contain feedback/iteration. Do not apply a DAG constraint here.
    if arch.get('status') == 'customer_confirmed':
        if not any(isinstance(e, dict) and e.get('kind') == 'customer_confirmation' and text(e.get('locator')) for e in arch.get('evidence', [])):
            errors.append('企业骨架customer_confirmed缺客户确认定位')
    return errors


def validate_process_projection(data):
    """Old projection is accepted unchanged; new embedded architecture opts in."""
    errors = []
    if not isinstance(data.get('use_cases'), list):
        return ['场景投影use_cases须为数组']
    if any(not isinstance(u, dict) for u in data['use_cases']):
        errors.append('场景投影用例须为对象')
    for u in data.get('use_cases', []):
        if isinstance(u, dict) and isinstance(u.get('evidence'), list):
            errors.extend(framework_evidence_errors(u['evidence'], str(u.get('id', '?'))))
    if 'process_architecture' not in data:
        # A new process link must not silently look validated without its architecture.
        if any(isinstance(u, dict) and u.get('business_process_refs') for u in data.get('use_cases', [])):
            errors.append('已提供business_process_refs但未嵌入process_architecture，无法核对企业流程ID')
        return errors
    arch = data['process_architecture']
    errors.extend(validate_architecture(arch))
    active = {p['id'] for p in arch.get('processes', []) if isinstance(p, dict) and text(p.get('id')) and p.get('active') is True} if isinstance(arch, dict) else set()
    for label in ('big_scenarios', 'use_cases'):
        for item in data.get(label, []):
            if not isinstance(item, dict):
                continue
            refs = item.get('business_process_refs', [])
            if not isinstance(refs, list) or any(not text(r) for r in refs):
                errors.append(str(item.get('id')) + ' business_process_refs须为企业流程ID数组'); continue
            if label == 'use_cases' and item.get('confirmation') != 'excluded' and not refs:
                errors.append(str(item.get('id')) + ' 缺本企业流程/任务定位')
            for ref in refs:
                if ref not in active:
                    errors.append(str(item.get('id')) + ' 企业流程引用无效: ' + ref)
    return errors
