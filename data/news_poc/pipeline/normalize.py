"""로컬 Google News RSS XML을 뉴스 CSV와 검토용 메타데이터로 변환한다.

기사 본문이나 AI API를 호출하지 않는다. 요약·AI 분석 값은 검증 없이
채우지 않으며, 데이터 누락과 링크 확인 상태를 메타데이터에 남긴다.
"""
import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import xml.etree.ElementTree as ET

# 카테고리 분류를 제외하기로 한 팀 결정에 맞춘 PoC 출력 컬럼이다.
ARTICLE_FIELDS = ['title', 'description', 'published_at', 'original_url',
                  'related_business', 'importance_score']


class TextOnly(HTMLParser):
    """HTML 태그를 제외한 텍스트 조각을 수집한다. HTML 정화 도구는 아니다."""

    def __init__(self):
        """문자 참조를 해석하고 텍스트 조각을 담을 목록을 초기화한다."""
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        """파서가 전달하는 텍스트 조각을 원래 순서대로 보관한다."""
        self.parts.append(data)


def plain(value):
    """HTML 문자열 또는 None을 공백이 정리된 일반 텍스트로 반환한다."""
    parser = TextOnly()
    parser.feed(value or '')
    return ' '.join(' '.join(parser.parts).split())


def valid_url(value):
    """호스트가 있고 사용자명이 없는 HTTP(S) URL인지 검사한다.

    문자열 형식만 확인한다. 실제 접근 가능 여부나 원문 기사 여부는 검증하지 않는다.
    """
    try:
        url = urlsplit(value)
        return url.scheme in ('https', 'http') and bool(url.hostname) and not url.username
    except ValueError:
        return False


def is_google(value):
    """파싱 가능한 URL의 호스트가 google.com 또는 그 하위 도메인인지 반환한다."""
    host = (urlsplit(value).hostname or '').lower()
    return host == 'google.com' or host.endswith('.google.com')


def identity_link(value):
    """중복 식별용으로 Google URL의 쿼리와 fragment를 제거한다.

    외부 URL은 쿼리가 기사 식별자일 수 있어 그대로 유지한다.
    원문 URL을 찾거나 링크를 방문하는 함수는 아니다.
    """
    if valid_url(value) and is_google(value):
        url = urlsplit(value)
        return urlunsplit((url.scheme, url.netloc, url.path, '', ''))
    return value


def parse_feed(payload):
    """RSS XML 바이트를 뉴스 필드와 검토 정보가 포함된 dict 목록으로 변환한다.

    Args:
        payload: 로컬 XML 파일에서 읽은 bytes.

    Returns:
        뉴스 6개 컬럼, article_key, 출처·링크·설명 상태, issues를 담은 목록.
        항목의 제목·날짜·링크 오류는 행을 버리는 대신 issues에 기록한다.
        description과 AI 필드는 검토/실행 전이므로 항상 None이다.

    Raises:
        ValueError: 용량 제한 초과, DTD/ENTITY 선언 탐지, RSS 구조 불일치.
        ET.ParseError: XML 구문을 파싱할 수 없는 경우.
    """
    # 예상 밖의 대용량 응답과 명시적인 DTD/ENTITY 선언을 파싱 전에 거른다.
    if len(payload) > 10_000_000:
        raise ValueError('RSS exceeds 10 MB limit')
    if b'<!DOCTYPE' in payload.upper() or b'<!ENTITY' in payload.upper():
        raise ValueError('DTD/entities are not accepted')
    root = ET.fromstring(payload)
    if root.tag != 'rss' or root.find('channel') is None:
        raise ValueError('Expected RSS channel; possibly HTML/consent response')
    rows = []
    for element in root.findall('./channel/item'):
        issues = []
        raw_title = plain(element.findtext('title'))
        publisher = plain(element.findtext('source'))
        title = raw_title
        # 제목 본문에 포함된 언론사명까지 지우지 않도록 끝의 정확한 접미사만 제거한다.
        if publisher and title.endswith(' - ' + publisher):
            title = title[:-(len(publisher) + 3)].strip()
        if not title:
            issues.append('missing_title')
        description_text = plain(element.findtext('description'))
        # HTML을 벗겨도 제목·언론사만 남을 수 있다. 문장부호 차이를 제거해 비교한다.
        canonical = lambda text: re.sub(r'[\W_]+', '', text).casefold()
        repeats = {canonical(raw_title), canonical(title), canonical(title + publisher)}
        description_status = ('missing' if not description_text else
                              'title_repeat' if canonical(description_text) in repeats else 'needs_review')
        published = None
        try:
            value = parsedate_to_datetime(element.findtext('pubDate') or '')
            if value.tzinfo is None:
                # 로컬 컴퓨터의 시간대를 임의 적용하면 기사 시각이 달라질 수 있다.
                raise ValueError('Timezone is missing')
            published = value.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError):
            issues.append('invalid_date')
        link = (element.findtext('link') or '').strip()
        good_link = valid_url(link)
        # 외부 링크도 원문 '후보'일 뿐이다. 언론사 홈페이지(source url)는 대체하지 않는다.
        original = link if good_link and not is_google(link) else None
        if not good_link:
            issues.append('invalid_link')
        guid = (element.findtext('guid') or '').strip()
        # GUID → 링크 → 제목·언론사·날짜 순으로 안정적인 중복 식별 키를 만든다.
        key = guid or identity_link(link) or '|'.join([title, publisher, published or ''])
        source = element.find('source')
        rows.append(dict(
            article_key=hashlib.sha256(key.encode()).hexdigest(),
            title=title, description=None, published_at=published, original_url=original,
            related_business=None, importance_score=None,
            google_url=link if good_link and is_google(link) else None,
            rss_link=link, guid=guid, publisher=publisher,
            publisher_url=source.get('url') if source is not None else None,
            description_text=description_text, description_status=description_status,
            original_url_status='rss_direct_unverified' if original else 'unresolved',
            issues=issues,
        ))
    return rows


