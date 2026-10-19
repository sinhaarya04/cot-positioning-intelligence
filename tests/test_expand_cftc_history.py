"""Publication evidence must survive source changes without guessing dates."""
import copy
from datetime import date, timedelta
import hashlib
import json

import pytest

from src import expand_cftc_history as history


def schedule_fixture():
    parts = []
    for prefix, count in (("December 9, 2025:", 13), ("November 18, 2025:", 17)):
        parts.append(f"<p>{prefix} intended COT Report publication dates</p><table>")
        parts.append("<tr><th>COT Report Date</th><th>Original Publish Date</th><th>New Publish Date</th></tr>")
        for i in range(count):
            report = date(2025, 9, 30) + timedelta(weeks=i)
            original, planned = report + timedelta(days=3), report + timedelta(days=50)
            parts.append(f"<tr><td><strong>{report:%m/%d/%Y}</strong></td>"
                         f"<td>{original:%m/%d/%Y}</td><td>{planned:%m/%d/%Y}<sup>+</sup></td></tr>")
        parts.append("</table>")
    return "".join(parts)


def test_all_past_schedule_rows_remain_plans_with_blank_timestamps():
    rows = history.catchup_schedule_rows(schedule_fixture())
    assert len(rows) == 60
    assert {r["status"] for r in rows} == {"scheduled", "superseded"}
    assert sum(r["status"] == "superseded" for r in rows) == 34
    assert all(r["release_at"] == "" for r in rows)


@pytest.mark.parametrize("transform", [
    lambda html: html.replace("December 9, 2025:", "December 10, 2025:"),
    lambda html: html.replace("intended COT Report publication dates", "COT publication dates"),
    lambda html: html.replace("11/19/2025<sup>+</sup>", "11/19/2025 revised"),
    lambda html: html.replace("09/30/2025", "11/30/2025"),
])
def test_changed_schedule_context_or_invalid_dates_fail_closed(transform):
    with pytest.raises(ValueError):
        history.catchup_schedule_rows(transform(schedule_fixture()))


def test_missing_table_and_duplicate_table_are_rejected():
    html = schedule_fixture()
    first = html[:html.index("</table>") + len("</table>")]
    with pytest.raises(ValueError, match="Missing reviewed"):
        history.catchup_schedule_rows(first)
    with pytest.raises(ValueError, match="Duplicate"):
        history.catchup_schedule_rows(html + first)


def test_date_parsing_does_not_accept_unreviewed_notes_or_invalid_dates():
    assert history.parse_table_date("11/10/2025++") == "2025-11-10"
    for value in ("11/10/2025 probably", "11/31/2025", "11/10/25", "11/10/2025+++"):
        with pytest.raises(ValueError):
            history.parse_table_date(value)


def test_notice_rule_requires_publication_wording_not_only_dates(monkeypatch):
    monkeypatch.setattr(history, "RULES", [history.RULES[4]])
    html = ("<p>March 11, 2011: Due to a clearing system problem for trade date "
            "03/08/2011 in NYMEX Platinum, the report published today was adjusted.</p>")
    rows = history.reviewed_notice_rows(html)
    assert {r["report_date"] for r in rows} == {"2011-03-08"}
    assert {r["release_date"] for r in rows} == {"2011-03-11"}
    assert all(r["status"] == "confirmed" and not r["release_at"] for r in rows)
    with pytest.raises(ValueError, match="Missing or changed"):
        history.reviewed_notice_rows(html.replace("report published today", "report expected next week"))


def test_correction_notice_is_only_available_by(monkeypatch):
    monkeypatch.setattr(history, "RULES", [history.RULES[8]])
    rows = history.reviewed_notice_rows(
        "<p>December 4, 2012: Some reports for 11/27/2012 did not include classifications; "
        "updated commitments reports will follow.</p>")
    assert all(r["status"] == "available_by" for r in rows)
    assert all(r["release_at"] == "" for r in rows)
    assert all(r["release_date"] == "2012-12-04" for r in rows)


def test_launch_requires_retrospective_confirmation_and_observation_link():
    sources = {
        "launch": "September 4, 2009 (for data as of September 1) 22 contract markets",
        "history": "September 4, 2009—The CFTC begins disaggregating",
        "shutdown_2019": "Monday, December 24, 2018; expects to publish this report on Friday, February 1, 2019",
    }
    rows = history.supplemental_rows(sources)
    assert len([r for r in rows if r["status"] == "confirmed"]) == 1
    assert rows[0]["dataset"] == "disagg"
    for key in ("history", "launch"):
        changed = {**sources, key: "Ordinary releases are on Friday"}
        with pytest.raises(ValueError):
            history.supplemental_rows(changed)


def test_merge_preserves_existing_notes_and_rejects_conflicts(monkeypatch):
    new = history.make_rows("2011-03-08", "2011-03-11", "confirmed", "new note")
    monkeypatch.setattr(history, "reviewed_notice_rows", lambda _: new)
    monkeypatch.setattr(history, "catchup_schedule_rows", lambda _: [])
    monkeypatch.setattr(history, "supplemental_rows", lambda _: [])
    original = [{**new[0], "note": "Original curated provenance"}]
    merged = history.expand_rows(original, {"announcements": ""})
    assert len(merged) == 2
    assert next(r for r in merged if r["dataset"] == "legacy")["note"] == "Original curated provenance"
    assert history.expand_rows(merged, {"announcements": ""}) == merged
    broken = copy.deepcopy(original)
    broken[0]["release_date"] = "2011-03-12"
    with pytest.raises(ValueError, match="Conflicting"):
        history.expand_rows(broken, {"announcements": ""})


def test_offline_snapshot_replay_checks_hashes(tmp_path):
    payload = b"<html>Archived evidence</html>"
    (tmp_path / "source.html").write_bytes(payload)
    record = {"file": "source.html", "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
    manifest = {"parser_version": history.PARSER_VERSION, "sources": {
        key: {**record, "url": url} for key, url in history.SOURCES.items()}}
    (tmp_path / "expansion-manifest.json").write_text(json.dumps(manifest))
    assert set(history.source_snapshots(tmp_path)) == set(history.SOURCES)
    (tmp_path / "source.html").write_bytes(b"Altered source")
    with pytest.raises(ValueError, match="hash mismatch"):
        history.source_snapshots(tmp_path)
