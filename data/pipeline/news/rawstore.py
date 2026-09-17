"""raw 계층 읽기. 원본을 고치거나 옮기지 않는다.

레이아웃 (data/docs/DATA_STORAGE_STANDARD.md 4장)

    data/raw/google_news_rss/articles/<collection_run_id>/
        <plan_id>.xml     RSS 응답 원본 바이트 그대로
        requests.json     요청 URL·시각·HTTP 상태·SHA-256 (수집기가 쓴 것)

`requests.json` 은 수집기(`collect.py`)가 `--out` 폴더에 남기는 파일이다. 이 계층은
그 폴더를 그대로 raw 로 인정하고, 파싱은 수집기의 파서를 재사용한다 — 파서를
복사해 두면 RSS 해석 규칙이 두 곳으로 갈라진다.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pipeline.news.schema import PROVIDER

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "raw" / PROVIDER / "articles"

# 수집 실행 ID. 회사명을 식별자로 쓰지 않는다 — 한 실행이 여러 기업을 다룰 수 있고,
# 회사명이 경로에 박히면 같은 기업을 재조회할 때 폴더가 겹친다.
RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")


def relative(path: Path) -> str:
    """data/ 기준 상대 경로. 밖의 경로(테스트 임시 폴더)는 그대로 문자열로 남긴다."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def mint_run_id(now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(4)}"


@dataclass
class RawFile:
    path: Path
    plan_id: str
    bytes: int
    sha256: str
    request: dict          # requests.json 의 해당 항목. 없으면 빈 dict

    @property
    def relative(self) -> str:
        return relative(self.path)

    @property
    def checksum_matches(self) -> bool | None:
        """수집기가 기록한 해시와 지금 파일의 해시가 같은가. 기록이 없으면 None."""
        recorded = self.request.get("sha256")
        return None if not recorded else recorded == self.sha256


@dataclass
class RawRun:
    run_id: str
    directory: Path
    files: list[RawFile]
    requests: dict[str, dict]

    @property
    def run_id_conforms(self) -> bool:
        return bool(RUN_ID_RE.match(self.run_id))

    @property
    def failed_requests(self) -> list[dict]:
        return [r for r in self.requests.values() if r.get("status") != "ok"]

    def collected_range(self) -> tuple[str, str]:
        stamps = sorted(r["checked_at"] for r in self.requests.values() if r.get("checked_at"))
        return (stamps[0], stamps[-1]) if stamps else ("", "")

    def target_range(self) -> tuple[str, str]:
        """요청 계획의 KST 대상 구간. end 는 exclusive 다 (수집기 규약)."""
        starts = sorted(r["start"] for r in self.requests.values() if r.get("start"))
        ends = sorted(r["end"] for r in self.requests.values() if r.get("end"))
        return (starts[0] if starts else "", ends[-1] if ends else "")

    def queries(self) -> list[str]:
        return sorted({r["query"] for r in self.requests.values() if r.get("query")})


def run_dir(run_id: str) -> Path:
    return RAW_DIR / run_id


def load_run(run_id: str, raw_dir: Path | None = None) -> RawRun:
    """원본 폴더 하나를 읽는다. XML 이 없으면 예외를 던진다 — 표본을 만들지 않는다."""
    directory = (raw_dir or RAW_DIR) / run_id
    if not directory.is_dir():
        raise FileNotFoundError(f"원본 폴더가 없다: {directory}")
    manifest_path = directory / "requests.json"
    requests = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    files = []
    for path in sorted(directory.glob("*.xml")):
        payload = path.read_bytes()
        files.append(RawFile(
            path=path, plan_id=path.stem, bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            request=requests.get(path.stem, {}),
        ))
    if not files:
        raise ValueError(f"RSS XML 이 없다: {directory} — 표본 데이터를 만들지 않는다")
    return RawRun(run_id=run_id, directory=directory, files=files, requests=requests)


def list_runs(raw_dir: Path | None = None) -> list[str]:
    directory = raw_dir or RAW_DIR
    if not directory.is_dir():
        return []
    return sorted(p.name for p in directory.iterdir() if p.is_dir() and any(p.glob("*.xml")))


def load_parser():
    """수집기의 RSS 파서를 가져온다.

    `refactor/news-data` 가 `data/news_poc` 를 `data/news` 로 옮기는 중이므로 두 이름을
    모두 시도한다. 어느 쪽도 없으면 여기서 멈춘다 — 파서를 복제하지 않는다.
    """
    import sys

    repo_root = str(ROOT.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    errors = []
    for module_name in ("data.news.pipeline.normalize", "data.news_poc.pipeline.normalize"):
        try:
            module = __import__(module_name, fromlist=["parse_feed"])
            return module
        except ImportError as error:      # noqa: PERF203 — 두 경로 중 하나만 존재한다
            errors.append(f"{module_name}: {error}")
    raise ImportError("수집기 RSS 파서를 찾을 수 없다.\n  " + "\n  ".join(errors))
