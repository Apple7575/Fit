import json
import tempfile
import unittest
from pathlib import Path

from data.scripts.run_rag_chunking_experiment import build_command


class ChunkingExperimentCliTest(unittest.TestCase):
    def test_build_command_uses_fixed_selection_and_isolated_profile_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selection = root / "selection.json"
            selection.write_text(json.dumps({
                "companies": [{"corp_code": "00126380"}, {"corp_code": "00164779"}],
            }), encoding="utf-8")

            command = build_command(
                selection=selection, dart_archive=root / "dart.zip",
                extract_dir=root / "extracted", output_root=root / "output",
                profile="adaptive-v1", workers=16, embedding_dimension=1024,
            )

        self.assertIn("adaptive-v1", command)
        self.assertIn(str(root / "output" / "staging" / "adaptive-v1"), command)
        self.assertEqual(command.count("--corp-code"), 2)


if __name__ == "__main__":
    unittest.main()
