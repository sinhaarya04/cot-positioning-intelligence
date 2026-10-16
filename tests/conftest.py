import pytest


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Every test is offline by convention and isolated from user databases/keys."""
    monkeypatch.setenv("COT_DB_PATH", str(tmp_path / "test.duckdb"))
    monkeypatch.setenv("COT_RAW_DIR", str(tmp_path / "raw"))
    monkeypatch.delenv("COT_RELEASE_CALENDAR", raising=False)
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    monkeypatch.delenv("COT_START_DATE", raising=False)
