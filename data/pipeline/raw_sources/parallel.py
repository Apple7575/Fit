"""사업보고서 XML을 기업 단위로 병렬 파싱한다."""

from concurrent.futures import ProcessPoolExecutor
from collections import Counter
from pathlib import Path
import time
from typing import Iterator

from pipeline.rag_corpus.load import build_business_report_records

from .business_report import BusinessReportSource
from .chunking_profiles import get_chunking_profile
from .dart_archive import DartArchive
from .models import EvidenceBatch
from .staging import stage_batch_lazy


_WORKER_SOURCE: BusinessReportSource | None = None
_WORKER_STAGING_DIR: Path | None = None
_WORKER_SOURCE_SIGNATURE = ""


def _init_worker(
    archive_dir: str, staging_dir: str, source_signature: str, profile_name: str,
) -> None:
    global _WORKER_SOURCE, _WORKER_STAGING_DIR, _WORKER_SOURCE_SIGNATURE
    _WORKER_SOURCE = BusinessReportSource(
        DartArchive(archive_dir), profile=get_chunking_profile(profile_name),
    )
    _WORKER_STAGING_DIR = Path(staging_dir)
    _WORKER_SOURCE_SIGNATURE = source_signature


def _build_company_batch(corp_code: str) -> dict[str, object]:
    if _WORKER_SOURCE is None or _WORKER_STAGING_DIR is None:
        raise RuntimeError("사업보고서 worker가 초기화되지 않았습니다")
    started = time.monotonic()
    staged = stage_batch_lazy(
        _WORKER_STAGING_DIR, corp_code,
        lambda: _validated_batch(corp_code, _WORKER_SOURCE.batch(corp_code)),
        source_signature=_WORKER_SOURCE_SIGNATURE,
        chunking_version=_WORKER_SOURCE.profile.name,
    )
    return {**staged, "elapsed_ms": int((time.monotonic() - started) * 1000)}


def iter_parallel_batches(
    archive_dir: str | Path, corp_codes: list[str], *, workers: int,
    staging_dir: str | Path, source_signature: str,
    profile_name: str = "structural-1500-v2",
) -> Iterator[dict[str, object]]:
    """기업 순서를 유지하며 사업보고서 배치를 병렬 생성한다."""
    if workers <= 0:
        raise ValueError("workers는 양수여야 합니다")
    if workers == 1:
        source = BusinessReportSource(
            DartArchive(archive_dir), profile=get_chunking_profile(profile_name),
        )
        for corp_code in corp_codes:
            started = time.monotonic()
            staged = stage_batch_lazy(
                Path(staging_dir), corp_code,
                lambda: _validated_batch(corp_code, source.batch(corp_code)),
                source_signature=source_signature,
                chunking_version=profile_name,
            )
            yield {**staged, "elapsed_ms": int((time.monotonic() - started) * 1000)}
        return
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_worker,
        initargs=(
            str(Path(archive_dir).resolve()), str(Path(staging_dir).resolve()), source_signature,
            profile_name,
        ),
    ) as executor:
        yield from executor.map(_build_company_batch, corp_codes, chunksize=1)


def _validated_batch(corp_code: str, batch: EvidenceBatch) -> EvidenceBatch:
    result = build_business_report_records(corp_code, batch.records)
    inputs = Counter(batch.input_counts)
    inputs["external:DART_BUSINESS_REPORT"] += len(batch.records)
    inputs.update(
        f"business_report_{record.metadata['content_type'].lower()}_chunks"
        for record in result.records
        if record.metadata.get("content_type") in ("TEXT", "TABLE")
    )
    excluded = Counter(batch.excluded_counts)
    excluded.update(result.excluded_counts)
    return EvidenceBatch(
        result.records, dict(sorted(inputs.items())), dict(sorted(excluded.items())), batch.failures,
    )
