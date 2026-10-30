#!/usr/bin/env python3
"""Offline framework query CLI. APQC source data plus explicitly labelled local references; stdlib only."""
from __future__ import annotations
import argparse, json, re, sqlite3, sys, time
from pathlib import Path


def dump(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'))
def norm_hier(h):return str(h)+'.0' if h and re.fullmatch(r'\d+',str(h)) else h

class Query:
 def __init__(self,root):
  self.root=Path(root).resolve();db=self.root/'检索'/'apqc.sqlite'
  if not db.is_file():raise FileNotFoundError('索引不存在，请运行工具/build.py --reindex')
  self.c=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True);self.c.row_factory=sqlite3.Row
  self.datasets={r['dataset_id']:dict(r) for r in self.c.execute('select * from datasets')}
  for d in self.datasets.values():d['meta']=json.loads(d['meta']);d['aliases']=json.loads(d['aliases'])
  self.fts=self.c.execute("select value from build_info where key='fts5'").fetchone()[0]=='True'
  self.ancestors={}

 def ds_short(self,d):
  m=d['meta'];return {'dataset_id':d['dataset_id'],'industry':d['industry_zh'],'version':d['version'],'file_year':d['year'],
   'language':m['language'],'date_type':m['date_type'],'status':d['status'],'node_count':m.get('statistics',{}).get('node_count',0),
   'framework_family':m.get('framework_family','APQC'),'source_type':m.get('source_type','apqc_excel'),'is_official':m.get('is_official',True)}

 def resolve(self,args):
  ds=list(self.datasets.values())
  if args.dataset:ds=[d for d in ds if d['dataset_id']==args.dataset]
  if args.industry:
   term=args.industry.casefold()
   exact=[d for d in ds if any(term==a.casefold() for a in d['aliases'])]
   ds=exact or [d for d in ds if any(term in a.casefold() for a in d['aliases'])]
  if args.version:ds=[d for d in ds if d['version']==args.version.lstrip('Vv')]
  if args.year:ds=[d for d in ds if d['year']==args.year]
  return ds

 def path(self,row):
  out=[];parent=row['parent_id'];seen=set()
  while parent and parent not in seen:
   seen.add(parent)
   if parent not in self.ancestors:self.ancestors[parent]=self.c.execute('select * from nodes where node_id=?',(parent,)).fetchone()
   p=self.ancestors[parent]
   if not p:break
   out.append({'hierarchy_id':p['hierarchy_id'],'name':p['name'],'pcf_id':p['pcf_id']});parent=p['parent_id']
  return list(reversed(out))

 def snippet(self,row,full=False):
  r=dict(row);n=json.loads(r['record']);d=self.datasets[r['dataset_id']];m=d['meta']
  common={'dataset_id':r['dataset_id'],'industry':d['industry_zh'],'version':d['version'],'file_year':d['year'],
          'node_id':r['node_id'],'pcf_id':r['pcf_id'],'hierarchy_id':r['hierarchy_id'],'level':r['level'],
          'name':r['name'],'name_en':r['name_en'],'name_zh':r['name_zh'],'parent_path':self.path(row),
          'source':{'file':m['source_file'],'sheet':n['source_sheet'],'row':n['source_row'],'kind':m.get('source_type','apqc_excel')},
          'framework_family':m.get('framework_family','APQC'),'source_type':m.get('source_type','apqc_excel'),'is_official':m.get('is_official',True)}
  if m.get('source_type')=='analyst_compiled_reference':
   common.update(reference_id=n['reference_id'],description_origin=n['description_origin'],evidence_type=n['evidence_type'],
     applicable_business_models=n['applicable_business_models'],reference_notice='本地实务归纳，不是APQC或官方行业标准。')
   common['source']['source_ids']=list(dict.fromkeys(s['source_id'] for s in n['source_references']))
  if full:
   common['record']=n
   common['source_variants']=[json.loads(s['record']) for s in self.c.execute('select record from supplements where node_id=?',(r['node_id'],))]
   common['metric_record_count']=self.c.execute('select count(*) from metrics where node_id=?',(r['node_id'],)).fetchone()[0]
   common['year_basis']=m['year_basis']
  else:
   common['description_excerpt']=(r['description'][:180]+'…' if len(r['description'] or '')>180 else r['description'])
   v=self.c.execute('select count(*) from supplements where node_id=?',(r['node_id'],)).fetchone()[0]
   if v:common['source_variant_count']=v
  return common

 def output(self,args,rows,total,**extra):
  # Rows are already a single page, or a bounded list. Never split a JSON record silently.
  results=[self.snippet(r,args.full or args.command=='get') for r in rows]
  return self.page(args,results,total,**extra)

 def page(self,args,results,total,**extra):
  response={'status':'ok','total':total,'offset':args.offset,'returned':len(results),
   'next_offset':args.offset+len(results) if args.offset+len(results)<total else None,'results':results,**extra}
  original=len(results)
  while response['results'] and len(dump(response))>args.max_chars-250:
   response['results'].pop();response['returned']=len(response['results'])
   response['next_offset']=args.offset+len(response['results']) if args.offset+len(response['results'])<total else None
  if len(response['results'])<original:
   response['output_budget_applied']=True
   if not response['results']:response['hint']='单条记录超出输出预算；提高 --max-chars 后重试，或不使用 --full 查看摘要。'
  response['truncated']=response['next_offset'] is not None
  return response

 def selection(self,args,ds):
  if not ds:return {'status':'not_found','results':[], 'message':'没有匹配的行业或版本；未自动改用其他版本。当前不含生命科学Excel、跨行业通用V8.0 Excel。请用list查看可用范围。'}
  if args.command not in ['list','compare'] and len(ds)!=1 and not (args.command=='search' and args.all_industries):
   return {'status':'needs_selection','message':'请指定一个行业/数据集和版本；跨行业search需显式添加 --all-industries。','candidates':[self.ds_short(d) for d in ds]}
  if args.command not in ['list'] and any(d['status']!='ready' for d in ds):
   return {'status':'not_ready','message':'所选数据集尚未完成转换校验。','candidates':[self.ds_short(d) for d in ds]}
  return None

 def run(self,args):
  ds=self.resolve(args)
  warning=self.selection(args,ds)
  if warning:return warning
  if args.pcf_id and ds and all(d['meta'].get('source_type')=='analyst_compiled_reference' for d in ds):
   return {'status':'unsupported_identifier','results':[],'is_official':False,'message':'该数据集没有APQC PCF ID。请用--id层级编号（如10.3）查询；ECOM编号只是本地参考。'}
  if args.command=='list':
   results=[self.ds_short(d) for d in ds]
   return self.page(args,results[args.offset:args.offset+args.limit],len(results),known_missing=['生命科学Excel','跨行业通用V8.0 Excel'])
  dids=[d['dataset_id'] for d in ds];params=list(dids);where='dataset_id IN ('+','.join('?' for _ in dids)+')'
  if args.command=='outline':
   sql=f'select * from nodes where {where} and level<=? order by dataset_id,sort_order';params.append(args.depth if args.depth is not None else 2)
   return self.select_page(args,sql,params)
  if args.command=='search':
   if not(args.q or args.id or args.pcf_id):raise ValueError('search需提供 --q、--id 或 --pcf-id')
   if args.id:where+=' AND hierarchy_id=?';params.append(norm_hier(args.id))
   if args.pcf_id:where+=' AND pcf_id=?';params.append(args.pcf_id)
   terms=[]
   if args.q:
    q=args.q.strip();terms.append(q)
    for r in self.c.execute('select alias,terms from search_aliases'):
     if r['alias'] in q:terms.extend(json.loads(r['terms']))
    terms=list(dict.fromkeys(t for t in terms if t))
    predicates=[]
    if self.fts:
     fts=' OR '.join('"'+t.replace('"','""')+'"' for t in terms)
     predicates.append('node_id IN (select node_id from node_fts where node_fts MATCH ?)');params.append(fts)
    for t in terms:
     predicates.append("(name LIKE ? ESCAPE '\\' OR name_en LIKE ? ESCAPE '\\' OR name_zh LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\' OR search_context LIKE ? ESCAPE '\\')")
     escaped=t.replace('\\','\\\\').replace('%','\\%').replace('_','\\_');params.extend(['%'+escaped+'%']*5)
    where+=' AND ('+' OR '.join(predicates)+')'
   name_rank=[];rank_params=[]
   for rank,t in enumerate(terms):
    escaped=t.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
    name_rank.append("WHEN (name LIKE ? ESCAPE '\\' OR name_en LIKE ? ESCAPE '\\' OR name_zh LIKE ? ESCAPE '\\') THEN "+str(rank));rank_params.extend(['%'+escaped+'%']*3)
   ordering='CASE '+' '.join(name_rank)+' ELSE '+str(len(terms)+1)+' END,' if name_rank else ''
   sql=f'select * from nodes where {where} order by {ordering}dataset_id,sort_order'
   return self.select_page(args,sql,params+rank_params,search_terms=terms,search_mode='keyword/alias OR; names ranked first; not semantic search')
  if args.command=='compare':
   if not args.pcf_id:raise ValueError('compare需提供 --pcf-id；不按相同层级编号假定跨行业等价')
   sql=f'select * from nodes where {where} and pcf_id=? order by dataset_id,sort_order'
   return self.select_page(args,sql,params+[args.pcf_id],notice='相同PCF ID仅用于辅助并列查看，不自动证明各行业节点语义完全相同；同数据集也可能出现多次。')
  node,ambiguous=self.find_one(args,where,params)
  if ambiguous:return ambiguous
  if args.command=='get':return self.output(args,[node] if args.offset==0 else [],1)
  if args.command=='children':
   sql='select * from nodes where parent_id=? order by sort_order'
   return self.select_page(args,sql,[node['node_id']],root_node=node['node_id'])
  if args.command=='subtree':
   depth=args.depth if args.depth is not None else 2
   # Ancestor prefix requires a dot; 1.0 root maps to 1 rather than 1.0 prefix.
   h=node['hierarchy_id'];prefix=h[:-2] if node['level']==1 else h
   sql='select * from nodes where dataset_id=? and (hierarchy_id=? or hierarchy_id LIKE ?) and level<=? order by sort_order'
   return self.select_page(args,sql,[node['dataset_id'],h,prefix+'.%',node['level']+depth],root_node=node['node_id'],depth=depth)
  if args.command=='metrics':
   rows=list(self.c.execute('select record from metrics where node_id=? order by rowid',(node['node_id'],)))
   records=[]
   for r in rows[args.offset:args.offset+args.limit]:
    m=json.loads(r['record']);d=self.datasets[m['dataset_id']]
    base={'industry':d['industry_zh'],'version':d['version'],'file_year':d['year'],'dataset_id':m['dataset_id'],
     'node_id':m['node_id'],'pcf_id':m['pcf_id'],'metric_id':m['metric_id'],'metric_name':m['metric_name'],
     'metric_category':m['metric_category'],'units':m['units'],
     'source':{'file':d['meta']['source_file'],'sheet':m['source_sheet'],'row':m['source_row']}}
    if args.full:base['formula']=m['formula']
    records.append(base)
   notice='仅列本文件实际附带的指标；原表Metrics Available为Y不保证本地含指标明细。公式仅按原文保存。'
   if self.datasets[node['dataset_id']]['meta'].get('source_type')=='analyst_compiled_reference':
    notice='该电商数据集为非官方本地编制参考，未附原始指标库；不编造官方指标或公式。'
   return self.page(args,records,len(rows),notice=notice)
  raise ValueError('未知操作')

 def select_page(self,args,sql,params,**extra):
  # Query parameters for ORDER BY CASE may occur after filter parameters; wrapping retains them.
  total=self.c.execute('select count(*) from ('+sql+')',params).fetchone()[0]
  rows=list(self.c.execute(sql+' LIMIT ? OFFSET ?',params+[args.limit,args.offset]))
  return self.output(args,rows,total,**extra)

 def find_one(self,args,where,params):
  if args.id:where+=' AND hierarchy_id=?';params=params+[norm_hier(args.id)]
  elif args.pcf_id:where+=' AND pcf_id=?';params=params+[args.pcf_id]
  else:raise ValueError(f'{args.command}需提供 --id 或 --pcf-id')
  rows=list(self.c.execute('select * from nodes where '+where+' order by sort_order',params))
  if not rows:return None,{'status':'not_found','results':[],'message':'未找到该节点。'}
  if len(rows)>1:return None,{'status':'needs_disambiguation','message':'同一PCF ID对应多个节点，请用 --id 指定层级编号。','candidates':[self.snippet(r) for r in rows]}
  return rows[0],None


