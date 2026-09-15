from __future__ import annotations

import csv
from collections import Counter
import io
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import zipfile


_REQUIRED_COLUMNS = frozenset({"corp_name", "corp_code", "year", "rcept_no", "rcept_dt", "file"})
_CORP_CODE = re.compile(r"^[0-9]{8}$")
_RECEIPT = re.compile(r"^[0-9]{14}$")


@dataclass(frozen=True)
class DartDocumentRef:
    corp_code: str
    corp_name: str
    year: int
    rcept_no: str
    rcept_dt: str
    report_name: str
    entry_name: str
    size: int


class DartArchive:
    """ZIP을 풀지 않고 사업보고서 manifest와 XML을 읽는다."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._excluded: Counter[str] = Counter()
        self._manifest_rows = 0
        self._zip = zipfile.ZipFile(self.path)
        try:
            self._documents = self._load_manifest()
        except Exception:
            self._zip.close()
            raise

    def __enter__(self) -> "DartArchive":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self._zip.close()

    def documents(self, corp_code: str | None = None, *, years: set[int] | None = None) -> tuple[DartDocumentRef, ...]:
        return tuple(
            ref for ref in self._documents
            if (corp_code is None or ref.corp_code == corp_code) and (years is None or ref.year in years)
        )

    def companies(self) -> tuple[str, ...]:
        return tuple(sorted({ref.corp_code for ref in self._documents}))

    def read(self, ref: DartDocumentRef) -> bytes:
        return self._zip.read(ref.entry_name)

    def inventory(self) -> dict[str, object]:
        years = sorted({ref.year for ref in self._documents})
        return {
            "archive": str(self.path), "documents": len(self._documents),
            "manifest_rows": self._manifest_rows, "companies": len(self.companies()),
            "years": [years[0], years[-1]] if years else [],
            "uncompressed_xml_bytes": sum(ref.size for ref in self._documents),
            "excluded": dict(sorted(self._excluded.items())),
        }

    def _load_manifest(self) -> tuple[DartDocumentRef, ...]:
        manifest, rows = self._find_manifest()
        self._manifest_rows = len(rows)
        entries_by_name: dict[str, list[zipfile.ZipInfo]] = {}
        for entry in self._zip.infolist():
            if not entry.is_dir():
                entries_by_name.setdefault(PurePosixPath(entry.filename).name, []).append(entry)

        refs: list[DartDocumentRef] = []
        seen_company_year: set[tuple[str, int]] = set()
        seen_receipts: set[str] = set()
        for index, row in enumerate(rows, 2):
            corp_code = (row.get("corp_code") or "").strip()
            receipt = (row.get("rcept_no") or "").strip()
            filename = PurePosixPath((row.get("file") or "").strip()).name
            try:
                year = int((row.get("year") or "").strip())
            except ValueError as error:
                raise ValueError(f"manifest {manifest.filename}:{index} year가 잘못되었습니다") from error
            if not _CORP_CODE.fullmatch(corp_code) or not _RECEIPT.fullmatch(receipt):
                raise ValueError(f"manifest {manifest.filename}:{index} 식별자가 잘못되었습니다")
            if (corp_code, year) in seen_company_year:
                raise ValueError(f"manifest에 중복 기업·연도가 있습니다: {corp_code}/{year}")
            if receipt in seen_receipts:
                raise ValueError(f"manifest에 중복 접수번호가 있습니다: {receipt}")
            matches = entries_by_name.get(filename, [])
            if not matches:
                self._excluded["manifest_missing_xml"] += 1
                continue
            if len(matches) != 1:
                raise ValueError(f"manifest XML 연결이 유일하지 않습니다: {filename} ({len(matches)}건)")
            seen_company_year.add((corp_code, year))
            seen_receipts.add(receipt)
            entry = matches[0]
            refs.append(DartDocumentRef(
                corp_code=corp_code, corp_name=(row.get("corp_name") or "").strip(), year=year,
                rcept_no=receipt, rcept_dt=(row.get("rcept_dt") or "").strip(),
                report_name=(row.get("report_nm") or "").strip(), entry_name=entry.filename,
                size=entry.file_size,
            ))
        return tuple(sorted(refs, key=lambda item: (item.corp_code, item.year, item.rcept_no)))

    def _find_manifest(self) -> tuple[zipfile.ZipInfo, list[dict[str, str]]]:
        candidates: list[tuple[zipfile.ZipInfo, list[dict[str, str]]]] = []
        for entry in self._zip.infolist():
            if entry.is_dir() or not entry.filename.lower().endswith(".csv"):
                continue
            text = self._zip.read(entry).decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text), skipinitialspace=True)
            names = {name.strip() for name in reader.fieldnames if name} if reader.fieldnames else set()
            if _REQUIRED_COLUMNS.issubset(names):
                candidates.append((entry, list(reader)))
        if len(candidates) != 1:
            raise ValueError(f"사업보고서 manifest CSV가 1개여야 합니다: {len(candidates)}개")
        return candidates[0]
