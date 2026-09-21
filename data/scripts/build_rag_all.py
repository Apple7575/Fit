"""전체 기업의 RAG 코퍼스를 청킹·정형표·임베딩까지 한 번에 만든다.

    python data/scripts/build_rag_all.py --dart-archive <폴더> --workers 10

기업 하나가 작업 단위다. 한 기업에 대해 세 단계를 순서대로 돌린다.

    1) build_rag_corpus.py      청크        -> rag_evidence
    2) load_form_table_rows.py  서식 표 행  -> company_table_row
    3) build_rag_embeddings.py  벡터        -> rag_evidence_embedding

순서를 지켜야 한다. 정형 표 행은 같은 좌표의 청크가 있어야 근거 ID 가 붙고(LINKED),
없으면 PENDING_CHUNK 로 남아 리포트가 인용하지 못한다.

**중단해도 된다.** 진행 기록(JSONL)에 성공한 기업이 남고, 다시 실행하면 건너뛴다.
각 단계가 기업 단위로 지우고 다시 넣으므로 중간에 죽어도 반쪽 상태가 남지 않는다.

임베딩 서버는 가끔 죽는다. 3단계만 재시도하고, 그래도 실패하면 그 기업을 failed 로
남기고 다음으로 간다. 나중에 --retry-failed 로 실패분만 다시 돌린다.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

PROFILE = "adaptive-v1"
EMBED_BATCH = 512
EMBED_ATTEMPTS = 3
RETRY_WAIT_S = 30


def companies_from_manifest(archive: Path) -> list[str]:
    """manifest CSV 에서 XML 이 실제로 있는 기업 코드를 읽는다."""
    manifests = [
        path for path in archive.rglob("*.csv")
        if {"corp_code", "rcept_no", "file"} <= set(_header(path))
    ]
    if len(manifests) != 1:
        raise SystemExit(f"manifest CSV 가 1개여야 합니다: {len(manifests)}개")
    with manifests[0].open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    return sorted({
        row["corp_code"].strip() for row in rows
        if (row.get("file") or "").strip() and (row.get("corp_code") or "").strip()
    })


def _header(path: Path) -> list[str]:
    try:
        with path.open(encoding="utf-8-sig") as handle:
            return next(csv.reader(handle), [])
    except (OSError, UnicodeDecodeError, StopIteration):
        return []


class Progress:
    """성공·실패를 JSONL 한 줄씩 남긴다. 파일이 곧 재개 지점이다."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.done: set[str] = set()
        self.failed: set[str] = set()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                code = row.get("corp_code")
                if not code:
                    continue
                if row.get("status") == "success":
                    self.done.add(code)
                    self.failed.discard(code)
                else:
                    self.failed.add(code)

    def write(self, row: dict) -> None:
        with self.lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            code = row["corp_code"]
            if row["status"] == "success":
                self.done.add(code)
                self.failed.discard(code)
            else:
                self.failed.add(code)


