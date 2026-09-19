"""고정 기업 표본에 여러 청킹 프로필을 순차 실행한다."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.raw_sources.chunking_profiles import chunking_profile_names  # noqa: E402


def build_command(
    *, selection: Path, dart_archive: Path, extract_dir: Path, output_root: Path,
    profile: str, workers: int, embedding_dimension: int,
) -> list[str]:
    payload = json.loads(selection.read_text(encoding="utf-8"))
    corp_codes = [company["corp_code"] for company in payload["companies"]]
    command = [
        sys.executable, str(Path(__file__).with_name("build_rag_corpus.py")),
        "--business-report-only", "--dry-run",
        "--dart-archive", str(dart_archive),
        "--extract-dir", str(extract_dir),
        "--workers", str(workers),
        "--embedding-dimension", str(embedding_dimension),
        "--chunking-profile", profile,
        "--staging-dir", str(output_root / "staging" / profile),
        "--output", str(output_root / f"{profile}-summary.json"),
    ]
    for corp_code in corp_codes:
        command.extend(("--corp-code", corp_code))
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="기업 RAG 다중 청킹 프로필 실험")
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--dart-archive", required=True, type=Path)
    parser.add_argument("--extract-dir", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--embedding-dimension", type=int, default=1024)
    parser.add_argument(
        "--profile", action="append", choices=chunking_profile_names(),
        dest="profiles",
    )
    args = parser.parse_args()
    profiles = args.profiles or list(chunking_profile_names())
    args.output_root.mkdir(parents=True, exist_ok=True)

    for profile in profiles:
        print(json.dumps({
            "event": "profile_started", "profile": profile,
            "at": datetime.now().astimezone().isoformat(),
        }, ensure_ascii=False), flush=True)
        completed = subprocess.run(build_command(
            selection=args.selection, dart_archive=args.dart_archive,
            extract_dir=args.extract_dir, output_root=args.output_root,
            profile=profile, workers=args.workers,
            embedding_dimension=args.embedding_dimension,
        ), check=False)
        print(json.dumps({
            "event": "profile_finished", "profile": profile,
            "return_code": completed.returncode,
            "at": datetime.now().astimezone().isoformat(),
        }, ensure_ascii=False), flush=True)
        if completed.returncode not in (0, 1):
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
