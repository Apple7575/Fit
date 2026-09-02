"""DART 수집·정규화 파이프라인 정식 코드.

계층은 DESIGN.md 6장을 따른다.
  수집(dart_client)  API 호출 + 원본 캐시. 해석하지 않는다
  정규화             원본 → 기업-연도 1행. 계정 매칭·집계·교차검증
  적재               PostgreSQL upsert
"""
