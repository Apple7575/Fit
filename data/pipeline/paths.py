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
