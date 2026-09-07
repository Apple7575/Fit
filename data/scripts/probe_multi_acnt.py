"""fnlttMultiAcnt(다중회사 주요계정) 실측.

이 저장소는 이 엔드포인트를 한 번도 호출한 적이 없다. 명세만 보고 배치 크기를
정하면 2,703개사를 잘못된 가정으로 훑게 되므로, 쓰기 전에 실측한다
(S15P21A504-85 지시서 원칙 ② · D-3).

재는 것

  T1 단건            기준선. 필드 목록과 회사당 행 수
  T2 10 / 50 / 100   묶음 크기별로 회사가 전부 돌아오는가
  T3 한도 초과       101개를 넣으면 어떻게 되는가
  T4 혼합 내성       ★ 데이터 없는 회사가 섞이면 묶음 전체가 죽는가
  T5 단건 대조       fnlttSinglAcnt 와 같은 값이 오는가

T4 가 가장 중요하다. 2,703개사에는 그 해에 사업보고서가 없는 회사가 반드시
섞인다. 한 곳 때문에 묶음 100개가 통째로 빈다면 배치 전략 자체가 달라진다.

    python scripts/probe_multi_acnt.py --year 2023
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.dart_client import DartApiError, DartClient
from pipeline.paths import ROOT, raw_api_dir
from pipeline.universe import load_universe

OUT = ROOT / "_out"
ENDPOINT = "fnlttMultiAcnt.json"
REPRT = "11011"          # 사업보고서


def call(client: DartClient, codes: list[str], year: int, tag: str) -> dict:
    """묶음 1회 호출. 실패도 결과로 기록한다 — 실패 양상이 실측 대상이다."""
    joined = ",".join(codes)
    name = f"probe_multiacnt_{tag}_{year}.json"
    try:
        body = client.get_json(ENDPOINT, name, corp_code=joined,
                               bsns_year=str(year), reprt_code=REPRT)
    except DartApiError as e:
        return {"tag": tag, "요청": len(codes),
                "error": {"status": e.status, "message": e.message}}

    rows = DartClient.rows(body)
    got = {r.get("corp_code") for r in rows if r.get("corp_code")}
    return {
        "tag": tag,
        "요청": len(codes),
        "status": str(body.get("status")),
        "message": body.get("message"),
        "행": len(rows),
        "응답한_회사": len(got),
        "누락한_회사": sorted(set(codes) - got),
        "회사당_행": round(len(rows) / len(got), 1) if got else 0,
        "필드": sorted(rows[0].keys()) if rows else [],
        "fs_div_값": sorted({r.get("fs_div") for r in rows if r.get("fs_div")}),
        "계정_예시": [r.get("account_nm") for r in rows[:6]],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2023)
    ap.add_argument("--no-cache", action="store_true",
                    help="캐시를 무시하고 새로 받는다")
    args = ap.parse_args()

    universe = load_universe()
    codes = [c.corp_code for c in universe]
    print(f"모집단 {len(universe)}개사 · 기준연도 {args.year}\n")

    client = DartClient(cache=raw_api_dir(), use_cache=not args.no_cache)
    results = []

    # T1·T2·T3 — 묶음 크기
    for n, tag in ((1, "n1"), (10, "n10"), (50, "n50"), (100, "n100"), (101, "n101")):
        r = call(client, codes[:n], args.year, tag)
        results.append(r)
        if "error" in r:
            print(f"  {tag:>5} 요청 {n:>3} → 오류 {r['error'].get('status')} "
                  f"{r['error'].get('message')}")
        else:
            print(f"  {tag:>5} 요청 {n:>3} → status {r['status']} · "
                  f"회사 {r['응답한_회사']:>3} · 행 {r['행']:>4} · "
                  f"회사당 {r['회사당_행']}")

    # T4 — 없는 회사가 섞였을 때. 존재하지 않는 corp_code 를 하나 끼운다.
    mixed = codes[:9] + ["00000000"]
    r = call(client, mixed, args.year, "mixed_badcode")
    results.append(r)
    if "error" in r:
        print(f"\n  혼합(가짜코드 1) → 오류 {r['error'].get('status')} "
              f"{r['error'].get('message')}  ← 묶음 전체가 죽는다")
    else:
        print(f"\n  혼합(가짜코드 1) → 회사 {r['응답한_회사']}/10 · "
              f"누락 {r['누락한_회사']}  ← 나머지는 살아 돌아온다")

    # T5 — 단건 엔드포인트와 대조
    one = codes[0]
    single = client.single_acnt(one, args.year)
    s_rows = DartClient.rows(single)
    m_rows = DartClient.rows(client.get_json(
        ENDPOINT, f"probe_multiacnt_n1_{args.year}.json",
        corp_code=one, bsns_year=str(args.year), reprt_code=REPRT))

    def key(r):
        return (r.get("fs_div"), r.get("sj_div"), r.get("account_nm"))

    s_map = {key(r): r.get("thstrm_amount") for r in s_rows}
    m_map = {key(r): r.get("thstrm_amount") for r in m_rows}
    common = s_map.keys() & m_map.keys()
    same = sum(1 for k in common if s_map[k] == m_map[k])
    print(f"\n  단건 대조 {one} — 단건 {len(s_rows)}행 · 다중 {len(m_rows)}행 · "
          f"공통 {len(common)}개 중 값 일치 {same}")
    results.append({"tag": "vs_single", "단건_행": len(s_rows), "다중_행": len(m_rows),
                    "공통": len(common), "일치": same})

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "probe_multi_acnt.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n호출 {client.stats.calls}회 · 캐시히트 {client.stats.cache_hits}")
    print(f"→ {OUT / 'probe_multi_acnt.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
