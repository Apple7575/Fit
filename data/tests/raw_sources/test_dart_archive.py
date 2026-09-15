import csv
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from pipeline.raw_sources.dart_archive import DartArchive


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


if __name__ == "__main__":
    unittest.main()
