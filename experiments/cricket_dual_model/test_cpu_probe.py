"""No-network, CPU-only toy-training regression suite."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from train_cpu_probe import TRAIN_FAMILIES, TEST_FAMILIES, examples, fit


class TrainingProbeTests(unittest.TestCase):
    def test_template_family_holdout_is_disjoint(self):
        self.assertTrue(set(TRAIN_FAMILIES).isdisjoint(TEST_FAMILIES))
        tr, te = examples(TRAIN_FAMILIES), examples(TEST_FAMILIES)
        self.assertEqual(len(tr), 320)
        self.assertEqual(len(te), 160)
        self.assertTrue({x["family"] for x in tr}.isdisjoint(
            {x["family"] for x in te}))

    def test_labels_balanced_and_no_duplicate_pairs(self):
        for rows in (examples(TRAIN_FAMILIES), examples(TEST_FAMILIES)):
            self.assertEqual(sum(x["label"] for x in rows), len(rows) // 2)
            self.assertEqual(len(rows), len({(x["text"], x["label"]) for x in rows}))

    def test_real_fit_emits_research_only_artifact(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "fresh-training"
            report = fit(path)
            self.assertEqual(report["training_rows"], 320)
            self.assertEqual(report["holdout_rows"], 160)
            self.assertFalse(report["independent_model_provenance_verified"])
            self.assertIn("NOT_DEPLOYED", report["status"])
            self.assertEqual(report["artifact_sha256"], hashlib.sha256(
                (path / "toy_cpu_reviewer.joblib").read_bytes()).hexdigest())
            self.assertEqual(json.loads((path / "receipt.json").read_text())["seed"],
                             report["seed"])
            with self.assertRaises(FileExistsError):
                fit(path)


if __name__ == "__main__":
    unittest.main()
