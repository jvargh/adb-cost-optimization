import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ASSESSMENT_ROOT = Path(__file__).resolve().parents[2]
if str(ASSESSMENT_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ASSESSMENT_ROOT.parent))

from assessment.reports import render_reports
from assessment.reports.render import REPORT_FILES


class ReportRendererTests(unittest.TestCase):
    fixture_path = Path(__file__).parent / "fixtures" / "report_case.json"

    def _materialize_fixture(self, root: Path) -> None:
        fixture = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        normalized = fixture.pop("normalized")
        for name, value in fixture.items():
            (root / name).write_text(
                json.dumps(value, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        normalized_root = root / "normalized"
        normalized_root.mkdir()
        for entity, records in normalized.items():
            (normalized_root / f"{entity}.ndjson").write_text(
                "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
                encoding="utf-8",
            )

    def test_renders_all_reports_and_csvs_deterministically_from_fixture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._materialize_fixture(root)

            first = render_reports(root)
            first_bytes = {path.name: path.read_bytes() for path in first}
            second = render_reports(root)
            second_bytes = {path.name: path.read_bytes() for path in second}

            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(
                {
                    "assessment-report.md",
                    "top-cost-drivers.csv",
                    "prioritized-backlog.csv",
                    "human-validation-sign-off.csv",
                },
                set(first_bytes),
            )

    def test_reports_preserve_finding_ids_evidence_links_and_unknown_savings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._materialize_fixture(root)
            render_reports(root)

            report = (root / "reports" / "assessment-report.md").read_text(encoding="utf-8")
            drivers = (root / "reports" / "top-cost-drivers.csv").read_text(encoding="utf-8")

            self.assertIn("MON-UNOWNED-COST", report)
            self.assertIn("DYN-AUTOSCALING", report)
            self.assertIn("[finding record](../optimization-candidates.json)", report)
            self.assertIn("Not estimated", report)
            self.assertIn("../cost-reconciliation.json", report)
            self.assertIn("**Insufficient evidence:**", report)
            self.assertIn("## 17. Human validation and sign-off", report)
            self.assertLess(drivers.index("workspace-a"), drivers.index("workspace-b"))

    def test_resource_findings_keep_unique_ids_in_report_and_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._materialize_fixture(root)
            path = root / "optimization-candidates.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["findings"] = [{**data["findings"][0], "detectorId": "CAP-SIZING", "findingId": name}
                                for name in ("resource-instance-one", "resource-instance-two")]
            path.write_text(json.dumps(data), encoding="utf-8")
            render_reports(root)
            for file in ("assessment-report.md", "prioritized-backlog.csv", "human-validation-sign-off.csv"):
                text = (root / "reports" / file).read_text(encoding="utf-8")
                for name in ("resource-instance-one", "resource-instance-two"):
                    self.assertIn(name, text)

    def test_pipeline_invokes_report_renderer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "config.json"
            config.write_text(json.dumps({
                "customerId": "customer",
                "assessmentId": "assessment",
                "azure": {"currency": "USD"},
                "analysis": {
                    "startUtc": "2026-01-01T00:00:00Z",
                    "endUtc": "2026-02-01T00:00:00Z",
                },
                "thresholds": {},
            }), encoding="utf-8")
            run_root = root / "run"
            raw = run_root / "raw" / "azure"
            raw.mkdir(parents=True)
            (raw / "cost-management.ndjson").write_text(
                '{"costBasis":"ActualCost","PreTaxCost":12,"Currency":"USD"}\n',
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ASSESSMENT_ROOT / "pipeline" / "run_assessment.py"),
                    "--config",
                    str(config),
                    "--run-root",
                    str(run_root),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue((run_root / "reports" / "assessment-report.md").exists())
            self.assertTrue((run_root / "reports" / "prioritized-backlog.csv").exists())


if __name__ == "__main__":
    unittest.main()
