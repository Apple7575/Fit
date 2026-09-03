"""백엔드 조회 API 응답 원본 수집 (S15P21A504-86 Step 1).

    python scripts/probe_backend_api.py
    python scripts/probe_backend_api.py --base-url http://staging:8080
    python scripts/probe_backend_api.py --list        # 호출 목록만 보고 끝낸다

**해석하지 않는다.** 받은 응답을 그대로 `tests/fixtures/api/` 에 저장할 뿐이다.
DB 값과의 대조는 `scripts/verify_api.py`(Step 2)가 한다. 수집과 검증을 분리하는
것은 DART 수집 계층과 같은 이유다 — 대조 규칙을 고쳤을 때 API 를 다시 때리지
않으려면 원본이 파일로 남아 있어야 한다.

왜 응답을 먼저 찍어보나
--------------------
명세서를 믿지 말라는 것이 이 프로젝트의 원칙 ②다. 실제로 이번에도 걸렸다 —
검색 파라미터를 `query` 로 짐작했으나 실제는 `keyword` 였고 400 이 났다.
명세와 다른 점이 나오면 그 자체가 86 의 발견 사항이다.

**접속 대상은 인자로 뺀다.** 지금은 로컬 백엔드를 보지만, 스테이징 적재가
끝나면 `--base-url` 만 바꿔 같은 스크립트를 재사용한다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.paths import ROOT  # noqa: E402
from pipeline.targets import load_targets  # noqa: E402

DEFAULT_BASE = "http://127.0.0.1:8080"
OUT = ROOT / "tests" / "fixtures" / "api"

# 표본 기업 — 정상 경로와 예외 경로를 모두 덮는다
SAMSUNG = "00126380"       # 5년 전부 · 모든 지표 정상
SHIFTUP = "01384787"       # 2024 상장 · 2년만 · rejected 지표 포함


def cases(corp_codes: list[str]) -> list[tuple[str, str, dict]]:
    """(저장 이름, 경로, 쿼리) 목록. 이름이 곧 파일명이 된다."""
    out: list[tuple[str, str, dict]] = [
        # 검색 — 파라미터는 query 가 아니라 keyword 다
        ("search_삼성", "/api/companies", {"keyword": "삼성"}),
        ("search_없는이름", "/api/companies", {"keyword": "존재하지않는회사명"}),
        ("search_종목코드", "/api/companies", {"keyword": "005930"}),
        # 파라미터 누락·경계값 — 오류 응답 형태도 규격이다
        ("search_빈키워드", "/api/companies", {"keyword": " "}),
        ("search_페이지크기초과", "/api/companies", {"keyword": "삼성", "size": 101}),
    ]
    for cc in corp_codes:
        out += [
            (f"detail_{cc}", f"/api/companies/{cc}", {}),
            # year 생략 = 최신 적재 연도
            (f"metrics_{cc}_최신", f"/api/companies/{cc}/metrics", {}),
            (f"metrics_{cc}_2025", f"/api/companies/{cc}/metrics", {"year": 2025}),
            (f"metrics_{cc}_2021", f"/api/companies/{cc}/metrics", {"year": 2021}),
            (f"metrics_{cc}_yoy없이", f"/api/companies/{cc}/metrics",
             {"year": 2025, "yoy": "false"}),
            (f"timeseries_{cc}", f"/api/companies/{cc}/metrics/timeseries",
             {"from": 2021, "to": 2025}),
            (f"timeseries_{cc}_단일지표", f"/api/companies/{cc}/metrics/timeseries",
             {"from": 2021, "to": 2025, "keys": "revenue"}),
            (f"comparison_{cc}", f"/api/companies/{cc}/industry-comparison", {"year": 2025}),
        ]
    out += [
        # 없는 기업 · 상장 이전 연도 — 404 인지 빈 응답인지가 규격이다
        ("detail_없는기업", "/api/companies/99999999", {}),
        (f"metrics_시프트업_2022_상장이전", f"/api/companies/{SHIFTUP}/metrics",
         {"year": 2022}),
    ]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="백엔드 API 응답 원본 수집")
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--corp", nargs="+", default=[SAMSUNG, SHIFTUP],
                    help="상세 조회 대상 corp_code")
    ap.add_argument("--list", action="store_true", help="호출 목록만 출력")
    ap.add_argument("--timeout", type=float, default=10.0)
    args = ap.parse_args()

    plan = cases(args.corp)
    if args.list:
        for name, path, params in plan:
            print(f"  {name:<34} {path}  {params}")
        print(f"\n총 {len(plan)}건")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    ok = fail = 0
    index: list[dict] = []

    for name, path, params in plan:
        url = args.base_url + path
        t0 = time.monotonic()
        try:
            # requests 가 UTF-8 로 인코딩한다. 셸에서 한글을 넘기면 CP949 로
            # 깨져 500 이 난다(실제로 겪었다) — 그래서 curl 을 쓰지 않는다
            r = requests.get(url, params=params, timeout=args.timeout)
            elapsed = int((time.monotonic() - t0) * 1000)
            try:
                body = r.json()
                text = None
            except ValueError:
                body, text = None, r.text[:2000]

            (OUT / f"{name}.json").write_text(json.dumps({
                "_request": {"path": path, "params": params},
                "_status": r.status_code,
                "_elapsed_ms": elapsed,
                "_content_type": r.headers.get("content-type"),
                "body": body,
                "text": text,
            }, ensure_ascii=False, indent=2), encoding="utf-8")

            marker = "OK " if r.status_code < 400 else "ERR"
            print(f"  {marker} {r.status_code}  {name:<34} {elapsed:>5}ms")
            index.append({"name": name, "path": path, "params": params,
                          "status": r.status_code, "elapsed_ms": elapsed})
            ok += 1
        except Exception as e:
            print(f"  FAIL   {name:<34} {type(e).__name__}: {e}")
            index.append({"name": name, "path": path, "params": params,
                          "status": None, "error": f"{type(e).__name__}: {e}"})
            fail += 1

    (OUT / "_index.json").write_text(
        json.dumps({"base_url": args.base_url, "cases": index},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n수집 {ok}건 / 실패 {fail}건  →  {OUT}")
    codes: dict[int, int] = {}
    for c in index:
        if c.get("status"):
            codes[c["status"]] = codes.get(c["status"], 0) + 1
    print("상태코드 " + ", ".join(f"{k} {v}건" for k, v in sorted(codes.items())))
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
