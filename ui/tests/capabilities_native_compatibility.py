"""Re-analyze an existing native snapshot offline; preserve every original file."""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ui" / "server"))
import capability_operations as operations
import assessment_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root", type=Path)
    args = parser.parse_args()
    parent = args.run_root.resolve()

    def hashes():
        return {str(path.relative_to(parent)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in parent.rglob("*") if path.is_file()}

    before = hashes()
    with tempfile.TemporaryDirectory(prefix="native-capability-compatibility-") as folder:
        output = Path(folder)
        child = operations.reanalyze(output, parent, {})["runId"]
        analysis = operations.load(output / child / "capability-analysis.json")
        results = assessment_server.map_results(output / child)
        assert results["parentRunId"] == parent.name
        assert analysis["origin"] == "native"
        assert before == hashes(), "Parent snapshot changed"
        record = {"status": "PASS", "boundary": "Existing native evidence; temporary local analysis; no cloud calls; original file hashes unchanged",
                  "coverage": analysis["coverage"], "findings": len(analysis["findings"]), "legacyResultsLoaded": True}
        operations.save(ROOT / "ui" / "docs" / "test-evidence" / "capabilities-existing-evidence.json", record)
        print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
