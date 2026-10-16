"""Content-addressed source snapshots, without request credentials."""
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _redact(value):
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if re.search(r"api.?key|token|authorization|password|secret", k, re.I)
                    else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def save_snapshot(dataset, identity, payload):
    """Save normalized source payload and append a retrieval manifest entry."""
    base = Path(os.environ.get("COT_RAW_DIR") or Path(__file__).resolve().parents[1] / "data/raw")
    dataset = re.sub(r"[^A-Za-z0-9_-]", "_", str(dataset))
    identity = re.sub(r"[^A-Za-z0-9_-]", "_", str(identity))
    raw = json.dumps(_redact(payload), sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    directory = base / dataset / identity
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{digest}.json"
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f"Archived snapshot failed its checksum: {path}")
    if not path.exists():
        # Link a fully written temporary file atomically; an interrupted write
        # must never leave a partial file under a valid content hash.
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".snapshot-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            try:
                os.link(temporary, path)
            except FileExistsError:
                if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise ValueError(f"Archived snapshot failed its checksum: {path}")
        finally:
            temporary.unlink(missing_ok=True)
    record = {"dataset": dataset, "identity": identity, "source_hash": digest,
              "retrieved_at": datetime.now(timezone.utc).isoformat(), "path": str(path)}
    with (base / "manifest.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    return record
