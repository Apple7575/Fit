"""검증된 PoC 결과를 백엔드 인계 후보로 변환한다. DB 적재나 기업 코드 추정은 하지 않는다."""
import json
from pathlib import Path
root=Path('data/news_poc/local_output/92-career-holdout')
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
inputs={r['sample_id']:r for r in read(root/'dataset.json')}
results=read(root/'analysis/predictions-1.json'); accepted=[];excluded=[]
for r in results:
 s=inputs[r['sample_id']]
 if r['predicted']!='related' or not r['schema_valid']:
  excluded.append(dict(sample_id=r['sample_id'],relevance=r['predicted'],schema_valid=r['schema_valid'],reason=r.get('schema_error','not_related')));continue
 source={x['article_key']:x for x in read(Path(s['source_file']))}[s['article_key']]
 accepted.append(dict(sample_id=r['sample_id'],company_name=s['company'],corp_code=None,article_key=s['article_key'],title=s['title'],description=s['description'],published_at=s['published_at'],original_url=source.get('original_url'),rss_link=s['rss_link'],business_status=r['business_status'],related_business=r['related_business'],importance_score=r['importance_score'],analysis_metadata={k:r.get(k) for k in ['company_understanding','job_connection','application_use','business_reason','company_understanding_reason','job_connection_reason','application_use_reason','abstention_reason']},model='gemini-2.5-flash-lite',rubric='career-v1',relevance=r['predicted'],schema_valid=True))
out=root/'backend-handoff';out.mkdir(exist_ok=True)
for name,data in [('candidates.json',accepted),('excluded.json',excluded),('manifest.json',dict(candidate_count=len(accepted),excluded_count=len(excluded),corp_code_resolution='required against company master',db_loaded=False,api_response=False,original_url_missing=sum(x['original_url'] is None for x in accepted),description_missing=sum(x['description'] is None for x in accepted)))]:
 (out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
assert len(accepted)+len(excluded)==30
assert len({x['article_key'] for x in accepted})==len(accepted)
assert all(0<=x['importance_score']<=10 and x['relevance']=='related' for x in accepted)
assert all(x['corp_code'] is None for x in accepted)
print((out/'manifest.json').read_text(encoding='utf-8'))
