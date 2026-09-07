"""경로·인증키 해석.

프로토타입의 `_paths.py`를 정식 코드로 옮긴 것. 달라진 점 두 가지.
  - 인증키를 python-dotenv 로 읽는다 (프로토타입은 문자열 split 임시 코드였다)
  - 캐시 파일명을 만드는 규칙을 여기 모은다 (DESIGN.md 6장 raw 레이아웃)

환경변수
  DART_API_KEY    필수. data/.env 또는 프로세스 환경
  DART_CACHE_DIR  선택. 기본값 data/.cache
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# pipeline/ 의 부모 = data/
ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
LOG = ROOT / "_log"

_ENV_LOADED = False


def _load_env() -> None:
    """data/.env 를 1회만 읽는다. 이미 프로세스 환경에 있는 값은 덮어쓰지 않는다."""
    global _ENV_LOADED
    if not _ENV_LOADED:
        load_dotenv(ROOT / ".env", override=False)
        _ENV_LOADED = True


def cache_dir() -> Path:
    """API 응답 원본 캐시. 이게 있으면 API 호출 없이 정규화를 재실행할 수 있다."""
    _load_env()
    p = Path(os.getenv("DART_CACHE_DIR") or (ROOT / ".cache"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def log_dir() -> Path:
    LOG.mkdir(parents=True, exist_ok=True)
    return LOG


def load_key() -> str:
    """DART 인증키. 프로세스 환경 우선, 없으면 data/.env."""
    _load_env()
    key = (os.getenv("DART_API_KEY") or "").strip().strip("\"'")
    if not key:
        raise RuntimeError(
            f"DART_API_KEY 가 없습니다. {ROOT / '.env.example'} 를 .env 로 복사하고 인증키를 넣으세요."
        )
    return key


# ── 저장 기준 경로 (DATA_STORAGE_STANDARD.md 2장) ──────────────────────
# 기존 10개사 경로는 .cache/ 평면 구조를 그대로 쓴다. 아래는 전 종목 수집이
# 새로 쓰는 경로다 — 파일이 1만 개를 넘어가므로 처음부터 기준 위치에 둔다.
RAW = ROOT / "raw"
STAGED = ROOT / "staged"
CURATED = ROOT / "curated"


def raw_api_dir() -> Path:
    """DART 정형 API 응답 원본. 읽기 전용, Git 제외."""
    p = RAW / "opendart" / "api"
    p.mkdir(parents=True, exist_ok=True)
    return p


def staged_dir(source: str = "opendart") -> Path:
    """표준화 결과. raw 에서 재생성 가능하므로 Git 제외."""
    p = STAGED / source
    p.mkdir(parents=True, exist_ok=True)
    return p


def curated_seed_dir() -> Path:
    """DB 적재본 <table_name>.csv. Git 추적."""
    p = CURATED / "seed"
    p.mkdir(parents=True, exist_ok=True)
    return p


def manifest_dir(provider: str = "opendart") -> Path:
    """수집 계보 기록. Git 추적한다 — 원본이 없어도 무엇을 받았는지 남아야 한다."""
    p = ROOT / "manifests" / provider
    p.mkdir(parents=True, exist_ok=True)
    return p


def run_log_dir(provider: str = "opendart") -> Path:
    """실행 로그. _log/ 는 기존 10개사 경로가 쓰므로 건드리지 않는다."""
    p = ROOT / "logs" / provider
    p.mkdir(parents=True, exist_ok=True)
    return p
