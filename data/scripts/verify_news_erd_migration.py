"""뉴스 ERD 마이그레이션(MR !209) 배포 전후 대조.

백엔드가 2026-09-22 리뷰에서 부탁한 확인 6항목을 기계로 돌린다.

    python scripts/verify_news_erd_migration.py --snapshot _out/news_before.json   # 배포 전
    python scripts/verify_news_erd_migration.py --compare  _out/news_before.json   # 배포 후

**배포 전에 먼저 찍어야 한다.** `source`·`guid` 는 마이그레이션이 지우므로, 그 값이
어디로 갔는지는 지운 뒤에 DB 만 봐서는 알 수 없다. 스냅샷은 행마다 id → source·guid
를 그대로 들고 있다가, 배포 뒤에 publisher·provider_article_id 와 한 행씩 맞춰 본다.

검사 항목

  [1] 전체 행 수가 같다
  [2] source 가 있던 행은 모두 publisher 로 옮겨졌다 (행 단위 대조)
  [3] guid 가 있던 행은 모두 provider_article_id 로 옮겨졌다 (행 단위 대조)
  [4] 새 자연키에 중복이 없다 (제공처 기준 · 원문 URL 기준 둘 다)
  [5] 기존 Google 뉴스 행의 provider_url 이 original_url 과 **값까지** 같다
  [6] normalized_url 에 빈 문자열이 없다 — 부분 UNIQUE 인덱스가 빈 문자열을 값으로
      보아 같은 기업의 두 번째 행부터 충돌한다 (백엔드 지적)
  [7] AI 코드가 더 이상 source·guid 를 조회하지 않는다 (DB 없이 코드로 본다)
  [8] provider 가 모든 행에 채워졌다 — 비면 제공처 기준 자연키가 성립하지 않는다
  [9] id 집합이 보존됐다 — 행 수가 같아도 지워지고 새로 들어갔을 수 있다

[7] 만 DB 없이 돈다. `--code-only` 로 그것만 볼 수 있다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.db import connect  # noqa: E402

DATA = Path(__file__).resolve().parents[1]
AI_DIR = DATA.parent / "ai" / "news_intelligence"
GOOGLE_PREFIX = "https://news.google.com/"

# SQL 문장 안에서 컬럼으로 읽히는 자리만 본다. 파이썬 지역변수 이름이 source 인 것은
# 무관하다 (ai/news_intelligence/chat.py 가 그렇게 쓴다).
_SELECT_LINE = re.compile(r"SELECT\b.*\b(source|guid)\b", re.IGNORECASE)
_ROW_ACCESS = re.compile(r"""row\[["'](source|guid)["']\]""")


class Check:
    def __init__(self, number: int, name: str):
        self.number = number
        self.name = name
        self.status = "pass"
        self.problems: list[str] = []
        self.detail: dict = {}

    def fail(self, problem: str) -> None:
        self.status = "fail"
        self.problems.append(problem)

    def skip(self, reason: str) -> None:
        self.status = "skip"
        self.detail["reason"] = reason

    @property
    def line(self) -> str:
        mark = {"pass": "✔", "fail": "✖", "skip": "·"}[self.status]
        return f"  {mark} [{self.number}] {self.name}"


def _columns(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'news_article'")
        return {row[0] for row in cur.fetchall()}


def _database_id(conn) -> dict:
    """스냅샷을 찍은 DB 를 표시한다.

    `system_identifier` 는 클러스터마다 다른 값이라 **어느 DB 인지 가리는 지문**이
    된다. 접속 정보가 섞이지 않아 파일에 남겨도 안전하다.

    왜 필요한가: dev 와 prod 는 같은 기사 500건을 들고 있지만 `id` 는 서로 다르다
    (identity 를 DB 마다 따로 세기 때문이다 — 2026-09-22 실측). 스냅샷을 엉뚱한 DB
    와 대조하면 "id 집합이 보존됐다" 가 통째로 빨개지고, 사람은 마이그레이션을
    의심하게 된다.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT system_identifier FROM pg_control_system()")
        identifier = str(cur.fetchone()[0])
        cur.execute("SELECT current_database()")
        return {"system_identifier": identifier, "database": cur.fetchone()[0]}


def take_snapshot(path: Path) -> int:
    """배포 전 상태를 적는다. source·guid 를 행 단위로 들고 있는다."""
    with connect() as conn:
        database = _database_id(conn)
        columns = _columns(conn)
        missing = {"source", "guid"} - columns
        if missing:
            print(f"! 배포 전 스냅샷인데 {', '.join(sorted(missing))} 가 이미 없다. "
                  "마이그레이션이 이미 적용된 DB 로 보인다.", file=sys.stderr)
            return 2
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM news_article")
            total = cur.fetchone()[0]
            cur.execute("SELECT id, corp_code, source, guid, original_url "
                        "FROM news_article ORDER BY id")
            rows = [{"id": r[0], "corp_code": r[1], "source": r[2],
                     "guid": r[3], "original_url": r[4]} for r in cur.fetchall()]

    payload = {
        "database": database,
        "total_rows": total,
        "source_not_null": sum(1 for r in rows if r["source"] is not None),
        "guid_not_null": sum(1 for r in rows if r["guid"] is not None),
        "google_original_url": sum(
            1 for r in rows if (r["original_url"] or "").startswith(GOOGLE_PREFIX)),
        "rows": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"배포 전 스냅샷 → {path}")
    print(f"  DB {database['database']} (system_identifier {database['system_identifier']})")
    print(f"  전체 {payload['total_rows']}행 · source 있음 {payload['source_not_null']}"
          f" · guid 있음 {payload['guid_not_null']}"
          f" · original_url 이 구글 링크 {payload['google_original_url']}")
    return 0


def check_ai_code() -> Check:
    check = Check(7, "AI 코드가 source·guid 를 조회하지 않는다")
    if not AI_DIR.exists():
        check.skip(f"{AI_DIR} 가 없다")
        return check
    hits: list[str] = []
    for path in sorted(AI_DIR.glob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _SELECT_LINE.search(line) or _ROW_ACCESS.search(line):
                hits.append(f"{path.name}:{number}: {line.strip()[:90]}")
    check.detail["hits"] = hits
    for hit in hits:
        check.fail(hit)
    return check


def _check_moved(cur, columns, number, name, old, new, by_id) -> Check:
    check = Check(number, name)
    if new not in columns:
        check.fail(f"{new} 컬럼이 없다 — 마이그레이션이 적용되지 않았다")
        return check
    cur.execute(f"SELECT id, {new} FROM news_article ORDER BY id")
    after = dict(cur.fetchall())
    expected = {i: r[old] for i, r in by_id.items() if r[old] is not None}
    mismatched = {i: (v, after.get(i)) for i, v in expected.items() if after.get(i) != v}
    check.detail = {"expected_rows": len(expected), "mismatched": len(mismatched)}
    for i, (want, got) in list(mismatched.items())[:5]:
        check.fail(f"id={i}: {old}={want!r} 였는데 {new}={got!r}")
    if len(mismatched) > 5:
        check.fail(f"… 외 {len(mismatched) - 5}건")
    return check


def _check_duplicate_keys(cur, columns) -> Check:
    check = Check(4, "새 자연키에 중복이 없다")
    pairs = [("제공처 기준", ("corp_code", "provider", "provider_article_id"),
              "provider_article_id"),
             ("원문 URL 기준", ("corp_code", "normalized_url"), "normalized_url")]
    for label, key, not_null in pairs:
        if not set(key) <= columns:
            check.fail(f"{label}: 컬럼이 없다 — 마이그레이션이 적용되지 않았다")
            continue
        cols = ", ".join(key)
        cur.execute(f"SELECT {cols}, count(*) FROM news_article "
                    f"WHERE {not_null} IS NOT NULL "
                    f"GROUP BY {cols} HAVING count(*) > 1")
        duplicated = cur.fetchall()
        check.detail[label] = len(duplicated)
        for row in duplicated[:5]:
            check.fail(f"{label}: {tuple(row[:-1])} 가 {row[-1]}행")
    return check


def _check_provider_url(cur, columns, by_id) -> Check:
    check = Check(5, "기존 Google 뉴스 행의 provider_url 이 original_url 과 같다")
    if "provider_url" not in columns:
        check.fail("provider_url 컬럼이 없다 — 마이그레이션이 적용되지 않았다")
        return check
    google = {i: r["original_url"] for i, r in by_id.items()
              if (r["original_url"] or "").startswith(GOOGLE_PREFIX)}
    if not google:
        check.skip("배포 전에 구글 링크 행이 없었다")
        return check
    cur.execute("SELECT id, provider_url FROM news_article WHERE id = ANY(%s)",
                (list(google),))
    after = dict(cur.fetchall())
    empty = [i for i in google if after.get(i) is None]
    # 채워졌는지만 보면 엉뚱한 값이 들어가도 통과한다. 값까지 맞춘다 (백엔드 요청).
    wrong = {i: (want, after.get(i)) for i, want in google.items()
             if after.get(i) is not None and after.get(i) != want}
    check.detail = {"google_rows": len(google), "still_null": len(empty),
                    "mismatched": len(wrong)}
    if empty:
        check.fail(f"{len(empty)}행이 아직 NULL 이다 (예: id={empty[:5]})")
    for i, (want, got) in list(wrong.items())[:5]:
        check.fail(f"id={i}: original_url={want!r} 인데 provider_url={got!r}")
    if len(wrong) > 5:
        check.fail(f"… 외 {len(wrong) - 5}건")
    return check


def _check_provider_backfill(cur, columns) -> Check:
    check = Check(8, "provider 가 모든 행에 채워졌다")
    if "provider" not in columns:
        check.fail("provider 컬럼이 없다 — 마이그레이션이 적용되지 않았다")
        return check
    cur.execute("SELECT count(*) FROM news_article WHERE provider IS NULL")
    empty = cur.fetchone()[0]
    cur.execute("SELECT provider, count(*) FROM news_article GROUP BY provider "
                "ORDER BY count(*) DESC")
    check.detail = {"null_rows": empty,
                    "by_provider": {row[0]: row[1] for row in cur.fetchall()}}
    if empty:
        # provider 가 비면 제공처 기준 자연키가 성립하지 않는다.
        check.fail(f"{empty}행의 provider 가 NULL 이다")
    return check


def _check_id_set(cur, by_id) -> Check:
    check = Check(9, "id 집합이 보존됐다")
    cur.execute("SELECT id FROM news_article")
    after = {row[0] for row in cur.fetchall()}
    before = set(by_id)
    lost = sorted(before - after)
    added = sorted(after - before)
    check.detail = {"lost": len(lost), "added": len(added)}
    # 행 수가 같아도 지워지고 새로 들어갔을 수 있다. 집합으로 본다 (백엔드 요청).
    if lost:
        check.fail(f"없어진 id {len(lost)}개 (예: {lost[:5]})")
    if added:
        check.fail(f"새로 생긴 id {len(added)}개 (예: {added[:5]})")
    return check


def _check_blank_normalized_url(cur, columns) -> Check:
    check = Check(6, "normalized_url 에 빈 문자열이 없다")
    if "normalized_url" not in columns:
        check.fail("normalized_url 컬럼이 없다 — 마이그레이션이 적용되지 않았다")
        return check
    cur.execute("SELECT count(*) FROM news_article WHERE normalized_url = ''")
    blanks = cur.fetchone()[0]
    check.detail = {"blank_rows": blanks}
    if blanks:
        check.fail(f"{blanks}행이 빈 문자열이다 — 부분 UNIQUE 인덱스가 값으로 본다")
    return check


class WrongDatabase(Exception):
    """스냅샷을 찍은 DB 가 아닌 곳에 대조하려 한다."""


def _guard_same_database(conn, before: dict) -> None:
    """스냅샷과 지금 DB 가 같은지 본다. 다르면 아무 검사도 하지 않고 멈춘다.

    틀린 짝으로 돌리면 `id` 가 통째로 어긋나 **마이그레이션이 망가진 것처럼 보인다.**
    예전 스냅샷(이 칸이 없는 것)은 막지 않는다 — 대신 확인할 수 없다고 말한다.
    """
    recorded = (before.get("database") or {}).get("system_identifier")
    if not recorded:
        print("! 스냅샷에 DB 표시가 없다(예전 형식). 같은 DB 인지 확인할 수 없다.",
              file=sys.stderr)
        return
    now = _database_id(conn)
    if now["system_identifier"] != recorded:
        raise WrongDatabase(
            f"스냅샷은 다른 DB 의 것이다 — 스냅샷 {recorded} vs 지금 "
            f"{now['system_identifier']} ({now['database']}).\n"
            "  dev 와 prod 는 기사가 같아도 id 가 달라서, 짝이 틀리면 결과가 통째로 "
            "어긋난다. 그 DB 에서 찍은 스냅샷으로 다시 돌릴 것.")


def run_compare(snapshot_path: Path) -> list[Check]:
    before = json.loads(snapshot_path.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in before["rows"]}
    checks: list[Check] = []

    with connect() as conn:
        _guard_same_database(conn, before)
        columns = _columns(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM news_article")
            total_now = cur.fetchone()[0]

            first = Check(1, "전체 행 수가 같다")
            first.detail = {"before": before["total_rows"], "after": total_now}
            if total_now != before["total_rows"]:
                first.fail(f"{before['total_rows']} → {total_now}")
            checks.append(first)

            checks.append(_check_moved(
                cur, columns, 2, "source 가 있던 행은 모두 publisher 로 옮겨졌다",
                "source", "publisher", by_id))
            checks.append(_check_moved(
                cur, columns, 3, "guid 가 있던 행은 모두 provider_article_id 로 옮겨졌다",
                "guid", "provider_article_id", by_id))
            checks.append(_check_duplicate_keys(cur, columns))
            checks.append(_check_provider_url(cur, columns, by_id))
            checks.append(_check_blank_normalized_url(cur, columns))
            checks.append(_check_provider_backfill(cur, columns))
            checks.append(_check_id_set(cur, by_id))

    checks.append(check_ai_code())
    return checks


def report(checks: list[Check], json_path: Path | None) -> int:
    checks = sorted(checks, key=lambda c: c.number)
    print("뉴스 ERD 마이그레이션 전후 대조")
    print("=" * 64)
    for check in checks:
        print(check.line)
        if check.status == "skip":
            print(f"        {check.detail.get('reason', '')}")
        for problem in check.problems:
            print(f"        ! {problem}")
    counts = {status: sum(1 for c in checks if c.status == status)
              for status in ("pass", "fail", "skip")}
    print("=" * 64)
    print(f"통과 {counts['pass']} · 실패 {counts['fail']} · 건너뜀 {counts['skip']}"
          f"  (총 {len(checks)})")
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(
            {"summary": counts,
             "checks": [{"number": c.number, "name": c.name, "status": c.status,
                         "problems": c.problems, "detail": c.detail} for c in checks]},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"→ {json_path}")
    return 1 if counts["fail"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--snapshot", type=Path, help="배포 전 상태를 이 파일에 적는다")
    group.add_argument("--compare", type=Path, help="배포 뒤 이 스냅샷과 대조한다")
    group.add_argument("--code-only", action="store_true",
                       help="DB 없이 [7] AI 코드 검사만 한다")
    parser.add_argument("--json", type=Path, help="결과를 JSON 으로도 쓴다")
    args = parser.parse_args()

    if args.snapshot:
        return take_snapshot(args.snapshot)
    if args.code_only:
        return report([check_ai_code()], args.json)
    if not args.compare.exists():
        print(f"! 스냅샷이 없다: {args.compare}\n"
              "  배포 **전에** --snapshot 으로 먼저 찍어야 한다.", file=sys.stderr)
        return 2
    try:
        checks = run_compare(args.compare)
    except WrongDatabase as wrong:
        # 틀린 결과를 내놓느니 아무것도 내놓지 않는다.
        print(f"! {wrong}", file=sys.stderr)
        return 2
    return report(checks, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
