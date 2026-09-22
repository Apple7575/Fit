"""전 종목 뉴스 수집 드라이버 — 기업 목록을 돌며 Google 뉴스 RSS 를 받는다.

`news_poc/pipeline/collect.py` 는 **기업 하나**를 하루 창으로 받는다. 100개사까지는
사람이 그것을 감싸는 스크립트로 돌렸는데 **그 드라이버가 저장소에 없었다** — 한 사람
노트북에만 있어 남이 이어 돌릴 수 없었다. 전 종목(2,703개사)으로 넓히기로 하면서
(2026-09-21 팀장 확정) 그 자리를 이 스크립트가 맡는다.

설계는 `docs/S15P21A504-NEWS-LOAD-PIPELINE.md` 에 있다. 요약하면 이렇다.

**쿼리를 주 단위 창으로 묶는다.** 수집기는 기업 하나씩 · 요청 간격 5초 하한이라
**쿼리 수가 곧 시간**이다. 지금처럼 `기업 × 하루` 로 일주일치를 받으면
2,703 × 7 = 18,921요청(26시간)이라 못 쓴다. 기업당 한 번으로 묶으면 2,703요청
(약 3.8시간)이다. 기업당 최신 5건만 시드에 남기므로 응답 100건 상한에 닿아도
손해가 아니다 — 하루 단위로 받아도 15%는 이미 상한에 닿는다.

**받은 것은 버리지 않는다.** 같은 `--out` 으로 다시 돌리면 성공한 XML(해시 일치)은
다시 요청하지 않는다. 중간에 끊겨도 이어서 돌릴 수 있다.

**막히면 즉시 멈춘다.** 403·429 같은 4xx 는 구글이 우리를 막기 시작했다는 신호라,
그때까지 받은 것을 남기고 끝낸다(종료 코드 2). 5xx·통신 오류는 수집기가 두 번
재시도하고, 그래도 안 되면 그 요청만 실패로 적고 넘어간다. 실패가 허용 비율을
넘으면 종료 코드 3 이다 — **반쪽짜리 수집이 시드로 넘어가지 않게 한다.**

    python scripts/collect_news.py --start 2026-09-14 --end 2026-09-21 --out ~/newsdata/raw/run1
    python scripts/collect_news.py --start ... --end ... --out ... --companies 20   # 시험
    python scripts/collect_news.py --start ... --end ... --out ... --window daily   # 옛 방식 대조용

다음 단계는 `import_news_raw.py --from <out>` 이다. 이 스크립트의 출력(XML +
requests.json)이 그 입력 규격이라, 수집기가 내던 것과 같은 모양으로 쓴다.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))              # news_poc 는 자기를 data.news_poc 로 부른다
sys.path.insert(0, str(ROOT / "data"))

# 콘솔이 cp949 면 출력의 화살표·기호에서 죽는다. 형제 스크립트들과 같은 처리다.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

from data.news_poc.pipeline.collect import AGENT, fetch, save_json  # noqa: E402
from data.news_poc.pipeline.collect import build_plan as build_daily_plan  # noqa: E402
from data.news_poc.pipeline.normalize import parse_feed  # noqa: E402
from pipeline.news import corpmap  # noqa: E402
from pipeline.paths import CONFIG  # noqa: E402
from pipeline.universe import is_excluded  # noqa: E402

# 정규 시장 상장사만 받는다. corp_cls=E 1,227개사는 다른 표가 아무도 참조하지 않는다
# (`build_curated_seed.build_company` 와 같은 경계다).
LISTED_CLS = frozenset(("Y", "K", "N"))

DEFAULT_INTERVAL = 5.0          # 수집기가 정한 하한. 더 짧게 두지 않는다
DEFAULT_MAX_FAIL_RATIO = 0.05   # 이보다 많이 실패하면 시드 단계로 넘기지 않는다
PROGRESS_EVERY = 50
SATURATION = 100                # 응답 100건은 '더 있을 수 있다' 는 관측 기준이다


def company_names(universe: Path | None = None, *, aliases: bool = True) -> list[str]:
    """검색어로 쓸 회사 이름. 마스터 이름과, 사람이 확인한 별칭을 함께 돌린다.

    이름은 `config/company_universe.csv` 에서 온다 — **매핑이 그 파일을 색인하므로
    같은 이름으로 물어야 corp_code 가 붙는다** (`pipeline/news/corpmap.py`).
    별칭은 언론 표기가 마스터와 다른 경우라, 빼면 그 기업 기사가 통째로 안 붙는다
    (100개사에서 2건이었다).
    """
    target = universe or (CONFIG / "company_universe.csv")
    names: list[str] = []
    seen: set[str] = set()
    with target.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if (row.get("corp_cls") or "").strip() not in LISTED_CLS:
                continue
            # 스팩은 묻지 않는다 — 사업이 없다 (pipeline/universe.py 주석).
            # 매핑(corpmap)도 같은 규칙으로 거르므로 검색어와 색인이 어긋나지 않는다.
            if is_excluded(row.get("corp_name") or ""):
                continue
            name = (row.get("corp_name") or "").strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    if aliases:
        for alias in corpmap.load_aliases():
            alias = alias.strip()
            if alias and alias not in seen:
                seen.add(alias)
                names.append(alias)
    return names


def weekly_spec(name: str, start: date, end: date) -> dict:
    """기업 하나를 [start, end) 한 번에 묻는 요청. 수집기의 계획 형식 그대로다.

    창 규칙도 수집기와 같다 — `after:D-1 before:D` 가 KST 하루 D 라서, 묶을 때도
    **시작 하루 전부터** 건다. 경계 흔들림을 흡수하는 보완 구간이고, 뒤의
    staged 단계가 [start, end) 로 다시 거른다.
    """
    begin = start - timedelta(days=1)
    query = f"{name} after:{begin.isoformat()} before:{end.isoformat()}"
    return dict(
        id=hashlib.sha256(query.encode()).hexdigest()[:20],
        query=query,
        start=begin.isoformat(),
        end=end.isoformat(),
        kind="weekly",
        url="https://news.google.com/rss/search?"
            + urlencode(dict(q=query, hl="ko", gl="KR", ceid="KR:ko")),
    )


def build_plan(names: list[str], start: date, end: date, *,
               window: str = "weekly") -> list[dict]:
    """기업마다 요청 하나(weekly) 또는 하루씩(daily, 옛 방식)."""
    if start >= end:
        raise ValueError("start 가 end 보다 앞이어야 한다")
    if window not in ("weekly", "daily"):
        raise ValueError("window 는 weekly 또는 daily 다")
    plan: list[dict] = []
    for name in names:
        if window == "daily":
            plan.extend(build_daily_plan(start, end, name))
        else:
            plan.append(weekly_spec(name, start, end))
    return plan


def _cached(spec: dict, out: Path, records: dict) -> bool:
    """이미 성공한 요청인가. 해시까지 같아야 건너뛴다 (수집기와 같은 규칙)."""
    path = out / (spec["id"] + ".xml")
    previous = records.get(spec["id"], {})
    if not (path.exists() and previous.get("status") == "ok"):
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == previous.get("sha256")


def run(plan: list[dict], out: Path, *, interval: float = DEFAULT_INTERVAL,
        fetch_fn=fetch, sleep_fn=time.sleep, clock=time.monotonic,
        progress_every: int = PROGRESS_EVERY, log=print) -> dict:
    """계획을 돌며 받는다.

    `requests.json` 을 **매 건 갱신**한다. 3.8시간짜리가 중간에 끊겨도 그때까지가
    남고, 같은 `--out` 으로 다시 돌리면 남은 것만 받는다.
    """
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / "requests.json"
    records: dict = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}

    started = clock()
    counts = {"ok": 0, "cached": 0, "error": 0, "saturated": 0}
    requested = False
    blocked_at: str | None = None

    for index, spec in enumerate(plan, 1):
        if _cached(spec, out, records):
            counts["cached"] += 1
            continue
        if requested:                      # 첫 요청 앞에서는 기다리지 않는다
            sleep_fn(interval)
        requested = True

        record = dict(spec, checked_at=datetime.now(timezone.utc).isoformat(), user_agent=AGENT)
        try:
            payload, status, final_url = fetch_fn(spec["url"])
            rows = parse_feed(payload)
            path = out / (spec["id"] + ".xml")
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(payload)
            temporary.replace(path)        # 반쪽 파일을 남기지 않는다
            record.update(status="ok", http_status=status, final_url=final_url,
                          count=len(rows), bytes=len(payload),
                          sha256=hashlib.sha256(payload).hexdigest())
            counts["ok"] += 1
            if len(rows) >= SATURATION:
                counts["saturated"] += 1
        except Exception as error:         # noqa: BLE001 — 사유를 적고 계속할지 판단한다
            record.update(status="error", error=str(error))
            if isinstance(error, HTTPError):
                record["http_status"] = error.code
            counts["error"] += 1
            records[spec["id"]] = record
            save_json(manifest, records)
            if isinstance(error, HTTPError) and error.code < 500:
                blocked_at = spec["query"]
                log(f"  X {error.code} — 막혔다. 여기서 멈춘다: {spec['query']}")
                break
            log(f"  ! 실패(계속): {spec['query']} — {error}")
            continue

        records[spec["id"]] = record
        save_json(manifest, records)

        if progress_every and index % progress_every == 0:
            left = len(plan) - index
            log(f"  [{index}/{len(plan)}] {index / len(plan):.0%} · "
                f"받음 {counts['ok']:,} · 실패 {counts['error']} · "
                f"남은 시간 약 {left * interval / 3600:.1f}시간")

    attempted = counts["ok"] + counts["error"]
    summary = dict(
        plan=len(plan), attempted=attempted, **counts,
        fail_ratio=(counts["error"] / attempted) if attempted else 0.0,
        blocked_at=blocked_at,
        elapsed_sec=round(clock() - started, 1),
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    save_json(out / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=date.fromisoformat, required=True, help="KST 시작일")
    parser.add_argument("--end", type=date.fromisoformat, required=True,
                        help="KST 종료일, exclusive")
    parser.add_argument("--out", type=Path, required=True, help="XML·requests.json 을 둘 폴더")
    parser.add_argument("--window", choices=("weekly", "daily"), default="weekly",
                        help="weekly 는 기업당 1요청 (기본) · daily 는 하루씩 — 전 종목이면 26시간이다")
    parser.add_argument("--companies", type=int, default=0, metavar="N",
                        help="앞 N개사만 (0 이면 전부). 시험용이다")
    parser.add_argument("--only", nargs="+", metavar="이름", help="이 회사만 받는다")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                        help=f"요청 간격 초 (하한 {DEFAULT_INTERVAL:g})")
    parser.add_argument("--max-fail-ratio", type=float, default=DEFAULT_MAX_FAIL_RATIO,
                        metavar="비율", help="이보다 많이 실패하면 종료 코드 3")
    parser.add_argument("--no-aliases", action="store_true", help="별칭 이름은 받지 않는다")
    parser.add_argument("--dry-run", action="store_true", help="계획만 찍고 받지 않는다")
    args = parser.parse_args()
    if args.interval < DEFAULT_INTERVAL:
        parser.error(f"--interval 은 {DEFAULT_INTERVAL:g} 이상이어야 한다 (수집기 하한)")

    names = args.only or company_names(aliases=not args.no_aliases)
    if args.companies:
        names = names[:args.companies]
    try:
        plan = build_plan(names, args.start, args.end, window=args.window)
    except ValueError as error:
        parser.error(str(error))

    print(f"기업 {len(names):,} · 요청 {len(plan):,} · 창 {args.start}~{args.end} ({args.window})")
    print(f"예상 시간 약 {len(plan) * args.interval / 3600:.1f}시간 (간격 {args.interval:g}초)")
    if args.dry_run:
        for spec in plan[:3]:
            print(f"  {spec['query']}")
        print(f"  … 총 {len(plan):,}건. --dry-run 이라 받지 않았다")
        return 0

    summary = run(plan, args.out, interval=args.interval)
    print(f"\n받음 {summary['ok']:,} · 건너뜀(이미 있음) {summary['cached']:,} · "
          f"실패 {summary['error']:,} · 100건 관측 {summary['saturated']:,}")
    print(f"걸린 시간 {summary['elapsed_sec'] / 3600:.2f}시간 → {args.out}")

    if summary["blocked_at"]:
        print("\n4xx 로 멈췄다. 간격을 늘리거나 시간을 바꿔 다시 돌린다 — 받은 것은 남아 있다.")
        return 2
    if summary["fail_ratio"] > args.max_fail_ratio:
        print(f"\n실패 비율 {summary['fail_ratio']:.1%} > 허용 {args.max_fail_ratio:.1%}. "
              "시드 단계로 넘기지 않는다 — 같은 --out 으로 다시 돌리면 실패분만 받는다.")
        return 3
    print(f"\n다음: python scripts/import_news_raw.py --from {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