def merge_articles(batches):
    """(기사 목록, 출처 라벨) 묶음을 article_key 기준으로 합친다.

    먼저 만난 행과 입력 순서를 유지하고 queries에 중복 없는 출처 라벨을 모은다.
    export에서는 라벨로 파일명을 사용한다. 기사 정정 반영이나 사건 단위 병합은 하지 않는다.
    """
    merged = {}
    for rows, query in batches:
        for row in rows:
            key = row['article_key']
            if key not in merged:
                merged[key] = dict(row, queries=[])
            if query not in merged[key]['queries']:
                merged[key]['queries'].append(query)
    return list(merged.values())


def safe_cell(value):
    """None은 빈 셀로, 수식처럼 시작하는 값은 작은따옴표를 붙인 문자열로 반환한다.

    스프레드시트 표시용 처리다. 변형되지 않은 분석 입력은 별도 JSON을 사용한다.
    """
    if value is None:
        return ''
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


def write_csv(path, fields, rows):
    """지정한 컬럼 순서로 dict 행들을 UTF-8 BOM CSV에 덮어쓴다.

    path는 pathlib.Path, fields는 컬럼명 목록이다. 추가 키는 제외하고 누락은 빈 셀로 쓴다.
    부모 디렉터리는 호출자가 준비해야 한다.
    """
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({key: safe_cell(row.get(key)) for key in fields})


def export(inputs, out):
    """로컬 XML 파일들을 합쳐 CSV 2개·JSON 2개를 저장하고 검증 요약을 반환한다.

    Args:
        inputs: 입력 순서대로 처리할 pathlib.Path 목록. 빈 목록은 허용하지 않는다.
        out: 산출물을 저장할 pathlib.Path 디렉터리. 없으면 생성한다.

    Returns:
        파일 해시·기사 수·누락 수와 미실행 검증 항목을 담은 report dict.

    Raises:
        ValueError, ET.ParseError: 입력 없음 또는 RSS 검증/파싱 실패.
        OSError: 입력 읽기나 출력 쓰기 실패.

    같은 이름의 산출물을 재생성한다. 누적 적재가 아니며 쓰기 전체가 원자적이지는 않다.
    """
    if not inputs:
        raise ValueError('No RSS input files; no sample data will be fabricated')
    batches, sources = [], []
    for path in inputs:
        payload = path.read_bytes()
        rows = parse_feed(payload)
        batches.append((rows, path.name))
        sources.append(dict(file=path.name, sha256=hashlib.sha256(payload).hexdigest(), count=len(rows)))
    rows = merge_articles(batches)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / 'news_samples.csv', ARTICLE_FIELDS, rows)
    # CSV 첫 줄은 헤더이므로 첫 기사 위치는 2행이다. 원문 값은 JSON에 그대로 남긴다.
    metadata = [dict(row, csv_row=index + 2) for index, row in enumerate(rows)]
    (out / 'collection_metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    # 첫 100건은 검토 대기열이다. 정답 라벨이나 대표성 있는 표본으로 간주하지 않는다.
    evaluation = [dict(article_key=r['article_key'], title=r['title'], description=r['description'],
                       relevance='', expected_business='', expected_importance='', reviewer='', notes='') for r in rows[:100]]
    write_csv(out / 'evaluation_input.csv', ['article_key', 'title', 'description', 'relevance',
                                          'expected_business', 'expected_importance', 'reviewer', 'notes'], evaluation)
    report = dict(generated_at=datetime.now(timezone.utc).isoformat(), source_files=sources,
                  total_items=sum(len(batch) for batch, _ in batches), unique_items=len(rows),
                  summary_count=sum(r['description'] is not None for r in rows),
                  direct_original_candidates=sum(r['original_url'] is not None for r in rows),
                  invalid_dates=sum(r['published_at'] is None for r in rows),
                  missing_titles=sum(not r['title'] for r in rows),
                  evaluation_note='First 100 rows are a review queue, not a balanced gold dataset; human selection required',
                  ai_execution='not_run', original_link_validation='not_run')
    (out / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    """CLI 인자를 읽어 XML을 파일명 순으로 변환하고 보고서를 출력한다.

    입력/출력 경로가 같으면 argparse 오류로 종료한다. 파일·파싱 오류는 종료 코드 1이다.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='Directory of lawfully obtained RSS XML files')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.out.resolve():
        parser.error('Use a separate output directory')
    try:
        print(json.dumps(export(sorted(args.input.glob('*.xml')), args.out), ensure_ascii=False, indent=2))
    except (ValueError, ET.ParseError, OSError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
