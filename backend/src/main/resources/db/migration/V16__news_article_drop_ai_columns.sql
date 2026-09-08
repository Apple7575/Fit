-- news_article 을 갱신된 확정 ERD 에 맞춘다 (S15P21A504-120).
--
-- ERD 대조
-- --------
-- 확정 ERD 명세서(Notion "기업 정보 ERD", 2026-09-08 갱신본)의 news_article 은
--
--     id · corp_code · title · published_at · original_url · importance_score
--     source · collected_at · guid
--
-- 이다. V13 이 남겨 둔 description · news_category · related_business · analyzed_at
-- 네 컬럼이 ERD 에서 빠졌다. 여기서 그 넷을 지워 코드를 ERD 쪽에 맞춘다.
--
-- V13 은 이 중 셋(source · collected_at · analyzed_at)을 "확정 ERD 에 없지만 남긴다,
-- Notion 에 함께 반영한다" 로 처리했다. 반영 결과 source 와 collected_at 은 ERD 에
-- 편입됐고 analyzed_at 은 편입되지 않았다. 그래서 analyzed_at 만 지운다.
--
-- guid 는 이 마이그레이션에서 만들지 않는다. ERD 가 UNIQUE (corp_code, guid) 를
-- 요구하는데 Google RSS 가 guid 를 늘 주지 않아(data/docs/DATA_STORAGE_STANDARD.md
-- 5장) 수집기가 article_key 로 대체하고 있다. 이름과 유일성 기준을 먼저 정해야 한다.
--
-- 화면 영향 (프론트 담당 확인 완료)
-- ------------------------------
-- 최근 이슈 탭에서 다음이 사라진다 — 뉴스 목록의 요약 문단과 "관련 사업" 줄,
-- 카테고리 칩, 이슈 분포 도넛 카드, KPI 4장 중 투자·기술 이슈 2장, 카테고리 필터.
-- 프론트 매퍼가 없는 필드를 null 로 접으므로 예외는 나지 않고 요소가 빠진다.
--
-- 되돌리기
-- --------
-- 컬럼을 다시 만들어도 값은 돌아오지 않는다. 이 표는 배포 시점에 0 행이므로
-- 지금은 잃을 값이 없다.

ALTER TABLE news_article
    DROP COLUMN description,
    DROP COLUMN news_category,
    DROP COLUMN related_business,
    DROP COLUMN analyzed_at;
