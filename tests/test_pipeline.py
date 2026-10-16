import json
from src.pipeline import run_pipeline


def test_empty_offline_pipeline_records_missing_evidence(tmp_path):
    record = run_pipeline(skip_ingest=True, output_dir=tmp_path / "output")
    assert record["status"] == "needs_release_evidence_or_history"
    manifests = list((tmp_path / "output").glob("run-*.json"))
    saved = json.loads(manifests[0].read_text())
    assert saved["summary_rows"] == 0
    assert len(saved["source_sha256"]) == 64
    assert saved["finished_at"]
