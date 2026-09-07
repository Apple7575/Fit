"""수집 실행 manifest. 원본 폴더에서 만들고, 손으로 쓰지 않는다.

manifest 는 "이 원본이 언제·무엇을·어떻게 받은 것인가" 를 담는다. 원본 자체는 Git
에 올리지 않으므로(사용조건 미확정·용량) 이 파일이 저장소에 남는 유일한 계보 기록이다.
그래서 manifest 는 커밋한다 — 기사 내용이 아니라 건수·해시·요청 이력만 들어간다.

경로: `data/manifests/google_news_rss/<collection_run_id>.json`
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.news import rawstore
from pipeline.news.schema import MANIFEST_SCHEMA_VERSION, PROVIDER

MANIFEST_DIR = rawstore.ROOT / "manifests" / PROVIDER


def build(run: rawstore.RawRun, target_start: str = "", target_end_exclusive: str = "") -> dict:
    """원본 폴더 하나의 manifest 를 만든다. XML 을 실제로 파싱해 건수를 센다."""
    normalize = rawstore.load_parser()
    collected_first, collected_last = run.collected_range()

    files, total_records, keys = [], 0, {}
    duplicate_candidates = 0
    for raw in run.files:
        payload = raw.path.read_bytes()
        rows = normalize.parse_feed(payload)
        total_records += len(rows)
        for row in rows:
            key = row["article_key"]
            if key in keys:
                duplicate_candidates += 1
            keys[key] = keys.get(key, 0) + 1
        files.append({
            "path": raw.relative,
            "bytes": raw.bytes,
            "sha256": raw.sha256,
            "record_count": len(rows),
            "request_query": raw.request.get("query", ""),
            "request_url": raw.request.get("url", ""),
            "http_status": raw.request.get("http_status"),
            "collected_at": raw.request.get("checked_at", ""),
            "user_agent": raw.request.get("user_agent", ""),
            "recorded_sha256_matches": raw.checksum_matches,
            # 응답이 100건 이상이면 잘렸을 수 있다는 관측 기준이다. 공식 한도가 아니다.
            "possibly_truncated": len(rows) >= 100,
        })

    failed = run.failed_requests
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "provider": PROVIDER,
        "collection_run_id": run.run_id,
        "collection_run_id_conforms": run.run_id_conforms,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "collected_at_first": collected_first,
        "collected_at_last": collected_last,
        "queries": run.queries(),
        "companies": sorted({q.split(" after:")[0].strip() for q in run.queries()}),
        "target_start": target_start,
        "target_end_exclusive": target_end_exclusive,
        "raw_directory": rawstore.relative(run.directory),
        "raw_files": files,
        "raw_file_count": len(files),
        "raw_total_bytes": sum(f["bytes"] for f in files),
        "record_count": total_records,
        "unique_article_keys": len(keys),
        "duplicate_candidate_count": duplicate_candidates,
        "request_count": len(run.requests),
        "success_count": sum(1 for r in run.requests.values() if r.get("status") == "ok"),
        "fail_count": len(failed),
        "failed_queries": [r.get("query", "") for r in failed],
        "saturated_files": [f["path"] for f in files if f["possibly_truncated"]],
        # 수집 코드 버전. 커밋 해시는 실행 환경에 따라 못 읽을 수 있어 모듈 경로로 남긴다.
        "collector_module": normalize.__name__.rsplit(".", 1)[0],
        "full_coverage_verified": False,
        "notes": [
            "원본 XML 은 Git 에 올리지 않는다. 사용조건 미확정 + 재배포 조건 미확인.",
            "possibly_truncated 는 응답 100건 관측 기준이며 공식 한도가 아니다.",
        ],
    }


def path_for(run_id: str, manifest_dir: Path | None = None) -> Path:
    return (manifest_dir or MANIFEST_DIR) / f"{run_id}.json"


def write(document: dict, manifest_dir: Path | None = None) -> Path:
    path = path_for(document["collection_run_id"], manifest_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return path


def load_all(manifest_dir: Path | None = None) -> list[dict]:
    directory = manifest_dir or MANIFEST_DIR
    if not directory.is_dir():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))]
