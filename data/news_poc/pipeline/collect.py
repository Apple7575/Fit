"""회사명으로 Google News RSS를 수집하고 KST 대상 기간의 고유 기사를 출력한다.

사용자가 사용조건 조사 후 지시한 한정된 PoC 실행용이다. robots 점검은 별도
근거로 유지하며 사용 허가를 판정하지 않는다. 기사 본문·AI API는 호출하지 않는다.
403/429를 받으면 실행을 중단하고 성공한 XML과 요청 이력을 보존한다.
"""
import argparse
import hashlib
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from data.news_poc.pipeline.normalize import parse_feed, merge_articles, write_csv, ARTICLE_FIELDS, valid_url

AGENT = 'SSAFYNewsPoC/0.1'
KST = timezone(timedelta(hours=9))


def screen_quality(rows):
    """명확한 입력 결함만 분리한다. 기업 관련성·중요도·제목 키워드는 판정하지 않는다.

    Google 경유 URL만으로는 목록 페이지를 판별할 수 없다. 확보된 실제 URL이
    검증한 목록 경로일 때만 제외한다. 분리된 행도 사유와 함께 보관해 복구할 수 있다.
    """
    ready, rejected = [], []
    for row in rows:
        issues = []
        if not (row.get('title') or '').strip():
            issues.append('missing_title')
        if not any(valid_url(row.get(key) or '') for key in ('rss_link','original_url','google_url')):
            issues.append('invalid_link')
        for key in ('original_url', 'rss_link'):
            value = row.get(key) or ''
            if valid_url(value):
                url = urlsplit(value)
                if url.hostname == 'stock.mk.co.kr' and url.path.startswith('/price/news/'):
                    issues.append('known_listing_page')
                    break
        if issues:
            rejected.append(dict(row, quality_issues=issues))
        else:
            ready.append(row)
    return ready, rejected


def build_plan(start, end, company='삼성전자'):
    """KST [start, end) 수집을 위해 앞 날짜부터 일별 회사명 조회를 만든다.

    start/end는 date다. 날짜 연산자의 실제 경계 해석은 수집 후 별도로 검증한다.
    id는 쿼리 해시로 만들어 같은 검색을 재개할 때 동일 파일을 찾는다.
    """
    if start >= end:
        raise ValueError('start must precede end')
    company = company.strip()
    if not company:
        raise ValueError('company must not be empty')
    plan = []

    def add(term, begin, finish, kind):
        query = f'{term} after:{begin.isoformat()} before:{finish.isoformat()}'
        plan.append(dict(id=hashlib.sha256(query.encode()).hexdigest()[:20], query=query,
                         start=begin.isoformat(), end=finish.isoformat(), kind=kind,
                         url='https://news.google.com/rss/search?' + urlencode(
                             dict(q=query, hl='ko', gl='KR', ceid='KR:ko'))))

    # RSS 검색 날짜와 KST 자정이 일치하지 않은 실측을 반영한 보완 구간이다.
    # 여러 날을 요청해도 인접 날짜 쿼리를 중복 생성하지 않는다. 전수 보장은 아니다.
    cursor = start - timedelta(days=1)
    while cursor < end:
        add(company, cursor, cursor + timedelta(days=1), 'daily')
        cursor += timedelta(days=1)
    return plan


def summarize(batches, start, end, plan):
    """KST 기간 필터 후 식별자로 합치고 포화·누락·부분 실행을 별도 보고한다.

    포화는 필터 전 반환 100건 이상이라는 관측 기준이다. 공식 한도나 전수 수집
    판정이 아니다. 제목·기업 관련성은 여기서 필터링하지 않고 검토 대상으로 남긴다.
    """
    begin = datetime.combine(start, datetime.min.time(), KST)
    finish = datetime.combine(end, datetime.min.time(), KST)
    filtered, metrics = [], []
    for spec, rows in batches:
        accepted, invalid = [], 0
        for row in rows:
            try:
                stamp = datetime.fromisoformat(row['published_at'])
                if stamp.tzinfo is None:
                    raise ValueError('Timezone missing')
            except (TypeError, ValueError):
                invalid += 1
                continue
            if begin <= stamp < finish:
                accepted.append(row)
        filtered.append((accepted, spec['query']))
        metrics.append(dict(query=spec['query'], raw_count=len(rows),
                            target_count=len(accepted), invalid_date_count=invalid,
                            outside_count=len(rows)-len(accepted)-invalid,
                            possibly_truncated=len(rows) >= 100))
    merged = merge_articles(filtered)
    succeeded = {spec['id'] for spec, _ in batches}
    missing = [spec['query'] for spec in plan if spec['id'] not in succeeded]
    return merged, dict(target_start=begin.isoformat(), target_end_exclusive=finish.isoformat(),
        all_queries_succeeded=not missing, missing_queries=missing,
        saturated_queries=[m['query'] for m in metrics if m['possibly_truncated']],
        raw_observations=sum(m['raw_count'] for m in metrics),
        target_observations=sum(m['target_count'] for m in metrics),
        invalid_date_observations=sum(m['invalid_date_count'] for m in metrics),
        unique_candidates=len(merged), missing_titles=sum(not r['title'] for r in merged),
        full_coverage_verified=False, queries=metrics)


