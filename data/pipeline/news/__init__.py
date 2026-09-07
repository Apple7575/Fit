"""뉴스 데이터 표준화 — raw → staged → curated.

수집은 하지 않는다. 수집기는 `data/news_poc/pipeline/collect.py`(리팩터 후
`data/news/pipeline/collect.py`)이고, 이 패키지는 그 원본을 팀 공통 저장 기준에 맞게
정제·적재 후보로 만드는 쪽만 담당한다. 기준은 `data/docs/DATA_STORAGE_STANDARD.md`.
"""
