"""단위 테스트용 최소 RSS 입력.

**수집한 데이터가 아니다.** 정제·시드 코드의 동작을 검사하려고 손으로 만든 입력이며,
`data/raw/` 나 `data/staged/` 에 두지 않는다. 실제 뉴스 데이터는 이 저장소에 없다
(data/docs/DATA_STORAGE_STANDARD.md 의 「현재 확보 상태」).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ITEM = """  <item>
    <title>{title}</title>
    <link>{link}</link>
    <guid isPermaLink="false">{guid}</guid>
    <pubDate>{pub_date}</pubDate>
    <description>{description}</description>
    <source url="{publisher_url}">{publisher}</source>
  </item>
"""

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>테스트 피드</title>
{items}</channel></rss>
"""


def item(title, link, guid, pub_date, publisher="테스트일보",
         publisher_url="https://news.example.test", description="&lt;p&gt;본문 일부&lt;/p&gt;"):
    return ITEM.format(title=title, link=link, guid=guid, pub_date=pub_date,
                       description=description, publisher=publisher, publisher_url=publisher_url)


def feed(items: list[str]) -> bytes:
    return FEED.format(items="".join(items)).encode("utf-8")


def daily_plan(target_start: str, target_end_exclusive: str) -> list[tuple[str, str]]:
    """수집기 build_plan 과 같은 하루 단위 구간을 만든다 — 앞에 하루를 더 붙인다."""
    from datetime import date, timedelta

    start = date.fromisoformat(target_start)
    end = date.fromisoformat(target_end_exclusive)
    cursor, plan = start - timedelta(days=1), []
    while cursor < end:
        plan.append((cursor.isoformat(), (cursor + timedelta(days=1)).isoformat()))
        cursor += timedelta(days=1)
    return plan


def write_run(directory: Path, entries: list[tuple[str, bytes, str, str]],
              company: str = "삼성전자",
              checked_at: str = "2026-09-06T00:10:00+00:00") -> Path:
    """XML 과 requests.json 을 수집기와 같은 형태로 쓴다.

    entries: (파일명, XML bytes, 쿼리 시작일, 쿼리 종료일) 목록.
    """
    directory.mkdir(parents=True, exist_ok=True)
    requests = {}
    for name, payload, start, end in entries:
        (directory / f"{name}.xml").write_bytes(payload)
        requests[name] = {
            "id": name,
            "query": f"{company} after:{start} before:{end}",
            "start": start, "end": end, "kind": "daily",
            "url": "https://news.google.com/rss/search?q=test",
            "checked_at": checked_at, "user_agent": "SSAFYNewsPoC/0.1",
            "status": "ok", "http_status": 200,
            "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload),
        }
    (directory / "requests.json").write_text(
        json.dumps(requests, ensure_ascii=False, indent=2), encoding="utf-8")
    return directory
