#!/usr/bin/env python3
"""SCOR V14.0 introduction-only local query. Python standard library; never reopens PDF."""
import argparse,json,sys,time
from pathlib import Path

def encode(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'))
def loadlines(p):
 with p.open(encoding='utf-8') as f:return [json.loads(x) for x in f if x.strip()]

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('command',choices=['list','search','get','page'])
 p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
 p.add_argument('--q',help='中文/英文关键词')
 p.add_argument('--type',dest='kind',help='记录类型，如process_concept、metric_reference')
 p.add_argument('--code',help='精确原始代码，如OE、RL.1.1、EV1.4')
 p.add_argument('--id',help='本地record_id，不是ASCM官方编号')
 p.add_argument('--page',type=int,help='物理页码，1—18；不是印刷罗马页码')
 p.add_argument('--limit',type=int,default=20)
 p.add_argument('--offset',type=int,default=0)
 p.add_argument('--max-chars',type=int,default=12000)
 p.add_argument('--full',action='store_true')
 a=p.parse_args();start=time.perf_counter()
 try:
  if not 1<=a.limit<=100:raise ValueError('limit范围1—100')
  if a.offset<0:raise ValueError('offset不能为负')
  if not 1500<=a.max_chars<=100000:raise ValueError('max-chars范围1500—100000')
  if a.page is not None and not 1<=a.page<=18:raise ValueError('page为物理页码，范围1—18')
  root=a.root.resolve();meta=json.loads((root/'metadata.json').read_text(encoding='utf-8'))
  rows=loadlines(root/('pages.jsonl' if a.command=='page' else 'records.jsonl'))
  if a.command=='page':
   if not a.page:raise ValueError('page操作需提供--page')
   rows=[r for r in rows if r['physical_page']==a.page]
  else:
   if a.kind:rows=[r for r in rows if r['record_type']==a.kind]
   if a.code:rows=[r for r in rows if (r.get('source_code_original') or '').casefold()==a.code.casefold()]
   if a.id:rows=[r for r in rows if r['record_id']==a.id]
   if a.page:rows=[r for r in rows if a.page in r['source_pages']]
   if a.q:
    aliases={'采购':['采购','source','procure'],'履约':['履约','fulfill'],'计划':['计划','plan'],'退货':['退货','return'],'绩效':['绩效','performance'],'碳排放':['碳排放','GHG','温室气体'],'范围':['范围','scope'],'统筹':['统筹','orchestrate']}
    terms=aliases.get(a.q,[a.q])
    rows=[r for r in rows if any(t.casefold() in encode(r).casefold() for t in terms)]
   if a.command=='search' and not any([a.q,a.kind,a.code,a.id,a.page]):raise ValueError('search至少提供一个查询条件')
   if a.command=='get' and not (a.code or a.id):raise ValueError('get需提供--code或--id')
  total=len(rows)
  page=rows[a.offset:a.offset+a.limit]
  results=[]
  for r in page:
   if a.command=='page' or a.command=='get' or a.full:result=r.copy()
   else:
    result={k:r.get(k) for k in ['record_id','record_type','title_original','label_zh','source_code_original','scor_level','source_pages']}
    if r.get('analysis_note_zh'):result['note_excerpt']=r['analysis_note_zh'][:180]
   result['source_pdf']=meta['source_pdf'];results.append(result)
  out={'status':'ok' if total else 'not_found','dataset_id':meta['dataset_id'],'version':meta['version'],'file_year':meta['file_year'],
   'content_scope':'framework_introduction','complete_catalog':False,'total':total,'offset':a.offset,'returned':len(results),
   'next_offset':a.offset+len(results) if a.offset+len(results)<total else None,'results':results,
   'notice':'仅用户提供的18页介绍册。记录是参考概念或示例，不是完整SCOR过程库；中文为辅助译名。'}
  before=len(results)
  while results and len(encode(out))>a.max_chars-120:
   results.pop();out['returned']=len(results);out['next_offset']=a.offset+len(results) if a.offset+len(results)<total else None
  if len(results)<before:out['output_budget_applied']=True
  if before and not results:out['hint']='单条原文超出预算；提高--max-chars后重试，未静默截断原文。'
  out['truncated']=out['next_offset'] is not None
  out['elapsed_ms']=round((time.perf_counter()-start)*1000,3)
  print(encode(out));return 0
 except (ValueError,OSError) as e:print(encode({'status':'error','message':str(e)}));return 2
if __name__=='__main__':raise SystemExit(main())