def run_step(python: str, script: Path, args: list[str], timeout: int) -> tuple[bool, str]:
    """하위 스크립트를 돌리고 (성공여부, 마지막 줄) 을 돌려준다."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        done = subprocess.run(
            [python, str(script), *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired:
        return False, f"timeout {timeout}s"
    out = (done.stdout or "").strip().splitlines()
    tail = out[-1] if out else (done.stderr or "").strip()[-300:]
    # 하위 스크립트는 JSON 한 줄을 낸다. 종료코드보다 이 status 가 정확하다.
    # partial 은 종료코드 1 로 끝나지만 실패가 아니다 — manifest 에 XML 이 없는
    # 연도(빈 file 칸)를 건너뛴 것뿐이고, 나머지 연도는 정상으로 들어갔다.
    try:
        payload = json.loads(tail)
    except json.JSONDecodeError:
        payload = None
    if payload is not None and "status" in payload:
        return payload["status"] != "failed", tail[-300:]
    if done.returncode != 0:
        return False, tail or f"exit {done.returncode}"
    return True, tail[-300:]


def build_company(corp_code: str, opts: argparse.Namespace, scripts: Path) -> dict:
    python = opts.python
    started = time.monotonic()
    steps: dict[str, str] = {}

    ok, note = run_step(python, scripts / "build_rag_corpus.py", [
        "--dart-archive", str(opts.dart_archive), "--business-report-only",
        "--chunking-profile", PROFILE, "--corp-code", corp_code,
    ], opts.chunk_timeout)
    steps["chunk"] = note
    if not ok:
        return {"corp_code": corp_code, "status": "failed", "stage": "chunk",
                "note": note, "elapsed_s": round(time.monotonic() - started, 1)}

    ok, note = run_step(python, scripts / "load_form_table_rows.py", [
        "--dart-archive", str(opts.dart_archive), "--profile", PROFILE,
        "--corp-code", corp_code, "--workers", "1", "--quiet",
    ], opts.table_timeout)
    steps["tables"] = note
    if not ok:
        return {"corp_code": corp_code, "status": "failed", "stage": "tables",
                "note": note, "elapsed_s": round(time.monotonic() - started, 1)}

    for attempt in range(1, EMBED_ATTEMPTS + 1):
        ok, note = run_step(python, scripts / "build_rag_embeddings.py", [
            "--corp-code", corp_code, "--batch-size", str(EMBED_BATCH),
        ], opts.embed_timeout)
        steps["embed"] = note
        if ok:
            break
        if attempt < EMBED_ATTEMPTS:
            time.sleep(RETRY_WAIT_S)
    if not ok:
        return {"corp_code": corp_code, "status": "failed", "stage": "embed",
                "note": note, "elapsed_s": round(time.monotonic() - started, 1)}

    return {"corp_code": corp_code, "status": "success", "steps": steps,
            "elapsed_s": round(time.monotonic() - started, 1)}


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="전체 기업 RAG 코퍼스 구축")
    parser.add_argument("--dart-archive", type=Path, required=True,
                        help="사업보고서 XML 과 manifest CSV 가 든 폴더 또는 ZIP")
    parser.add_argument("--workers", type=int, default=10,
                        help="동시에 처리할 기업 수 (기본: 10). 임베딩 서버가 병목이다")
    parser.add_argument("--progress", type=Path, default=Path("outputs/rag-build-progress.jsonl"),
                        help="진행 기록 JSONL. 재개 지점이 된다")
    parser.add_argument("--python", default=sys.executable, help="하위 스크립트를 돌릴 python")
    parser.add_argument("--limit", type=int, help="앞에서 N 개사만 (시험용)")
    parser.add_argument("--corp-code", action="append", default=[],
                        help="이 기업만 (여러 번 지정 가능). 일부만 다시 채울 때 쓴다")
    parser.add_argument("--corp-codes-file", type=Path,
                        help="한 줄에 기업 코드 하나. --corp-code 와 합쳐진다")
    parser.add_argument("--retry-failed", action="store_true",
                        help="성공분은 건너뛰고 실패로 남은 기업만 다시 돌린다")
    parser.add_argument("--chunk-timeout", type=int, default=1800)
    parser.add_argument("--table-timeout", type=int, default=1800)
    parser.add_argument("--embed-timeout", type=int, default=3600)
    args = parser.parse_args(argv)
    if args.workers <= 0:
        parser.error("--workers 는 양수여야 합니다")
    return args


def main(argv=None) -> int:
    opts = parse_args(argv)
    scripts = Path(__file__).resolve().parent
    opts.progress.parent.mkdir(parents=True, exist_ok=True)
    progress = Progress(opts.progress)

    todo = companies_from_manifest(opts.dart_archive)
    wanted = list(opts.corp_code)
    if opts.corp_codes_file:
        wanted += [
            line.strip()
            for line in opts.corp_codes_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    if wanted:
        # 지정한 기업만 돈다. 아카이브에 없는 코드는 돌 수 없으므로 알리고 뺀다.
        selected = set(wanted)
        unknown = sorted(selected - set(todo))
        if unknown:
            print(f"아카이브에 없는 기업 {len(unknown)}개는 건너뛴다: {', '.join(unknown[:5])}", flush=True)
        todo = [code for code in todo if code in selected]
    if opts.retry_failed:
        todo = [code for code in todo if code in progress.failed]
    else:
        todo = [code for code in todo if code not in progress.done]
    if opts.limit:
        todo = todo[:opts.limit]

    total = len(todo)
    print(f"대상 {total}개사 | 이미 완료 {len(progress.done)} | 동시 {opts.workers}", flush=True)
    if not total:
        return 0

    started = time.monotonic()
    counter = {"done": 0, "failed": 0}
    counter_lock = threading.Lock()

    def worker(corp_code: str) -> None:
        row = build_company(corp_code, opts, scripts)
        progress.write(row)
        with counter_lock:
            counter["done"] += 1
            if row["status"] != "success":
                counter["failed"] += 1
            n = counter["done"]
            elapsed = time.monotonic() - started
            rate = elapsed / n
            left = (total - n) * rate / 3600
            mark = "OK " if row["status"] == "success" else "FAIL"
            print(f"[{n}/{total}] {mark} {corp_code} {row['elapsed_s']}s "
                  f"| 실패 {counter['failed']} | 남은 시간 약 {left:.1f}h", flush=True)

    with ThreadPoolExecutor(max_workers=opts.workers) as pool:
        list(pool.map(worker, todo))

    elapsed = (time.monotonic() - started) / 3600
    print(f"완료: 성공 {total - counter['failed']} / 실패 {counter['failed']} / {elapsed:.1f}시간", flush=True)
    return 1 if counter["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
