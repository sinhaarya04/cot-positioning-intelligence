from datetime import date
import hashlib
import json

import pytest

from src.expand_eia_history import (
    Cache, Document, archive_links, merge_evidence, parse_ngwu, parse_wpsr,
)

AS_OF = date(2026, 10, 18)
SOURCE = "https://www.eia.gov/example/"


def wpsr(observation="February 17, 2023", publication="February 23, 2023"):
    return f"<h2>Weekly Petroleum Status Report</h2><p>For week ending {observation}</p><b>Release Date:</b> {publication}"


def ngwu(observation="2023-02-17", publication="February 23, 2023", prior="2023-02-10"):
    return f"""<h2>Natural Gas Weekly Update</h2><p>For week ending February 22, 2023 |
      <b>Release date:</b> {publication}</p>
      <table><tr><th>Working gas in underground storage</th></tr>
      <tr><th>Stocks</th><th>billion cubic feet (Bcf)</th></tr>
      <tr><th>Region</th><th>{observation}</th><th>{prior}</th><th>change</th></tr>
      <tr><td>Total</td><td>2,195</td><td>2,266</td><td>-71</td></tr></table>
      <p>Data source: U.S. Energy Information Administration</p>"""


def test_wpsr_holiday_date_is_read_without_scheduled_time():
    row = parse_wpsr(wpsr(), SOURCE, AS_OF)
    assert row["report_date"] == "2023-02-17"
    assert row["release_date"] == "2023-02-23"
    assert row["status"] == "confirmed"
    assert row["release_at"] == ""


def test_ngwu_uses_inventory_table_not_headline_week():
    row = parse_ngwu(ngwu(), SOURCE, AS_OF)
    assert row["report_date"] == "2023-02-17"
    assert row["status"] == "available_by"
    assert row["release_at"] == ""


def test_old_ngwu_abbreviated_month_and_slash_dates():
    row = parse_ngwu(ngwu("12/16/11", "Dec. 22, 2011", "12/9/11"), SOURCE, AS_OF)
    assert row["report_date"] == "2011-12-16"
    assert row["release_date"] == "2011-12-22"


@pytest.mark.parametrize("html", ["<p>No release header</p>",
    wpsr() + "<p>Released: February 24, 2023</p>",
    wpsr(publication="Unparseable date"),
    wpsr(publication="February 30, 2023")])
def test_missing_malformed_or_ambiguous_header_fails_closed(html):
    with pytest.raises(ValueError):
        parse_wpsr(html, SOURCE, AS_OF)


def test_scripts_and_comments_cannot_supply_release_evidence():
    html = "<!-- Release Date: February 23, 2023 -->"
    html += "<script>Release Date: February 23, 2023</script><p>For week ending February 17, 2023</p>"
    with pytest.raises(ValueError, match="Missing"):
        parse_wpsr(html, SOURCE, AS_OF)
    assert "hidden" not in Document("<style>hidden</style><p>visible</p>").text


@pytest.mark.parametrize("html", [
    ngwu("2015-12-25", "December 17, 2015", "2015-12-18"),
    ngwu("2023-02-17", prior="2023-02-24"),
    ngwu("2023-02-17", publication="March 30, 2023"),
    ngwu().replace("Total", "Unreported"),
])
def test_ngwu_future_stale_reversed_or_missing_table_fails(html):
    with pytest.raises(ValueError):
        parse_ngwu(html, SOURCE, AS_OF)


def test_ngwu_headline_without_storage_table_does_not_count():
    with pytest.raises(ValueError, match="storage table"):
        parse_ngwu("Release date: February 23, 2023 For week ending February 22, 2023", SOURCE, AS_OF)


def test_wpsr_index_fallback_requires_actual_release_header():
    row = parse_wpsr("<p>Released: August 3, 2011</p>", SOURCE, AS_OF, date(2011, 7, 29))
    assert row["report_date"] == "2011-07-29"
    assert "official archive index" in row["note"]
    with pytest.raises(ValueError, match="release header"):
        parse_wpsr("<p>Archived report</p>", SOURCE, AS_OF, date(2011, 7, 29))
    with pytest.raises(ValueError, match="disagrees"):
        parse_wpsr(wpsr(), SOURCE, AS_OF, date(2023, 2, 10))


