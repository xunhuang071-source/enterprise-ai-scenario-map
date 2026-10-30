"""Stdlib in-memory fallback; derived from the original approved APQC library builder.
No Excel dependencies, corpus writes, or persistent cache creation.
"""
import datetime,json,sqlite3
from pathlib import Path
SCHEMA_VERSION="1.1.0"

def memory_index(root):
 """Build a read-only-use in-memory query index from the bundled canonical files."""
 root=Path(root)
 ALIASES=json.loads((root/"检索别名.json").read_text(encoding="utf-8"))["aliases"]
 cat=json.loads((root/'catalog.json').read_text(encoding='utf-8'))
 c=sqlite3.connect(':memory:')
 c.executescript('''
 CREATE TABLE datasets(dataset_id TEXT PRIMARY KEY, industry_zh TEXT, industry_en TEXT, version TEXT, year INTEGER, status TEXT, aliases TEXT, meta TEXT);
 CREATE TABLE nodes(node_id TEXT PRIMARY KEY,dataset_id TEXT,pcf_id TEXT,hierarchy_id TEXT,level INTEGER,parent_id TEXT,sort_order INTEGER,name TEXT,name_en TEXT,name_zh TEXT,description TEXT,record TEXT,search_context TEXT);
 CREATE INDEX node_dataset_hierarchy ON nodes(dataset_id,hierarchy_id);
 CREATE INDEX node_pcf ON nodes(pcf_id,dataset_id);
 CREATE INDEX node_parent ON nodes(parent_id);
 CREATE TABLE metrics(record_id TEXT PRIMARY KEY,dataset_id TEXT,node_id TEXT,pcf_id TEXT,metric_id TEXT,record TEXT);
 CREATE INDEX metric_node ON metrics(node_id);
 CREATE INDEX metric_pcf ON metrics(dataset_id,pcf_id);
 CREATE TABLE supplements(dataset_id TEXT,node_id TEXT,kind TEXT,record TEXT);
 CREATE INDEX supplement_node ON supplements(node_id);
 CREATE TABLE search_aliases(alias TEXT PRIMARY KEY,terms TEXT);
 CREATE TABLE build_info(key TEXT PRIMARY KEY,value TEXT);
 ''')
 try:
  c.execute("CREATE VIRTUAL TABLE node_fts USING fts5(node_id UNINDEXED,name,name_en,name_zh,description,context,tokenize='unicode61')")
  fts=True
 except sqlite3.OperationalError:fts=False
 for item in cat['datasets']:
  meta=json.loads((root/item['directory']/'metadata.json').read_text(encoding='utf-8'))
  c.execute('INSERT INTO datasets VALUES(?,?,?,?,?,?,?,?)',(meta['dataset_id'],meta['industry_zh'],meta['industry_en'],meta['version'],meta['file_year'],meta['status'],json.dumps(meta['aliases'],ensure_ascii=False),json.dumps(meta,ensure_ascii=False)))
  if meta['status']!='ready':continue
  for i,line in enumerate((root/item['directory']/'processes.jsonl').read_text(encoding='utf-8').splitlines()):
   n=json.loads(line)
   context=''
   if meta.get('source_type')=='analyst_compiled_reference':
    if n['pcf_id'] is not None or n.get('is_official') is not False:raise ValueError('本地参考节点不得伪造官方PCF身份：'+n['node_id'])
    context=' '.join([n.get('reference_id',''),n.get('applicability_notes','')]+[str(v) for k in ['roles','inputs','outputs','related_systems','applicable_business_models'] for v in n.get(k,[])]+[meta.get('business_models',{}).get(v,v) for v in n.get('applicable_business_models',[])])
   c.execute('INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(n['node_id'],n['dataset_id'],n['pcf_id'],n['hierarchy_id'],n['level'],n['parent_id'],i,n['name_original'],n['name_en'],n['name_zh'],n['description'],line,context))
   if fts:c.execute('INSERT INTO node_fts VALUES(?,?,?,?,?,?)',(n['node_id'],n['name_original'],n['name_en'],n['name_zh'],n['description'],context))
  # metrics.jsonl可拆分为metrics.jsonl+metrics.part2.jsonl（排序后顺序读取），规避单文件体积限制
  for p in sorted((root/item['directory']).glob('metrics*.jsonl')):
   for line in p.read_text(encoding='utf-8').splitlines():
    m=json.loads(line);c.execute('INSERT INTO metrics VALUES(?,?,?,?,?,?)',(m['metric_record_id'],m['dataset_id'],m['node_id'],m['pcf_id'],m['metric_id'],line))
  sp=root/item['directory']/'supplement.jsonl'
  if sp.exists():
   for line in sp.read_text(encoding='utf-8').splitlines():
    s=json.loads(line);node=s.get('node_id') or s.get('record',{}).get('node_id')
    c.execute('INSERT INTO supplements VALUES(?,?,?,?)',(meta['dataset_id'],node,s['kind'],line))
 for a,terms in ALIASES.items():c.execute('INSERT INTO search_aliases VALUES(?,?)',(a,json.dumps(terms,ensure_ascii=False)))
 for k,v in {'schema_version':SCHEMA_VERSION,'fts5':str(fts),'data_origin':'JSONL','built_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}.items():c.execute('INSERT INTO build_info VALUES(?,?)',(k,v))
 c.commit();check=c.execute('pragma integrity_check').fetchone()[0]
 if check!='ok':raise RuntimeError(check)
 c.row_factory=sqlite3.Row
 return c
