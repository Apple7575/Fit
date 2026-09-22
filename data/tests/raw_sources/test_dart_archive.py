import csv
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from pipeline.raw_sources.dart_archive import DartArchive, extract_archive
from pipeline.raw_sources.parallel import iter_parallel_batches


def make_archive(path: Path, rows: list[dict], files: dict[str, bytes]) -> None:
    output = io.StringIO(newline="")
    fields = ["corp_name", "corp_code", "year", "rcept_no", "rcept_dt", "report_nm", "file"]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("dart_local/company_reports.csv", output.getvalue())
        for name, payload in files.items():
            archive.writestr(f"dart_local/cache/{name}", payload)


class DartArchiveTest(unittest.TestCase):
    def test_extract_archive_materializes_zip_once_and_reuses_complete_marker(self):
        rows = [{
            "corp_name": "회사1", "corp_code": "00000001", "year": 2024,
            "rcept_no": "20250318000001", "rcept_dt": "20250318", "report_nm": "사업보고서",
            "file": "document_20250318000001.xml",
        }]
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "dart.zip"
            extract_dir = Path(directory) / "cache"
            make_archive(archive_path, rows, {rows[0]["file"]: b"<DOCUMENT/>"})
            first = extract_archive(archive_path, extract_dir)
            marker_before = (extract_dir / ".complete").read_text(encoding="utf-8")
            second = extract_archive(archive_path, extract_dir)

            self.assertEqual(first, extract_dir)
            self.assertEqual(second, extract_dir)
            self.assertEqual((extract_dir / "dart_local/cache/document_20250318000001.xml").read_bytes(), b"<DOCUMENT/>")
            self.assertEqual((extract_dir / ".complete").read_text(encoding="utf-8"), marker_before)

    def test_reads_manifest_and_xml_from_extracted_directory(self):
        rows = [{
            "corp_name": "회사1", "corp_code": "00000001", "year": 2024,
            "rcept_no": "20250318000001", "rcept_dt": "20250318", "report_nm": "사업보고서",
            "file": "document_20250318000001.xml",
        }]
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "dart.zip"
            extract_dir = Path(directory) / "cache"
            make_archive(archive_path, rows, {rows[0]["file"]: b"<DOCUMENT/>"})
            extract_archive(archive_path, extract_dir)
            with DartArchive(extract_dir) as archive:
                ref = archive.documents("00000001")[0]
                self.assertEqual(archive.read(ref), b"<DOCUMENT/>")

    def test_parallel_batches_preserves_requested_company_order(self):
        rows = [
            {"corp_name": "회사1", "corp_code": "00000001", "year": 2024,
             "rcept_no": "20250318000001", "rcept_dt": "20250318", "report_nm": "사업보고서",
             "file": "document_20250318000001.xml"},
            {"corp_name": "회사2", "corp_code": "00000002", "year": 2024,
             "rcept_no": "20250318000002", "rcept_dt": "20250318", "report_nm": "사업보고서",
             "file": "document_20250318000002.xml"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "dart.zip"
            extract_dir = Path(directory) / "cache"
            make_archive(archive_path, rows, {
                row["file"]: b"<DOCUMENT/>" for row in rows
            })
            extract_archive(archive_path, extract_dir)
            staging_dir = Path(directory) / "staging"
            batches = list(iter_parallel_batches(
                extract_dir, ["00000002", "00000001"], workers=2,
                staging_dir=staging_dir, source_signature="archive-v1",
            ))

        self.assertEqual(len(batches), 2)
        self.assertEqual([batch["corp_code"] for batch in batches], ["00000002", "00000001"])
        self.assertEqual([batch["write_status"] for batch in batches], ["staged", "staged"])
    def test_indexes_manifest_without_extracting_and_counts_missing_xml(self):
        rows = [
            {"corp_name": "회사2", "corp_code": "00000002", "year": 2024,
             "rcept_no": "20250318000002", "rcept_dt": "20250318", "report_nm": "사업보고서",
             "file": "document_20250318000002.xml"},
            {"corp_name": "회사1", "corp_code": "00000001", "year": 2023,
             "rcept_no": "20240318000001", "rcept_dt": "20240318", "report_nm": "사업보고서",
             "file": "document_20240318000001.xml"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "dart.zip"
            make_archive(archive_path, rows, {rows[0]["file"]: b"<DOCUMENT/>"})
            with DartArchive(archive_path) as archive:
                selected = archive.documents("00000002", years={2024})
                inventory = archive.inventory()
                payload = archive.read(selected[0])

        self.assertEqual(selected[0].entry_name, "dart_local/cache/document_20250318000002.xml")
        self.assertEqual(payload, b"<DOCUMENT/>")
        self.assertEqual(inventory["excluded"], {"manifest_missing_xml": 1})

    def test_keeps_missing_manifest_xml_as_company_failure_lineage(self):
        rows = [{
            "corp_name": "회사1", "corp_code": "00000001", "year": 2024,
            "rcept_no": "20250318000001", "rcept_dt": "20250318", "report_nm": "사업보고서",
            "file": "document_20250318000001.xml",
        }]
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "dart.zip"
            make_archive(archive_path, rows, {})
            with DartArchive(archive_path) as archive:
                failures = archive.failures("00000001", years={2024})

        self.assertEqual(failures, ({
            "corp_code": "00000001", "rcept_no": "20250318000001",
            "document_file": "document_20250318000001.xml", "reason": "manifest_missing_xml",
        },))


if __name__ == "__main__":
    unittest.main()