def test_future_publication_does_not_count():
    with pytest.raises(ValueError, match="ordering"):
        parse_wpsr(wpsr(), SOURCE, date(2023, 2, 22))


def test_discovery_uses_existing_official_links_and_ignores_future():
    path = "/petroleum/supply/weekly/archive/2017/2017_01_05/wpsr_2017_01_05.php"
    future = "/petroleum/supply/weekly/archive/2027/2027_01_06/wpsr_2027_01_06.php"
    html = f'<table><tr><td>January</td><td><a href="{path}">5</a></td><td>12/30</td></tr></table>'
    html += f'<a href="{future}">Future</a><a href="https://other.example{path}">Other</a>'
    links = archive_links(html, "wpsr", 2011, AS_OF)
    assert len(links) == 1
    assert next(iter(links.values()))["index_report_date"] == date(2016, 12, 30)


def test_merge_preserves_curated_metadata_and_delayed_duplicate_observation():
    original = parse_wpsr(wpsr(), SOURCE, AS_OF)
    original["note"] = "Curated note"
    addition = {**original, "note": "Generated note"}
    delayed = {**addition, "report_date": "2023-02-10"}
    rows = merge_evidence([original], [addition, delayed])
    assert len(rows) == 2
    assert next(r for r in rows if r["report_date"] == "2023-02-17")["note"] == "Curated note"
    assert len({r["evidence_id"] for r in rows}) == 2


def test_offline_cache_checks_content_hash(tmp_path):
    url, raw = SOURCE, b"archive"
    key = hashlib.sha256(url.encode()).hexdigest()
    (tmp_path / f"{key}.html").write_bytes(raw)
    (tmp_path / f"{key}.json").write_text(json.dumps({"source": url, "http_status": 200,
            "sha256": hashlib.sha256(raw).hexdigest()}))
    cache = Cache(tmp_path, offline=True)
    assert cache.get(url)[0] == "archive"
    (tmp_path / f"{key}.html").write_bytes(b"changed")
    with pytest.raises(ValueError, match="integrity"):
        cache.get(url)
    with pytest.raises(ValueError, match="offline"):
        cache.get(url + "missing")


def test_notice_dates_do_not_override_wpsr_issue_header():
    html = wpsr() + "<p>Notice: future report with data for week ending March 3, 2023</p>"
    assert parse_wpsr(html, SOURCE, AS_OF)["report_date"] == "2023-02-17"


def test_delayed_wpsr_index_uses_printed_release_day_not_url_day():
    path = "/petroleum/supply/weekly/archive/2023/2023_11_08/wpsr_2023_11_08.php"
    html = f'<table><tr><td>November</td><td><a href="{path}">15</a></td><td>3</td></tr></table>'
    context = next(iter(archive_links(html, "wpsr", 2011, AS_OF).values()))
    assert context["issue_hint"] == date(2023, 11, 8)
    assert context["index_release_date"] == date(2023, 11, 15)
    row = parse_wpsr(wpsr("November 3, 2023", "November 15, 2023"), SOURCE, AS_OF,
                     context["index_report_date"], context["index_release_date"])
    assert row["release_date"] == "2023-11-15"


def test_denied_cache_is_never_retried_and_stops_other_network_requests(tmp_path, monkeypatch):
    import src.expand_eia_history as module

    class Session:
        def get(self, *args, **kwargs):
            class Response:
                status_code = 403
                content = b"Access denied"
            return Response()

    monkeypatch.setattr(module._THREAD, "session", Session(), raising=False)
    cache = Cache(tmp_path, retry_failures=True)
    assert cache.get(SOURCE)[1]["http_status"] == 403
    with pytest.raises(ValueError, match="Network stopped"):
        cache.get(SOURCE + "other")
    assert cache.get(SOURCE)[1]["http_status"] == 403
    restarted = Cache(tmp_path, retry_failures=True)
    with pytest.raises(ValueError, match="Network stopped"):
        restarted.get(SOURCE + "new-after-restart")


