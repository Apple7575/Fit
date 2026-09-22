"""staged → curated. `news_article` 에 바로 적재할 시드 CSV 를 만든다.

규칙 (data/docs/DATA_STORAGE_STANDARD.md 6장)

- DB 테이블 하나당 CSV 하나. 파일명은 `<table_name>.csv`
- 헤더는 Flyway 의 실제 컬럼명과 일치. identity 컬럼(`id`)은 넣지 않는다
- BOM 없는 UTF-8, LF
- 같은 입력이면 같은 정렬·같은 바이트
- corp_code 가 없는 행은 넣지 않는다 (FK 위반). 버리는 대신 사유와 함께 세어 보고한다
- 길이·범위 위반은 잘라서 통과시키지 않는다. 위반으로 보고하고 그 행을 뺀다

`news_article.source` 가 provider 인지 publisher 인지는 백엔드와 합의가 필요하다.
기본값은 publisher 다 — provider 는 staged·manifest 에 상수로 남아 있어 잃을 것이
없는데 publisher 는 현재 스키마에 다른 자리가 없다. `--source-column provider` 로 바꾼다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from pipeline.news import flyway
from pipeline.news.csvio import read_csv, write_csv
from pipeline.news.schema import (
    PROVIDER, SEED_COLUMN_FILL, SEED_FIELDS, SEED_IDENTITY_COLUMNS, SEED_SCHEMA_VERSION,
    SEED_SOURCE_DEFAULT, SEED_TABLE,
)

SEED_DIR = Path(__file__).resolve().parents[2] / "curated" / "seed"
SEED_MANIFEST_DIR = Path(__file__).resolve().parents[2] / "manifests" / "seed"
BLOCKLIST_PATH = Path(__file__).resolve().parents[2] / "config" / "news_source_blocklist.yaml"


def load_blocklist(path: Path | None = None) -> frozenset[str]:
    """뺄 출처 이름. 판단 근거는 YAML 에 함께 적혀 있다.

    회사 이름이 제목에 들어갔다는 이유로 도박·게임 홍보 글이 검색에 걸린다.
    출처 단위로 막는 것이라 근거 없이 넣지 않는다 — 조건과 반례는 YAML 머리말에
    적어 두었다. 파일이 없으면 아무것도 막지 않는다(비어 있는 것이 기본값이다).
    """
    target = path or BLOCKLIST_PATH
    if not target.exists():
        return frozenset()
    import yaml

    doc = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    return frozenset(
        (entry.get("name") or "").strip().casefold()
        for entry in (doc.get("publishers") or [])
        if (entry.get("name") or "").strip()
    )

# AI 분석은 아직 실행하지 않는다(S15P21A504-74 PoC). 채우지 않고 NULL 로 둔다 —
# 0 이나 빈 문자열로 채우면 "분석했으나 결과가 없음" 과 구분이 사라진다.
#
# V16 이 news_category · related_business · analyzed_at 을 지워 하나만 남았다.
AI_COLUMNS = ("importance_score",)


@dataclass
class CurateResult:
    rows: list[dict] = field(default_factory=list)
    dropped: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def _limits(schema: flyway.Schema) -> dict[str, int]:
    """VARCHAR(n) 컬럼의 n. 길이 검사를 Flyway 값으로 하기 위한 것이다."""
    table = schema.table(SEED_TABLE)
    if table is None:
        raise ValueError(f"Flyway 에 {SEED_TABLE} 테이블이 없다")
    out = {}
    for column in table.ordered():
        if column.data_type.startswith("VARCHAR("):
            out[column.name] = int(column.data_type[len("VARCHAR("):-1])
    return out


def seed_header(schema: flyway.Schema) -> list[str]:
    """Flyway 컬럼 순서에서 identity 를 뺀 헤더. **이것이 시드 헤더의 정본이다.**

    `SEED_FIELDS` 는 지금 스키마를 적어 둔 사본이라 낡을 수 있다 (뉴스 ERD 마이그레이션이 들어오면
    그렇게 된다). 낡았다는 사실은 verify 9번이 알려 준다.
    """
    table = schema.table(SEED_TABLE)
    return [c.name for c in table.ordered() if c.name not in SEED_IDENTITY_COLUMNS]


def build(staged_rows: list[dict], schema: flyway.Schema | None = None,
          source_column: str = SEED_SOURCE_DEFAULT,
          collected_at_fallback: str = "",
          per_company: int = 0) -> CurateResult:
    """staged 행에서 시드 행을 만든다. 값을 추정하거나 보정하지 않는다.

    `per_company` 가 0 보다 크면 기업마다 **최신 N 건만** 남긴다 (팀장 지시:
    기업별 5개). 잘라내는 것은 유효성 검사를 **통과한 뒤**다 — 먼저 5건을 고르고
    나서 그중 셋이 결함으로 빠지면 2건만 남는다. 뺀 행은 지우지 않고 사유와 함께
    `dropped` 에 남겨 무엇이 왜 빠졌는지 셀 수 있게 한다.
    """
    resolved = schema or flyway.load()
    # 헤더는 **스키마에서 받는다.** 상수에 맞추라고 요구하면 컬럼이 바뀌는 날
    # (MR !209) 시드가 통째로 멈춘다. 대신 "채울 줄 모르는 컬럼" 만 막는다.
    header = seed_header(resolved)
    unknown = [c for c in header if c not in SEED_COLUMN_FILL]
    if unknown:
        raise ValueError(
            f"시드에 어떻게 채울지 모르는 컬럼이 있다: {unknown}. "
            "pipeline/news/schema.py 의 SEED_COLUMN_FILL 에 적고 값을 넣어라")
    limits = _limits(resolved)

    result = CurateResult()
    blocked = load_blocklist()
    seen_url: dict[tuple[str, str], str] = {}
    for row in staged_rows:
        if row.get("is_duplicate") == "true":
            result.dropped.append(dict(row, drop_reason="staged_duplicate"))
            continue
        # 기업별 상한보다 **먼저** 뺀다. 나중에 빼면 스팸이 그 회사의 다섯 자리를
        # 차지하고 들어와, 걸러낸 만큼 기사가 비는 대신 자리만 날린다.
        publisher = (row.get("publisher") or "").strip()
        if publisher.casefold() in blocked:
            result.dropped.append(dict(row, drop_reason=f"blocked_source:{publisher}"))
            continue
        if row.get("stage_status") not in ("staged", "unresolved_corp"):
            result.dropped.append(dict(row, drop_reason=f"stage_status:{row.get('stage_status')}"))
            continue
        if not row.get("corp_code"):
            result.dropped.append(dict(
                row, drop_reason="corp_code_unresolved:" + (row.get("corp_map_reason") or "")))
            continue
        title = row.get("title") or ""
        if not title:
            result.dropped.append(dict(row, drop_reason="title_null_violates_not_null"))
            continue
        collected_at = row.get("collected_at") or collected_at_fallback
        if not collected_at:
            result.dropped.append(dict(row, drop_reason="collected_at_missing_violates_not_null"))
            continue

        # 언론사 원문 주소가 있으면 그것을 쓰고, 없으면 **구글 뉴스 링크**를 쓴다
        # (팀장 판단 2026-09-15). RSS 는 언론사 주소를 주지 않고 구글 자기 주소만
        # 준다 — 그 링크도 클릭하면 기사로 가므로 화면에서는 차이가 없다.
        # 원문 주소를 얻으려면 링크를 하나씩 열어봐야 하는데, 100개사에 486번이고
        # 전 종목이면 수만 번이라 차단 위험이 크다.
        #
        # **열 이름이 original_url 이지만 언론사 주소가 아닐 수 있다.** 어느 쪽인지는
        # staged 의 original_url_status 가 들고 있고, manifest 에 건수를 남긴다.
        original_url = (row.get("original_url") or "").strip()
        url_is_publisher = bool(original_url)
        if not original_url:
            original_url = (row.get("rss_link") or row.get("google_url") or "").strip()
        # V12 의 부분 UNIQUE 인덱스 company_news_url_uk 와 같은 조건이다 —
        # (corp_code, original_url) WHERE original_url IS NOT NULL.
        #
        # **V13 이 news_article 을 만들면서 이 인덱스를 다시 만들지 않았다.** 그래서
        # 지금은 DB 가 중복을 막지 않고 이 판정이 유일한 방어다. 복원을 요청해 두었다
        # (docs/S15P21A504-v13-followup.md 2장). 복원되든 안 되든 여기는 그대로 둔다 —
        # 시드 단계에서 걸러야 적재가 실패하지 않는다.
        if original_url:
            key = (row["corp_code"], original_url)
            if key in seen_url:
                result.dropped.append(dict(row, drop_reason="duplicate_corp_url"))
                continue
            seen_url[key] = row["article_key"]

        # 값은 **이름으로** 채우고 헤더에 있는 것만 내보낸다. 스키마가 바뀌어도
        # (MR !209 가 source·guid 를 publisher·provider_article_id 로 옮긴다) 같은
        # 코드가 양쪽을 만든다.
        provider_url = (row.get("rss_link") or row.get("google_url") or "").strip()
        values = {
            "corp_code": row["corp_code"],
            "title": title,
            "published_at": row.get("published_at") or "",
            "original_url": original_url,
            "source": row.get("publisher", "") if source_column == "publisher" else PROVIDER,
            "collected_at": collected_at,
            # V17 이 더한 중복 방지 키. staged 가 RSS item/guid 를 그대로 들고 있어
            # 옮기기만 하면 된다. 없으면 빈 칸(NULL)이고 NULL 끼리는 충돌하지 않는다.
            "guid": row.get("guid") or "",
            # ── 뉴스 ERD 마이그레이션 이후의 자리들 (지금 스키마에는 없어 헤더에서 걸러진다)
            "provider": PROVIDER,
            "provider_url": provider_url,
            "provider_article_id": row.get("guid") or "",
            "publisher": row.get("publisher", ""),
            # 구글 링크를 원문 주소로 푸는 세 방법이 모두 실패했다 (2026-09-21 실측).
            # 못 채우는 값을 지어내지 않는다.
            "normalized_url": "",
            # 본문은 저장 근거가 없다 (news-poc/90-source-review.md).
            "body_text": "",
        }
        for column in AI_COLUMNS:
            values[column] = ""
        seed = {c: values.get(c, "") for c in header}

        violations = [
            f"{name}_exceeds_{limit}" for name, limit in limits.items()
            if len(seed.get(name) or "") > limit
        ]
        if violations:
            result.dropped.append(dict(row, drop_reason="length:" + ",".join(violations)))
            continue

        seed["_article_key"] = row["article_key"]
        seed["_url_is_publisher"] = url_is_publisher
        result.rows.append(seed)

    # 재실행 결정성. article_key 를 마지막 축으로 두어 동순위가 없다.
    result.rows.sort(key=lambda r: (r["corp_code"], r["published_at"], r["_article_key"]))

    if per_company > 0:
        # 오름차순 정렬이라 뒤쪽이 최신이다. 같은 시각이면 article_key 가 갈라주므로
        # 같은 입력에는 늘 같은 N 건이 남는다.
        kept: list[dict] = []
        group: list[dict] = []
        current = None
        for row in result.rows + [None]:
            corp = row["corp_code"] if row else None
            if corp != current and group:
                kept.extend(group[-per_company:])
                for cut in group[:-per_company]:
                    result.dropped.append(dict(cut, drop_reason=f"per_company_limit:{per_company}"))
                group = []
            current = corp
            if row:
                group.append(row)
        result.rows = kept

    result.summary = {
        "table": SEED_TABLE,
        "seed_schema_version": SEED_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "header": header,
        "identity_columns_excluded": SEED_IDENTITY_COLUMNS,
        "source_column_maps_to": source_column,
        "flyway_files": resolved.applied_files,
        "input_staged_rows": len(staged_rows),
        "per_company_limit": per_company or None,
        "seed_rows": len(result.rows),
        "dropped_rows": len(result.dropped),
        "drop_reasons": _count(result.dropped, "drop_reason"),
        "distinct_corp_codes": len({r["corp_code"] for r in result.rows}),
        "published_at_null_rows": sum(1 for r in result.rows if not r["published_at"]),
        "original_url_null_rows": sum(1 for r in result.rows if not r["original_url"]),
        # 열 이름은 original_url 이지만 값이 언론사 주소인지 구글 뉴스 링크인지
        # 나뉜다. 화면·후속 작업이 알아야 하므로 건수를 남긴다.
        "url_publisher_rows": sum(1 for r in result.rows if r.get("_url_is_publisher")),
        "url_google_news_rows": sum(1 for r in result.rows
                                    if r["original_url"] and not r.get("_url_is_publisher")),
        "ai_columns_null": list(AI_COLUMNS),
        "collection_run_ids": sorted({r.get("collection_run_id", "") for r in staged_rows if r.get("collection_run_id")}),
    }
    return result


def _count(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.get(key) or "(none)"] = counts.get(row.get(key) or "(none)", 0) + 1
    return dict(sorted(counts.items()))


def write(result: CurateResult, seed_dir: Path | None = None) -> dict[str, Path]:
    directory = seed_dir or SEED_DIR
    seed_path = directory / f"{SEED_TABLE}.csv"
    # 헤더는 build() 가 스키마에서 정한 것을 쓴다 — 상수를 다시 보면 컬럼이
    # 바뀌는 날 CSV 와 계보가 서로 다른 헤더를 말하게 된다.
    write_csv(seed_path, result.summary.get("header") or SEED_FIELDS, result.rows)

    # seed_dir 을 직접 준 경우(테스트)에는 manifest 도 그 트리 안에 둔다.
    manifest_dir = SEED_MANIFEST_DIR if seed_dir is None else directory.parents[1] / "manifests" / "seed"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"{SEED_TABLE}.json"
    summary = dict(result.summary, seed_csv_path=seed_path.relative_to(directory.parents[1]).as_posix())
    manifest_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rejects_path = directory.parents[1] / "staged" / PROVIDER / "seed_dropped.csv"
    fields = sorted({k for row in result.dropped for k in row}) if result.dropped else ["drop_reason"]
    write_csv(rejects_path, fields, result.dropped)
    return {"seed": seed_path, "manifest": manifest_path, "dropped": rejects_path}


def load_staged(staged_dir: Path) -> list[dict]:
    """staged 폴더들의 articles.csv 를 모아 읽는다. 폴더명 순서로 결정적이다."""
    rows: list[dict] = []
    for path in sorted(staged_dir.glob("*/articles.csv")):
        rows.extend(read_csv(path))
    return rows
