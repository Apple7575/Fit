-- 기업 헤더 v2 에 필요한 주소·홈페이지 컬럼을 추가한다 (S15P21A504-97)
--
-- 명세(기업분석 API 명세서 · /api/companies/{corpCode})의 v2 변경은 이렇다.
--   추가: address · homepageUrl · dataYear
--   제거: stockCode · market
--
-- dataYear 는 이미 company_metric 의 최신 연도를 조회 시점에 계산해서 내보내고 있어
-- 컬럼이 필요 없다. 여기서는 앞의 두 개만 만든다.


-- ────────────────────────────────────────────────
-- 주소·홈페이지
-- ────────────────────────────────────────────────
-- 둘 다 DART 기업개황(company.json)이 이미 내려주는 값이라 새 수집 경로가 필요하지 않다.
-- 적재는 DATA 파이프라인 몫이고(S15P21A504-72), 그전까지는 null 로 나간다.
-- 값 없음은 오류가 아니라는 규칙에 따라 화면은 "정보 없음"을 표시한다
-- (docs/decisions/0001-missing-data-response.md).
--
-- 길이는 넉넉히 잡았다. 도로명 주소에 건물명·층수가 붙으면 200자를 넘기는 기업이 있고,
-- 홈페이지도 리다이렉트 경로가 붙은 형태로 오는 경우가 있다.
ALTER TABLE company ADD COLUMN address      VARCHAR(300);
ALTER TABLE company ADD COLUMN homepage_url VARCHAR(300);

COMMENT ON COLUMN company.address      IS 'DART 기업개황 adres. 기업 헤더 응답의 address';
COMMENT ON COLUMN company.homepage_url IS 'DART 기업개황 hm_url. 기업 헤더 응답의 homepageUrl. 스킴이 없는 형태로 오는 경우가 있어 화면에서 그대로 링크를 걸기 전에 확인이 필요하다';


-- ────────────────────────────────────────────────
-- 낡은 주석 정리
-- ────────────────────────────────────────────────
-- corp_cls 주석이 "응답의 market 은 이 값에서 파생한다" 라고 설명하고 있으나
-- v2 에서 market 필드를 응답에서 뺐다. 컬럼과 데이터는 그대로 두되(시장 구분 자체는
-- 여전히 사실이고 다른 화면에서 쓸 수 있다) 설명만 실제에 맞춘다.
COMMENT ON COLUMN company.corp_cls IS 'Y=유가, K=코스닥, N=코넥스, E=기타. v2 기업 헤더 응답에는 나가지 않는다';