def fetch(url, opener=urlopen, sleep=time.sleep):
    """RSS bytes·HTTP 상태·최종 URL을 반환한다. 일시 오류는 최대 2회 재시도한다.

    5xx/통신 오류는 5초·10초 후 재시도한다. 다른 HTTP 오류는 즉시 전파한다.
    opener/sleep 주입으로 네트워크 없는 테스트가 가능하다.
    """
    for attempt in range(3):
        try:
            with opener(Request(url, headers={'User-Agent': AGENT}), timeout=25) as response:
                payload = response.read(10_000_001)
                if len(payload) > 10_000_000:
                    raise ValueError('RSS exceeds 10 MB limit')
                return payload, response.status, response.url
        except (HTTPError, URLError, TimeoutError) as error:
            if isinstance(error, HTTPError) and error.code < 500:
                raise
            if attempt == 2:
                raise
            sleep(5 * 2 ** attempt)


def save_json(path, value):
    """체크포인트 JSON을 임시 파일에 쓴 뒤 교체해 중간 쓰기 손상을 줄인다."""
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def compare_snapshots(previous, current):
    """동일 조건 재조회의 관측 차이를 비교한다. 미재관측을 기사 삭제로 해석하지 않는다."""
    old = {row['article_key']: row for row in previous}
    new = {row['article_key']: row for row in current}
    fields = ('title', 'published_at', 'description_text', 'publisher')
    changed = []
    for key in sorted(old.keys() & new.keys()):
        differences = [field for field in fields if old[key].get(field) != new[key].get(field)]
        if differences:
            changed.append(dict(article_key=key, fields=differences))
    return dict(previous_count=len(old), current_count=len(new),
                newly_observed_keys=sorted(new.keys() - old.keys()),
                not_reobserved_keys=sorted(old.keys() - new.keys()), changed=changed)


def main():
    """요청별 결과를 기록하고 재실행 시 검증된 기존 XML은 다시 요청하지 않는다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=date.fromisoformat, required=True)
    parser.add_argument('--end', type=date.fromisoformat, required=True, help='exclusive end date')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--company', default='삼성전자', help='검색할 회사명 하나')
    parser.add_argument('--previous-metadata', type=Path, help='동일 기업·기간의 이전 collection_metadata.json')
    parser.add_argument('--result-out', type=Path, help='CSV·집계 출력 경로. 기본: out/results')
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--limit', type=int, default=0, help='0 means full plan')
    args = parser.parse_args()
    if args.interval < 5 or args.limit < 0:
        parser.error('interval must be >=5; limit must be >=0')
    try:
        full_plan = build_plan(args.start, args.end, args.company)
    except ValueError as error:
        parser.error(str(error))
    plan = full_plan[:args.limit] if args.limit else full_plan
    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out / 'requests.json'
    records = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    requested = False
    failed = False
    batches = []
    for index, spec in enumerate(plan, 1):
        path = args.out / (spec['id'] + '.xml')
        previous = records.get(spec['id'], {})
        if path.exists() and previous.get('status') == 'ok':
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() == previous.get('sha256'):
                batches.append((spec, parse_feed(payload)))
                print(f'[{index}/{len(plan)}] cached {spec["query"]}', flush=True)
                continue
        if requested:
            time.sleep(args.interval)
        requested = True
        record = dict(spec, checked_at=datetime.now(timezone.utc).isoformat(), user_agent=AGENT)
        began = time.monotonic()
        stop = False
        try:
            payload, status, final_url = fetch(spec['url'])
            rows = parse_feed(payload)
            # 유효한 RSS만 정규화 입력에 넣는다. HTML 오류 페이지를 XML로 남기지 않는다.
            temporary = path.with_suffix('.tmp')
            temporary.write_bytes(payload)
            temporary.replace(path)
            record.update(status='ok', http_status=status, final_url=final_url, count=len(rows),
                          sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))
            batches.append((spec, rows))
        except Exception as error:
            failed = True
            record.update(status='error', error=str(error))
            if isinstance(error, HTTPError):
                record['http_status'] = error.code
                stop = error.code in (403, 429)
            # 응답이 RSS가 아니면 동의 화면/차단 가능성이 있으므로 추가 요청하지 않는다.
            if isinstance(error, ValueError):
                stop = True
        record['elapsed_seconds'] = round(time.monotonic() - began, 3)
        records[spec['id']] = record
        save_json(manifest_path, records)
        print(f'[{index}/{len(plan)}] {record["status"]} count={record.get("count", 0)} {spec["query"]}', flush=True)
        if stop:
            print('Stopped after server restriction or invalid response.', flush=True)
            break
    # 폴더에 남아 있는 과거 키워드 XML은 합치지 않고 이번 계획의 성공 응답만 사용한다.
    rows, report = summarize(batches, args.start, args.end, full_plan)
    report['company'] = args.company.strip()
    result_out = args.result_out or args.out / 'results'
    result_out.mkdir(parents=True, exist_ok=True)
    ready, rejected = screen_quality(rows)
    report.update(quality_ready_count=len(ready), quality_rejected_count=len(rejected))
    write_csv(result_out / 'news_samples.csv', ARTICLE_FIELDS, ready)
    write_csv(result_out / 'quality_rejected.csv', ARTICLE_FIELDS + ['article_key','quality_issues'], rejected)
    save_json(result_out / 'quality_rejected.json', rejected)
    save_json(result_out / 'analysis_input.json', ready)
    # 전체 메타데이터는 유지한다. 분석 입력과 분리된 행은 별도 파일로 확인한다.
    save_json(result_out / 'collection_metadata.json', rows)
    save_json(result_out / 'collection_summary.json', report)
    if args.previous_metadata:
        previous = json.loads(args.previous_metadata.read_text(encoding='utf-8'))
        save_json(result_out / 'snapshot_comparison.json', compare_snapshots(previous, rows))
    print(f'KST unique candidates={len(rows)}, saturated queries={len(report["saturated_queries"])}', flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
