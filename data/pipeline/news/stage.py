"""raw → staged. 원본 RSS 에서 정제 결과를 만든다.

**원본은 읽기만 한다.** 정제 결과는 언제든 지우고 이 코드로 다시 만들 수 있어야 하며,
그래서 수동 편집을 전제한 컬럼을 두지 않는다.

버리는 행이 없다. 기간 밖·입력 결함·기업 매핑 실패는 행을 지우는 대신
`stage_status`·`reject_reason` 으로 구분해 `rejects.csv` 에 남긴다. 무엇이 왜 빠졌는지
세지 못하면 검증(§11-3)을 할 수 없다.

RSS 해석 규칙은 수집기 파서(`parse_feed`)와 품질 선별(`screen_quality`)을 그대로 쓴다.
여기서 다시 구현하면 규칙이 두 곳으로 갈라진다.
"""
from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from pipeline.news import corpmap, rawstore, urls
from pipeline.news.schema import (
    COUNTRY, LANGUAGE, PROVIDER, REJECT_FIELDS, STAGE_SCHEMA_VERSION, STAGED_FIELDS,
)

KST = timezone(timedelta(hours=9))
STAGED_DIR = rawstore.ROOT / "staged" / PROVIDER

# 정제에서 분리하는 사유. 수집기의 issues·quality_issues 를 그대로 쓴다.
REJECT_INPUT_ISSUES = ("missing_title", "invalid_link", "known_listing_page")


