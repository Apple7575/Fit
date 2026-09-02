"""API 클라이언트 실측 점검 (WP-2 / F-26·F-24 AC2).

두 부분으로 나뉜다.

  [A] 캐시 점검   .cache 의 기존 응답으로 함정 ②(fs_div)와 빈 결과 처리를 확인한다.
                 네트워크를 쓰지 않으므로 언제든 돌릴 수 있다.
  [B] 오류 실측   일부러 잘못된 인증키로 호출해 실제 오류 응답을 받아본다.
                 F-24 AC2 "호출 제한과 오류 응답이 확인된다" 근거.
                 --live 를 줬을 때만 실행하고, 결과는 docs/API_NOTES.md 에 옮긴다.

실행
    python scripts/probe_api.py            # 캐시 점검만
    python scripts/probe_api.py --live     # 오류 실측까지 (실제 호출 4건)
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.dart_client import DartClient, DartApiError  # noqa: E402

SAMSUNG = "00126380"     # 삼성전자
SHIFTUP = "01384787"     # 시프트업 — 2024 상장. 2021~23 은 상장 이전이라 013 이 온다
                         # (corp_code 는 config/targets.csv 기준. 틀린 값도 013 이 오므로 주의)

ok = fail = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global ok, fail
    mark = "OK  " if cond else "FAIL"
    if cond:
        ok += 1
    else:
        fail += 1
    print(f"  {mark}  {label}{('  — ' + detail) if detail else ''}")


def cache_checks() -> None:
    """캐시만으로 확인 가능한 것들. 호출이 나가면 안 된다."""
    print("[A] 캐시 점검 (네트워크 미사용)")
    c = DartClient()

    body = c.single_acnt(SAMSUNG, 2024)
    rows = c.rows(body)
    check("fnlttSinglAcnt 응답 수신", body.get("status") == "000", f"{len(rows)}행")
    check("fnlttSinglAcnt 행에 fs_div 있음 (함정 ②)",
          bool(rows) and "fs_div" in rows[0],
          "값 " + ",".join(sorted({r.get("fs_div", "") for r in rows})))

    all_body = c.single_acnt_all(SAMSUNG, 2024)
    all_rows = c.rows(all_body)
    check("fnlttSinglAcntAll 응답 수신", all_body.get("status") == "000", f"{len(all_rows)}행")
    check("fnlttSinglAcntAll 행에 fs_div 없음 (함정 ②)",
          bool(all_rows) and "fs_div" not in all_rows[0])
    check("fnlttSinglAcntAll 행에 account_id 있음",
          bool(all_rows) and "account_id" in all_rows[0])

    emp = c.emp_status(SAMSUNG, 2024)
    emp_rows = c.rows(emp)
    check("empSttus 평균근속 필드명 avrg_cnwk_sdytrn",
          bool(emp_rows) and "avrg_cnwk_sdytrn" in emp_rows[0])

    check("호출이 전부 캐시로 해결됨",
          c.stats.calls == 0 and c.stats.cache_hits == 3,
          f"calls={c.stats.calls} cache_hits={c.stats.cache_hits}")

    # 상장 이전 연도(시프트업 2022)의 013 응답. 이 구간은 호출이 나가면 안 되므로
    # 캐시에 없으면 그냥 건너뛴다 — 캐시 미스로 API를 타면 [A]의 전제가 깨진다.
    pre_cache = c.cache / f"empSttus_{SHIFTUP}_2022.json"
    if not pre_cache.exists():
        print(f"  --    {pre_cache.name} 캐시 없음 — 013 점검 건너뜀")
        return
    pre = c.emp_status(SHIFTUP, 2022)
    check("status 013 을 빈 결과로 처리 (함정 ③)",
          pre.get("status") == "013" and c.rows(pre) == [],
          f"시프트업 2022(상장 이전) status={pre.get('status')}")
    check("[A] 전체에서 실제 호출 0건", c.stats.calls == 0, f"calls={c.stats.calls}")


def live_error_probes() -> None:
    """잘못된 인증키로 실제 오류 응답을 받아 기록한다 (F-24 AC2)."""
    print("\n[B] 오류 응답 실측 (실제 호출)")
    # 캐시를 더럽히지 않도록 임시 디렉터리를 쓴다
    tmp = Path(tempfile.mkdtemp(prefix="dart_probe_"))

    bad = DartClient(key="0" * 40, cache=tmp)
    try:
        bad.single_acnt(SAMSUNG, 2024)
        check("잘못된 키 → 오류", False, "예외가 발생하지 않았다")
    except DartApiError as e:
        check("잘못된 키(40자) → 인증 오류 status", e.status in ("010", "011"),
              f"[{e.status}] {e.message}")

    short = DartClient(key="abc", cache=tmp)
    try:
        short.single_acnt(SAMSUNG, 2024)
        check("길이가 틀린 키 → 오류", False, "예외가 발생하지 않았다")
    except DartApiError as e:
        check("길이가 틀린 키 → 오류 status", bool(e.status), f"[{e.status}] {e.message}")

    # zip 엔드포인트는 실패 시 zip 이 아니라 XML 에러 문서를 준다 (함정 ①)
    try:
        bad.document("20250311000000")
        check("잘못된 키 + document.xml → 오류", False, "예외가 발생하지 않았다")
    except DartApiError as e:
        check("document.xml 실패 응답은 zip 이 아니다 (함정 ①)", e.status != "non_zip",
              f"[{e.status}] {e.message}")

    # 없는 접수번호: 유효한 키로 확인 (파일 없음 = 014)
    real = DartClient(cache=tmp)
    try:
        real.document("99999999999999")
        check("없는 접수번호 → 오류", False, "예외가 발생하지 않았다")
    except DartApiError as e:
        check("없는 접수번호 → status 확인", bool(e.status), f"[{e.status}] {e.message}")

    print(f"\n  실제 호출 {bad.stats.calls + short.stats.calls + real.stats.calls}건 "
          f"(일 한도 20,000)")


if __name__ == "__main__":
    cache_checks()
    if "--live" in sys.argv:
        live_error_probes()
    else:
        print("\n[B] 오류 실측은 --live 를 줘야 실행된다")
    print(f"\n{ok}/{ok + fail} 통과")
    sys.exit(1 if fail else 0)
