"""삼성전자 30건과 관련 최대 20건 반복 분석용 PoC 실행기."""
import argparse
import hashlib
import json
import urllib.error
from collections import Counter
from pathlib import Path
from data.news_poc.pipeline.gms_client import request_batch, load_key
from data.news_poc.pipeline.business_analysis import (PROMPT, CAREER_PROMPT, CAREER_FIELDS, validate_analysis, normalize_analysis)

def main():
    """5건 배치로 분석한다. 통신·JSON 실패는 중단하고 업무 형식 실패 행은 별도 표시한다."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--repair-contract',action='store_true',help='상태별 빈 사업 값과 기존 보류 사유를 정규화')
    parser.add_argument('--rubric',choices=['company','career'],default='company',help='company는 과거 기업 영향, career는 취준생 유용성')
    args=parser.parse_args()
    def read(name):return json.loads((args.out/name).read_text(encoding='utf-8'))
    def save(name,value):(args.out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=read('input.json');catalog=read('business_catalog.json')
    assert len(rows)==30 and all(r['company']=='삼성전자' for r in rows)
    score_fields=CAREER_FIELDS if args.rubric=='career' else ('impact','duration','certainty')
    prompt=(CAREER_PROMPT if args.rubric=='career' else PROMPT)+'\n사업 목록:\n'+json.dumps(catalog,ensure_ascii=False)
    digest=hashlib.sha256((prompt+json.dumps(rows,ensure_ascii=False)).encode()).hexdigest()
    (args.out/'prompt.txt').write_text(prompt,encoding='utf-8')
    repeated=[r for r in rows if r['relevance']=='related'][:20]
    save('run-plan.json',dict(input_hash=digest,rubric=args.rubric,score_fields=score_fields,repeat_ids=[r['sample_id'] for r in repeated],model='gemini-2.5-flash-lite',human_gold=False))
    key=load_key(Path('data/.env'));runs=[];records=[]
    for run,inputs in enumerate([rows,repeated,repeated],1):
        results=[]
        for number,start in enumerate(range(0,len(inputs),5)):
            batch=inputs[start:start+5];name=f'run-{run}-batch-{number:02}.json';path=args.out/name
            if path.exists():
                record=read(name)
                if record.get('input_hash')!=digest or record.get('status') not in ('success','invalid_business_schema'):raise ValueError('Inspect saved batch before retry')
                if record['status']=='invalid_business_schema' and record.get('results'):
                    record['status']='success'
            else:
                record={}
                try:
                    record=request_batch('gemini-2.5-flash-lite',batch,key,prompt=prompt)
                except urllib.error.HTTPError as error:
                    record=dict(status='http_error',http_status=error.code)
                except (urllib.error.URLError,TimeoutError):record=dict(status='connection_error')
                except ValueError as error:
                    # 요청 성공 후 업무 스키마가 틀려도 raw·usage는 보존한다.
                    record=dict(record,status='invalid_business_schema',validation_error=str(error))
                record['input_hash']=digest;save(name,record)
            if record['status']=='success':
                original=record.get('raw_results',record['results'])
                record['raw_results']=original
                normalized=[];raw_errors=[]
                for output,input_row in zip(original,batch):
                    try:validate_analysis(output,input_row['relevance'],catalog['values'],score_fields=score_fields)
                    except ValueError as error:raw_errors.append(dict(sample_id=output['sample_id'],error=str(error)))
                    fixed=normalize_analysis(output,score_fields=score_fields,repair_contract=args.repair_contract)
                    try:
                        validate_analysis(fixed,input_row['relevance'],catalog['values'],score_fields=score_fields);fixed['schema_valid']=True
                    except ValueError as error:
                        fixed.update(schema_valid=False,schema_error=str(error))
                    normalized.append(fixed)
                record['results']=normalized if record['status']=='success' else original
                record['raw_schema_errors']=raw_errors;save(name,record)
            if record['status']!='success':
                print('STOP',name,record['status'],flush=True);return
            results.extend(record['results']);records.append(record)
            print('run',run,len(results),'/',len(inputs),flush=True)
        save(f'predictions-{run}.json',results);runs.append({r['sample_id']:r for r in results})
    first=list(runs[0].values());eligible=[r for r in first if r['predicted']=='related']
    triples=[[run[r['sample_id']] for run in runs] for r in repeated]
    business_stable=sum(all(r['schema_valid'] for r in triple) and len({json.dumps([r['business_status'],r['related_business']],ensure_ascii=False) for r in triple})==1 for triple in triples)
    scored=[t for t in triples if all(r['schema_valid'] and r['importance_score'] is not None for r in t)]
    summary=dict(n=30,related_gate_count=len(eligible),business_status_counts=dict(Counter(r['business_status'] for r in first)),
                 importance_scored=sum(r['schema_valid'] and r['importance_score'] is not None for r in eligible),
                 importance_coverage=sum(r['schema_valid'] and r['importance_score'] is not None for r in eligible)/len(eligible),
                 repeat_count=len(repeated),business_status_and_value_stable=business_stable,
                 repeat_all_scores_available=len(scored),repeat_score_range_within2=sum(max(r['importance_score'] for r in t)-min(r['importance_score'] for r in t)<=2 for t in scored),
                 estimated_credits=sum(r['estimated_credits'] for r in records),request_seconds=sum(r['seconds'] for r in records),
                 successful_batches=len(records),business_accuracy=None,importance_mae=None,human_review_count=0)
    summary['raw_schema_error_rows']=sum(len(r.get('raw_schema_errors',[])) for r in records)
    summary['normalized_rows']=sum(bool(x.get('normalization_repairs')) for r in records for x in r['results'])
    summary['first_run_valid_rows']=sum(r['schema_valid'] for r in first)
    summary['all_runs_invalid_rows']=sum(not x['schema_valid'] for r in records for x in r['results'])
    summary['importance_rubric']=args.rubric
    summary['repair_contract']=args.repair_contract
    pilots=[json.loads(path.read_text(encoding='utf-8')) for path in args.out.glob('pilot-*.json')]
    summary['pilot_batches']=len(pilots)
    summary['pilot_estimated_credits']=sum(r.get('estimated_credits',0) for r in pilots)
    summary['total_estimated_credits_including_pilot']=summary['estimated_credits']+summary['pilot_estimated_credits']
    save('summary.json',summary)
    explanation='일반 취준생의 지원 준비 유용성' if args.rubric=='career' else '기업 영향'
    axes_label='기업이해/직무연결/지원활용' if args.rubric=='career' else '영향/지속/확정'
    lines=['# 삼성전자 사업·중요도 AI 초안','', f'사람 정답이 아니다. 관련성은 기존 V1을 유지했다. 점수 기준: {explanation}.',
           '', f'| ID | 제목 | 사업 상태 | 사업 | {axes_label} | 합계 | 보류 이유 |','|---|---|---|---|---|---|---|']
    for source in rows:
        r=runs[0][source['sample_id']]
        def cell(v):return str(v if v is not None else '—').replace('|','\\|').replace('\n',' ')
        # 필수 사유가 빠진 실패 응답도 보고서에 남겨 사람이 검토할 수 있게 한다.
        lines.append('| '+' | '.join(cell(v) for v in [r['sample_id'],source['title'],r['business_status']+(' [형식 실패]' if not r['schema_valid'] else ''),r['related_business'],'/'.join(cell(r.get(k)) for k in score_fields),r['importance_score'],r.get('abstention_reason') or r.get('schema_error')])+' |')
    (args.out/'ai-draft.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