def test_archive_accepts_delayed_data_paths_and_missing_opening_row_tag():
    special = "/petroleum/supply/weekly/archive/2022/2022_06_17_data/wpsr_2022_06_17_data.php"
    november = "/petroleum/supply/weekly/archive/2016/2016_11_30/wpsr_2016_11_30.php"
    html = f'<td><a href="{special}">29</a></td><td>17</td></tr>'
    html += f'<td><a href="{november}">30</a></td><td>25</td></tr>'
    links = archive_links(html, "wpsr", 2011, AS_OF)
    assert links["https://www.eia.gov" + special]["index_report_date"] == date(2022, 6, 17)
    assert links["https://www.eia.gov" + special]["index_release_date"] == date(2022, 6, 29)
    assert links["https://www.eia.gov" + november]["index_report_date"] == date(2016, 11, 25)


def test_seed_reuses_original_metadata_and_checks_hash(tmp_path):
    raw = ngwu().encode()
    snapshot = tmp_path / "old.html"
    snapshot.write_bytes(raw)
    url = "https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/2023/02_23/"
    record = {"source": url, "path": str(snapshot), "retrieved_at": "2026-10-19T02:13:18Z",
              "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([record]))
    cache = Cache(tmp_path / "cache", offline=True)
    cache.seed(manifest)
    assert cache.get(url)[1]["retrieved_at"] == record["retrieved_at"]
    snapshot.write_bytes(b"altered")
    with pytest.raises(ValueError, match="Seed snapshot integrity"):
        cache.seed(manifest)


@pytest.mark.parametrize("bad_header", [
    wpsr("September 25, 2026", "September 30, 2026"),
    wpsr("October 2, 2026", "September 30, 2026"),
])
def test_conflicting_successful_document_is_quarantined_instead_of_using_index(bad_header):
    from src.expand_eia_history import INDEXES, expand

    bad_url = "https://www.eia.gov/petroleum/supply/weekly/archive/2026/2026_10_07/wpsr_2026_10_07.php"
    denied_url = "https://www.eia.gov/petroleum/supply/weekly/archive/2026/2026_10_15/wpsr_2026_10_15.php"
    gas_url = "https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/2023/02_23/"
    pages = {
        INDEXES["wpsr"]: (f'<tr><td><a href="{bad_url}">7</a></td><td>2</td></tr>'
                           f'<tr><td><a href="{denied_url}">15</a></td><td>9</td></tr>', 200),
        INDEXES["ngwu"]: (f'<a href="{gas_url}">February 23</a>', 200),
        bad_url: (bad_header, 200), denied_url: ("Access denied", 403), gas_url: (ngwu(), 200),
    }

    class MemoryCache:
        def get(self, url):
            html, status = pages[url]
            return html, {"source": url, "http_status": status, "retrieved_at": "2026-10-19T00:00:00Z",
                          "sha256": hashlib.sha256(html.encode()).hexdigest(), "bytes": len(html), "error": ""}

    additions, sources = expand(MemoryCache(), 2011, AS_OF, workers=1)
    identifiers = {row["evidence_id"] for row in additions}
    assert "eia-wpsr-index-2026-10-02" not in identifiers
    assert "eia-wpsr-index-2026-10-09" in identifiers
    conflict = next(row for row in sources if row["source"] == bad_url)
    assert conflict["parse_status"] == "conflict"
    assert conflict["quarantined_evidence_id"] == "eia-wpsr-index-2026-10-02"
    stale = {**parse_wpsr(wpsr(), SOURCE, AS_OF), "evidence_id": conflict["quarantined_evidence_id"]}
    curated = parse_wpsr(wpsr(), SOURCE, AS_OF)
    merged = merge_evidence([stale, curated], additions, {conflict["quarantined_evidence_id"]})
    assert stale not in merged
    assert curated in merged


def test_candidate_ledger_validation_runs_before_replacement(tmp_path):
    from src.expand_eia_history import COLUMNS, write_csv
    from src.research_audit import load_evidence
    target = tmp_path / "ledger.csv"
    row = parse_wpsr(wpsr(), SOURCE, AS_OF)
    write_csv(target, COLUMNS, [row], validator=load_evidence)
    before = target.read_bytes()
    invalid = {**row, "release_date": "2023-02-01"}
    with pytest.raises(ValueError, match="precedes"):
        write_csv(target, COLUMNS, [invalid], validator=load_evidence)
    assert target.read_bytes() == before
    assert b"\r\n" not in before
