-- 임베딩 벡터를 float16 으로도 저장할 수 있게 한다.
--
-- 벡터가 코퍼스 용량의 71% 를 차지한다(2,640개사 기준 60GB/84GB). 차원당 4바이트를 2바이트로
-- 줄이면 절반이 된다. 저장 전에 단위 벡터로 정규화하므로 값이 -0.18~0.18 범위에 모여 있어
-- float16 의 정밀도로 충분하다 — 실측에서 코사인 유사도 오차는 최대 8.8e-05 였고 상위 8건
-- 검색 결과는 100% 같았다.
--
-- 어느 정밀도로 담겼는지는 embedding_version 이 구분한다(예: document-v1 은 4바이트,
-- document-v1-f16 은 2바이트). 기본키가 (evidence_id, model, version) 이라 두 정밀도가
-- 한 청크에 공존할 수 있고, 옮기는 동안 검색은 예전 버전을 그대로 본다.

ALTER TABLE rag_evidence_embedding
    DROP CONSTRAINT rag_evidence_embedding_size_check;

ALTER TABLE rag_evidence_embedding
    ADD CONSTRAINT rag_evidence_embedding_size_check
    CHECK (octet_length(vector_bytes) IN (dimension * 4, dimension * 2));
