"""저장된 새 표본 응답만 감사한다. API 호출·정답 생성·실패 행 삭제는 하지 않는다."""
import json
from pathlib import Path
from collections import Counter
p=Path('data/news_poc/local_output/92-career-holdout').resolve()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def save(name,obj):(p/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
a=p/'analysis';summary=read(a/'summary.json');inputs={r['sample_id']:r for r in read(a/'input.json')}
records=[read(f) for f in sorted(a.glob('run-*-batch-*.json'))]
assert all(r['status']=='success' for r in records)
rows=[r for record in records for r in record['results']]
raw=[r for record in records for r in record['raw_results']]
fields=['company_understanding','job_connection','application_use'];violations=[]
for r in rows:
 source=inputs[r['sample_id']]
 if r['predicted']!=source['relevance']:violations.append(dict(id=r['sample_id'],rule='relevance_changed'))
 if source['relevance']!='related' and (r.get('business_status')!='not_applicable' or r.get('related_business') is not None or any(r.get(k) is not None for k in fields+['importance_score'])):violations.append(dict(id=r['sample_id'],rule='relevance_gate'))
 if 'news_category' in r or 'category' in r:violations.append(dict(id=r['sample_id'],rule='category_present'))
failures=[dict(id=r['sample_id'],error=r['schema_error']) for r in rows if not r['schema_valid']]
relevance=read(p/'relevance/gemini-2.5-flash-lite/run.json')
first_records=[read(f) for f in sorted(a.glob('run-1-batch-*.json'))]
# 반복 실험 비용과 실제 한 번 처리 비용을 분리한다.
firstcredits=sum(r['estimated_credits'] for r in first_records)
report=dict(sample_n=30,total_analysis_outputs=len(rows),raw_valid=len(raw)-summary['raw_schema_error_rows'],normalized_valid=len(rows)-len(failures),schema_errors=dict(Counter(r['error'] for r in failures)),violations=violations,failed_rows=failures,summary=summary,relevance_credits=relevance['estimated_credits'],first_analysis_credits=firstcredits,first_pipeline_credits=firstcredits+relevance['estimated_credits'],first_pipeline_credits_per_article=(firstcredits+relevance['estimated_credits'])/30,total_experiment_credits=summary['estimated_credits']+relevance['estimated_credits'],total_request_seconds=summary['request_seconds']+relevance['request_seconds'],human_accuracy=None,semantic_reason_validity=None,disposition='유효 출력만 후보로 사용. 형식 실패는 격리. 자동 검증 결과이며 운영 승인 아님.')
save('harness-result.json',report)
lines=['# 새 기사 자동 하네스 결과','', '사람 정답 없이 자동 형식·규칙·반복 안정성을 측정했다. 정확도·근거 타당성은 미측정이다.','',f"- 첫 분석: {summary['first_run_valid_rows']}/30 형식 유효",f"- 관련 기사 점수 출력: {summary['importance_scored']}/{summary['related_gate_count']}",f"- 전체 형식 유효: 원시 {report['raw_valid']}/{len(rows)}, 정규화 후 {report['normalized_valid']}/{len(rows)}",f"- 사업 반복 일치: {summary['business_status_and_value_stable']}/{summary['repeat_count']}",f"- 세 번 유효 점수 확보: {summary['repeat_all_scores_available']}/{summary['repeat_count']}; 이 중 2점 이내 변동 {summary['repeat_score_range_within2']}건",f"- 관련성 유지·차단·카테고리 검사 위반: {len(violations)}",f"- 형식 실패 유형: {report['schema_errors']}",f"- 한 번 처리 추정 비용(관련성 포함): {report['first_pipeline_credits']:.3f} Credit, 기사당 {report['first_pipeline_credits_per_article']:.3f}",f"- 반복 포함 전체 실험: {report['total_experiment_credits']:.3f} Credit, 요청 시간 합계 {report['total_request_seconds']:.2f}초",'', '정규화는 원시 출력과 분리 보존한다. 유효하지 않은 출력은 서비스 저장 후보에서 제외해야 한다. 수치 통과 기준을 사후에 만들지 않았으며 최종 운영 Pass를 의미하지 않는다.']
(p/'harness-result.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