def _load_collector():
    """수집기의 품질 선별 함수를 가져온다. 리팩터 전후 두 경로를 모두 시도한다."""
    import sys

    repo_root = str(rawstore.ROOT.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    errors = []
    for name in ("data.news.pipeline.collect", "data.news_poc.pipeline.collect"):
        try:
            return __import__(name, fromlist=["screen_quality"])
        except ImportError as error:      # noqa: PERF203
            errors.append(f"{name}: {error}")
    raise ImportError("수집기 collect 모듈을 찾을 수 없다.\n  " + "\n  ".join(errors))


def _pub_dates(payload: bytes) -> list[str]:
    """item 순서대로 pubDate 원문을 뽑는다.

    parse_feed 는 파싱된 UTC 값만 돌려주는데, 시간대 규칙이 바뀌면 원문을 다시
    읽어야 한다. 해석은 하지 않고 문자열만 가져오므로 파서와 규칙이 겹치지 않는다.
    """
    root = ET.fromstring(payload)
    return [(item.findtext("pubDate") or "").strip() for item in root.findall("./channel/item")]


def _company_of(query: str) -> str:
    """요청 쿼리에서 검색어(회사명)를 떼어 낸다. 쿼리는 '<회사명> after:… before:…' 다."""
    return (query or "").split(" after:")[0].strip()


def derive_target_window(run: rawstore.RawRun) -> tuple[str, str]:
    """요청 계획에서 KST 대상 구간을 되돌린다.

    수집기 build_plan 은 (start-1일) 부터 하루 단위 쿼리를 만들고 마지막 쿼리의 end 가
    args.end 다. 따라서 target_start = min(query.start) + 1일, target_end = max(query.end).
    이 도출이 틀릴 수 있으므로 run.json 이나 CLI 로 덮어쓸 수 있게 두었다.
    """
    start, end = run.target_range()
    if not start or not end:
        return "", ""
    return (date.fromisoformat(start) + timedelta(days=1)).isoformat(), end


@dataclass
class StageResult:
    run_id: str
    rows: list[dict] = field(default_factory=list)      # 대표 행 (중복 아님, 기간 안)
    rejects: list[dict] = field(default_factory=list)   # 분리된 행 + 사유
    duplicates: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def _base_row(row: dict, raw_file: str, index: int, pub_raw: str,
              run_id: str, company: str, collected_at: str) -> dict:
    published = row.get("published_at") or ""
    date_kst = ""
    if published:
        date_kst = datetime.fromisoformat(published).astimezone(KST).date().isoformat()
    title = row.get("title") or ""
    return {
        "article_key": row["article_key"],
        "collection_run_id": run_id,
        "source_raw_file": raw_file,
        "source_record_index": index,
        "corp_code": "",
        "query_company_name": company,
        "corp_map_method": "",
        "corp_map_reason": "",
        "title": title,
        "title_checksum": hashlib.sha256(title.encode("utf-8")).hexdigest(),
        # 검토를 통과한 요약만 채운다. 수집기가 제목 반복을 요약으로 쓰지 않기로 했고
        # (docs/news-poc/90-source-review.md) 그 판단을 여기서 뒤집지 않는다.
        "description": "",
        "description_raw": row.get("description_text") or "",
        "description_status": row.get("description_status") or "",
        "original_url": row.get("original_url") or "",
        "original_url_norm": urls.normalize(row.get("original_url") or ""),
        "original_url_status": row.get("original_url_status") or "",
        "rss_link": row.get("rss_link") or "",
        "google_url": row.get("google_url") or "",
        "guid": row.get("guid") or "",
        # RSS 가 이미지를 주지 않는다. 컬럼은 기준에 맞춰 두고 값은 비운다.
        "image_url": "",
        "provider": PROVIDER,
        "publisher": row.get("publisher") or "",
        "publisher_url": row.get("publisher_url") or "",
        "published_at": published,
        "published_at_raw": pub_raw,
        "published_date_kst": date_kst,
        "collected_at": collected_at,
        "language": LANGUAGE,
        "country": COUNTRY,
        "stage_status": "",
        "is_duplicate": "false",
        "duplicate_of": "",
        "duplicate_rule": "",
        "quality_issues": "|".join(row.get("issues") or []),
        "stage_schema_version": STAGE_SCHEMA_VERSION,
    }


def stage_run(run: rawstore.RawRun, mapper: corpmap.CorpMap,
              target_start: str = "", target_end_exclusive: str = "") -> StageResult:
    """원본 폴더 하나를 정제한다. 네트워크를 쓰지 않는다."""
    normalize = rawstore.load_parser()
    collector = _load_collector()
    if not target_start or not target_end_exclusive:
        derived_start, derived_end = derive_target_window(run)
        target_start = target_start or derived_start
        target_end_exclusive = target_end_exclusive or derived_end

    window_begin = window_end = None
    if target_start and target_end_exclusive:
        window_begin = datetime.combine(date.fromisoformat(target_start), datetime.min.time(), KST)
        window_end = datetime.combine(date.fromisoformat(target_end_exclusive), datetime.min.time(), KST)

    observed: list[dict] = []
    batches = []
    checksum_mismatches = []
    for raw in run.files:
        payload = raw.path.read_bytes()
        parsed = normalize.parse_feed(payload)
        pub_raws = _pub_dates(payload)
        if raw.checksum_matches is False:
            checksum_mismatches.append(raw.relative)
        company = _company_of(raw.request.get("query", ""))
        collected_at = raw.request.get("checked_at", "")
        batches.append((parsed, raw.request.get("query") or raw.plan_id))
        for index, row in enumerate(parsed):
            observed.append(_base_row(
                row, raw.path.name, index,
                pub_raws[index] if index < len(pub_raws) else "",
                run.run_id, company, collected_at,
            ))

    # 관측 순서는 (파일명, item 순번) 으로 결정되므로 재실행해도 같다.
    observed.sort(key=lambda r: (r["source_raw_file"], r["source_record_index"]))

    result = StageResult(run_id=run.run_id)
    seen_key: dict[str, str] = {}
    seen_url: dict[str, str] = {}
    seen_title: dict[tuple[str, str], str] = {}
    in_window = 0
    for row in observed:
        # 순서가 수집기와 같아야 한다 — 기간 필터(summarize) → 품질 선별(screen_quality).
        # 뒤집으면 in_window 가 수집기의 target_observations 와 어긋나 대조(§11-2)가 깨진다.
        if window_begin is not None:
            if not row["published_at"]:
                # 시각을 못 읽은 행은 기간 판정을 할 수 없다. 버리지 않고 남긴다.
                row["stage_status"] = "rejected"
                result.rejects.append(dict(row, reject_reason="unparsed_published_at"))
                continue
            stamp = datetime.fromisoformat(row["published_at"])
            if not (window_begin <= stamp < window_end):
                row["stage_status"] = "rejected"
                result.rejects.append(dict(row, reject_reason="outside_target_window"))
                continue
        in_window += 1

        issues = [i for i in row["quality_issues"].split("|") if i]
        # 수집기의 품질 선별을 그대로 적용한다 (확인된 목록 페이지 등).
        _, rejected = collector.screen_quality([{
            "title": row["title"], "original_url": row["original_url"],
            "rss_link": row["rss_link"], "google_url": row["google_url"],
        }])
        if rejected:
            issues = sorted(set(issues) | set(rejected[0].get("quality_issues") or []))
            row["quality_issues"] = "|".join(issues)

        blocking = [i for i in issues if i in REJECT_INPUT_ISSUES]
        if blocking:
            row["stage_status"] = "rejected"
            result.rejects.append(dict(row, reject_reason="input_defect:" + ",".join(blocking)))
            continue

        rule = ""
        original = ""
        if row["article_key"] in seen_key:
            rule, original = "article_key", seen_key[row["article_key"]]
        elif row["original_url_norm"] and row["original_url_norm"] in seen_url:
            rule, original = "original_url_norm", seen_url[row["original_url_norm"]]
        else:
            title_key = (row["title_checksum"], row["published_date_kst"])
            if row["published_date_kst"] and title_key in seen_title:
                rule, original = "title_checksum+published_date_kst", seen_title[title_key]
        if rule:
            row.update(is_duplicate="true", duplicate_of=original, duplicate_rule=rule,
                       stage_status="duplicate")
            result.duplicates.append(row)
            continue

        seen_key[row["article_key"]] = row["article_key"]
        if row["original_url_norm"]:
            seen_url[row["original_url_norm"]] = row["article_key"]
        if row["published_date_kst"]:
            seen_title[(row["title_checksum"], row["published_date_kst"])] = row["article_key"]

        mapping = mapper.resolve(row["query_company_name"])
        row["corp_code"] = mapping.corp_code
        row["corp_map_method"] = mapping.method
        row["corp_map_reason"] = mapping.reason
        row["stage_status"] = "staged" if mapping.corp_code else "unresolved_corp"
        result.rows.append(row)

    # 수집기 집계와 대조한다. 두 경로가 어긋나면 정제 규칙이 원본과 벌어진 것이다.
    collector_report: dict = {}
    if window_begin is not None:
        specs = [{"id": label, "query": label} for _, label in batches]
        _, collector_report = collector.summarize(
            list(zip(specs, [rows for rows, _ in batches])),
            date.fromisoformat(target_start), date.fromisoformat(target_end_exclusive),
            specs,
        )

    result.summary = {
        "provider": PROVIDER,
        "collection_run_id": run.run_id,
        "stage_schema_version": STAGE_SCHEMA_VERSION,
        "staged_at": datetime.now(timezone.utc).isoformat(),
        "raw_directory": rawstore.relative(run.directory),
        "raw_file_count": len(run.files),
        "raw_checksum_mismatches": checksum_mismatches,
        "target_start": target_start,
        "target_end_exclusive": target_end_exclusive,
        "queries": run.queries(),
        "companies": sorted({r["query_company_name"] for r in observed if r["query_company_name"]}),
        "raw_observations": len(observed),
        "in_window_observations": in_window,
        "staged_rows": len(result.rows),
        "unresolved_corp_rows": sum(1 for r in result.rows if not r["corp_code"]),
        "duplicate_rows": len(result.duplicates),
        "rejected_rows": len(result.rejects),
        "reject_reasons": _count(result.rejects, "reject_reason"),
        "duplicate_rules": _count(result.duplicates, "duplicate_rule"),
        "corp_map_reasons": _count([r for r in result.rows if not r["corp_code"]], "corp_map_reason"),
        "description_status": _count(result.rows, "description_status"),
        "original_url_status": _count(result.rows, "original_url_status"),
        "published_at_parsed": sum(1 for r in observed if r["published_at"]),
        "published_at_unparsed": sum(1 for r in observed if not r["published_at"]),
        # 수집기 집계와의 대조값. 어긋나면 verify_news.py 가 실패로 잡는다.
        "collector_target_observations": (collector_report or {}).get("target_observations"),
        "collector_unique_candidates": (collector_report or {}).get("unique_candidates"),
        "collector_saturated_queries": (collector_report or {}).get("saturated_queries", []),
        "collector_full_coverage_verified": (collector_report or {}).get("full_coverage_verified"),
        "company_universe_rows": mapper.row_count,
    }
    return result


def _count(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.get(key) or "(none)"] = counts.get(row.get(key) or "(none)", 0) + 1
    return dict(sorted(counts.items()))


def write(result: StageResult, out_dir: Path | None = None) -> dict[str, Path]:
    """staged 산출물을 쓴다. 같은 입력이면 같은 파일이 나온다."""
    from pipeline.news.csvio import write_csv

    directory = out_dir or (STAGED_DIR / result.run_id)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "articles": directory / "articles.csv",
        "rejects": directory / "rejects.csv",
        "duplicates": directory / "duplicates.csv",
        "summary": directory / "stage_summary.json",
    }
    write_csv(paths["articles"], STAGED_FIELDS, result.rows)
    write_csv(paths["rejects"], REJECT_FIELDS, result.rejects)
    write_csv(paths["duplicates"], STAGED_FIELDS, result.duplicates)
    paths["summary"].write_text(
        json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return paths