def parser():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent,help='Portable data root')
 subs=p.add_subparsers(dest='command',required=True)
 for name,helptext in [('list','列可用行业与版本'),('outline','查看第1—2级目录'),('search','按关键词或ID检索'),('get','节点原文、定义、来源和差异'),('children','直接子节点'),('subtree','指定深度分支，含起点'),('metrics','流程指标'),('compare','按PCF ID跨行业并列查看')]:
  sp=subs.add_parser(name,help=helptext)
  sp.add_argument('--industry',help='中文/英文行业名或别名')
  sp.add_argument('--dataset',help='精确dataset_id')
  sp.add_argument('--version',help='版本，例如8.0')
  sp.add_argument('--year',type=int,help='文件年份，不必然为发布年')
  sp.add_argument('--id',help='流程层级编号，例如4.1.1；顶层1规范化为1.0')
  sp.add_argument('--pcf-id',help='APQC概念编号')
  sp.add_argument('--q',help='业务关键词；不是自然语言语义搜索')
  sp.add_argument('--depth',type=int,help='outline为最大层级；subtree为起点以下层数')
  sp.add_argument('--limit',type=int,default=20,help='每页条数，默认20，最大200')
  sp.add_argument('--offset',type=int,default=0)
  sp.add_argument('--max-chars',type=int,default=12000,help='单次JSON输出预算，默认12000字符')
  sp.add_argument('--full',action='store_true',help='search/compare展开定义，metrics展开公式；get始终返回完整详情')
  sp.add_argument('--all-industries',action='store_true',help='显式允许search跨行业查询')
 return p


def main():
 p=parser();a=p.parse_args();t=time.perf_counter()
 try:
  if not 1<=a.limit<=200:raise ValueError('--limit范围1—200')
  if a.offset<0:raise ValueError('--offset不能为负')
  if not 2000<=a.max_chars<=200000:raise ValueError('--max-chars范围2000—200000')
  if a.depth is not None and a.depth<0:raise ValueError('--depth不能为负')
  q=Query(a.root);result=q.run(a);q.c.close()
  if 'candidates' in result and len(dump(result))>a.max_chars-250:
   result['candidate_total']=len(result['candidates'])
   result['candidates_truncated']=True
   result['hint']='候选受输出预算限制；请用list分页查看，或缩小行业和版本条件。'
   while result['candidates'] and len(dump(result))>a.max_chars-250:result['candidates'].pop()
  result['elapsed_ms']=round((time.perf_counter()-t)*1000,3)
  print(dump(result));return 0
 except (ValueError,FileNotFoundError,sqlite3.Error) as e:
  print(dump({'status':'error','message':str(e)}));return 2

if __name__=='__main__':raise SystemExit(main())
