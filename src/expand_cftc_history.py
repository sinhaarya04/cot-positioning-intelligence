"""Reproduce a bounded, reviewed expansion of CFTC publication evidence.

This extracts explicit facts from official notices. It never reconstructs a
calendar from weekdays, treats a schedule as an accomplished publication, or
assigns an intraday timestamp to a date-only notice. Run with --fetch to preserve
new source snapshots, or without it to replay a previously archived snapshot.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

import requests

from src.research_audit import COLUMNS, load_evidence

ROOT = Path(__file__).resolve().parents[1]
ANNOUNCEMENTS = "https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm"
SOURCES = {
    "announcements": ANNOUNCEMENTS,
    "launch": "https://www.cftc.gov/PressRoom/PressReleases/5710-09",
    "history": "https://www.cftc.gov/About/HistoryoftheCFTC/history_2000s.html",
    "shutdown_2019": "https://www.cftc.gov/PressRoom/PressReleases/7864-19",
}
PARSER_VERSION = "cftc-reviewed-notices-v1"


def normalize(text):
    return " ".join(text.split())


class NoticeHTML(HTMLParser):
    """Collect prose paragraphs and tables, retaining each table's preceding prose."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.paragraphs, self.tables, self.text = [], [], []
        self.paragraph = self.table = self.row = self.cell = None
        self.context = ""
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "p" and self.table is None:
            self.paragraph = []
        elif tag == "table":
            if self.table is not None:
                raise ValueError("Nested evidence tables require manual review")
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        self.text.append(data)
        if self.paragraph is not None:
            self.paragraph.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "p" and self.paragraph is not None:
            text = normalize("".join(self.paragraph))
            self.paragraphs.append(text)
            self.context = text
            self.paragraph = None
        elif tag in {"td", "th"} and self.cell is not None:
            self.row.append(normalize("".join(self.cell)))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append((self.context, self.table))
            self.table = None


# Each rule was read in its notice context. Anchors are checked before the
# reviewed dates are emitted. Scope is the weekly report's publication event;
# this does not assert that corrected fields or every contract were available.
# Notice date, report date, publication/bound date, status, required anchors.
RULES = [
    ("January 7, 2010:", "2009-12-29", "2010-01-04", "confirmed",
     ("COT data published on January 4 (as of December 29)", "Henry Hub Swap")),
    ("April 28, 2010:", "2010-04-20", "2010-04-23", "confirmed",
     ("reports published on April 23, 2010 for trade date April 20, 2010",)),
    ("May 27, 2010:", "2010-05-18", "2010-05-21", "confirmed",
     ("trade date May 18, 2010", "reports published on May 21, 2010")),
    ("September 2, 2010:", "2010-08-17", "2010-08-20", "confirmed",
     ("trade date August 17, 2010", "report published on August 20, 2010")),
    ("March 11, 2011:", "2011-03-08", "2011-03-11", "confirmed",
     ("trade date 03/08/2011", "NYMEX Platinum", "report published today")),
    ("May 27, 2011:", "2011-05-24", "2011-05-27", "confirmed",
     ("trade date 5/24/2011", "NYMEX Dubai Crude Oil", "report published today")),
    ("October 14, 2011:", "2011-10-11", "2011-10-14", "confirmed",
     ("trade date 10/11/2011", "reports published today")),
    ("January 13, 2012:", "2012-01-10", "2012-01-13", "confirmed",
     ("trade date 01/10/2012", "NATURAL GAS ICE HENRY HUB", "report published today")),
    ("December 4, 2012:", "2012-11-27", "2012-12-04", "available_by",
     ("reports for 11/27/2012 did not include", "updated commitments reports")),
    ("June 22, 2015:", "2015-06-16", "2015-06-22", "available_by",
     ("report for June 16, 2015 included changes in formatting", "will release a revised COT report")),
    ("April 4, 2017:", "2017-03-28", "2017-04-04", "available_by",
     ("today we have published updated commitment reports for as of date March 28, 2017",)),
    ("November 4, 2011:", "2011-11-08", "2011-11-14", "scheduled",
     ("MF Global", "scheduled", "Monday, November 14", "Tuesday, November 8")),
]


def make_rows(report, release, status, note, source=ANNOUNCEMENTS, datasets=("legacy", "disagg")):
    return [{"evidence_id": f"cftc-{report}-{release}-{dataset}-{status}",
             "dataset": dataset, "market": "*", "report_date": report,
             "release_date": release, "release_at": "", "status": status,
             "source": source, "note": note} for dataset in datasets]


def reviewed_notice_rows(html):
    document = NoticeHTML(html)
    rows = []
    for prefix, report, release, status, anchors in RULES:
        candidates = [p for p in document.paragraphs if p.startswith(prefix)
                      and all(anchor in p for anchor in anchors)]
        if len(candidates) != 1:
            raise ValueError(f"Missing or changed reviewed notice: {prefix}")
        if status == "confirmed":
            note = (f"Notice dated {prefix[:-1]} explicitly identifies report date {report} and "
                    f"publication {release}. The weekly publication event is supported; "
                    "contract-specific adjustments or later corrections do not establish original values.")
            if report == "2009-12-29":
                note += " The December observation year is 2009, preceding the dated January 2010 notice."
            if report == "2010-04-20":
                note += " Late inclusion concerned ICE Henry Hub 023391 and cocoa, not NYMEX 023651 or 067651."
        elif status == "available_by":
            note = (f"Notice dated {prefix[:-1]} discusses an already published or updated report "
                    f"dated {report}. Some version existed by {release}; this does not identify "
                    "the original publication day, first-release values, or an intraday timestamp.")
        else:
            note = (f"Notice dated {prefix[:-1]} explicitly schedules data from {report} for "
                    f"{release}. Prospective language does not confirm actual publication.")
        rows.extend(make_rows(report, release, status, note))
    return rows


def parse_table_date(cell):
    # Permit only the visible footnote markers, not arbitrary trailing text.
    match = re.fullmatch(r"(\d{2}/\d{2}/\d{4})\s*\+{0,2}", cell)
    if not match:
        raise ValueError(f"Unexpected CFTC schedule date: {cell!r}")
    return datetime.strptime(match.group(1), "%m/%d/%Y").date().isoformat()


def catchup_schedule_rows(html):
    document = NoticeHTML(html)
    rows, seen_notices = [], set()
    known = {"December 9, 2025:": (13, "scheduled"),
             "November 18, 2025:": (17, "superseded")}
    for context, table in document.tables:
        if not table or table[0] != ["COT Report Date", "Original Publish Date", "New Publish Date"]:
            continue
        prefixes = [key for key in known if context.startswith(key)]
        if len(prefixes) != 1 or "intended COT Report publication dates" not in context:
            raise ValueError("Unreviewed catch-up schedule context")
        prefix = prefixes[0]
        if prefix in seen_notices:
            raise ValueError("Duplicate catch-up schedule")
        seen_notices.add(prefix)
        expected, status = known[prefix]
        if len(table) - 1 != expected:
            raise ValueError(f"Changed catch-up schedule length: {prefix}")
        seen_reports = set()
        for cells in table[1:]:
            if len(cells) != 3:
                raise ValueError("Malformed catch-up schedule row")
            report, original, planned = map(parse_table_date, cells)
            if report in seen_reports or planned < report or original < report:
                raise ValueError("Duplicate or invalid report date in schedule")
            seen_reports.add(report)
            note = (f"{prefix[:-1]} table explicitly pairs report {report}, original intended "
                    f"publication {original}, and revised intended publication {planned}. "
                    "Schedule evidence only; actual publication is not established.")
            if status == "superseded":
                note += " This plan version was replaced by the December 9 table, including return to normal schedule."
            rows.extend(make_rows(report, planned, status, note))
    if seen_notices != set(known):
        raise ValueError("Missing reviewed 2025 catch-up table")
    return rows


def supplemental_rows(sources):
    launch = normalize(" ".join(NoticeHTML(sources["launch"]).text))
    history = normalize(" ".join(NoticeHTML(sources["history"]).text))
    if not all(t in launch for t in ("September 4, 2009", "for data as of September 1", "22 contract markets")):
        raise ValueError("Changed Disaggregated launch announcement")
    if not re.search(r"September 4, 2009\s*[—–-]\s*The CFTC begins disaggregating", history):
        raise ValueError("Missing retrospective confirmation of Disaggregated launch")
    rows = make_rows("2009-09-01", "2009-09-04", "confirmed",
                     "CFTC's retrospective history dates the start of Disaggregated publication to 2009-09-04. "
                     "Its linked launch notice explicitly identifies data as of September 1 for the initial 22 markets: "
                     f"{SOURCES['launch']}. This establishes launch-week publication, not an intraday time or original values.",
                     source=SOURCES["history"], datasets=("disagg",))
    shutdown = normalize(" ".join(NoticeHTML(sources["shutdown_2019"]).text))
    if not all(t in shutdown for t in ("Monday, December 24, 2018", "expects to publish this report on Friday, February 1, 2019")):
        raise ValueError("Changed 2019 shutdown schedule notice")
    rows.extend(make_rows("2018-12-24", "2019-02-01", "scheduled",
                          "2019-01-29 press release explicitly pairs observations dated Monday 2018-12-24 "
                          "with an expected resumption on 2019-02-01. This is a plan, not confirmation; "
                          "later Tuesday/Friday releases are not inferred from the stated cadence.",
                          source=SOURCES["shutdown_2019"]))
    return rows


def expand_rows(existing, sources):
    additions = (reviewed_notice_rows(sources["announcements"])
                 + catchup_schedule_rows(sources["announcements"])
                 + supplemental_rows(sources))
    merged = {row["evidence_id"]: row for row in existing}
    if len(merged) != len(existing):
        raise ValueError("Duplicate existing evidence IDs")
    for row in additions:
        old = merged.get(row["evidence_id"])
        if old:
            if any(old[key] != row[key] for key in COLUMNS if key != "note"):
                raise ValueError(f"Conflicting existing evidence: {row['evidence_id']}")
            # Retain the prior hand-reviewed provenance note verbatim.
        else:
            merged[row["evidence_id"]] = row
    return sorted(merged.values(), key=lambda r: (r["report_date"], r["release_date"], r["dataset"], r["status"]))


def source_snapshots(cache_dir, fetch=False):
    """Sequential bounded requests, content-addressed bytes, hash-checked replay."""
    cache_dir = Path(cache_dir)
    manifest_path = cache_dir / "expansion-manifest.json"
    if fetch:
        cache_dir.mkdir(parents=True, exist_ok=True)
        manifest = {"parser_version": PARSER_VERSION, "sources": {}}
        for key, url in SOURCES.items():
            response = requests.get(url, timeout=(10, 40))
            response.raise_for_status()
            payload = response.content
            digest = hashlib.sha256(payload).hexdigest()
            filename = f"{key}-{digest}.html"
            (cache_dir / filename).write_bytes(payload)
            manifest["sources"][key] = {"url": url, "file": filename, "sha256": digest,
                                         "bytes": len(payload),
                                         "retrieved_at": datetime.now(timezone.utc).isoformat()}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("parser_version") != PARSER_VERSION or set(manifest.get("sources", {})) != set(SOURCES):
        raise ValueError("Snapshot manifest does not match this parser")
    sources = {}
    for key, url in SOURCES.items():
        record = manifest["sources"][key]
        if record["url"] != url or Path(record["file"]).name != record["file"]:
            raise ValueError("Invalid source manifest entry")
        payload = (cache_dir / record["file"]).read_bytes()
        if len(payload) != record["bytes"] or hashlib.sha256(payload).hexdigest() != record["sha256"]:
            raise ValueError("Source snapshot hash mismatch")
        sources[key] = payload.decode("utf-8")
    return sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=ROOT / "config/release_evidence_cftc.csv")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "data/release_evidence_cftc")
    parser.add_argument("--fetch", action="store_true", help="Download the four reviewed official pages")
    parser.add_argument("--output", type=Path, required=True, help="CSV to write after all evidence checks succeed")
    args = parser.parse_args()
    rows = expand_rows(load_evidence([args.evidence]), source_snapshots(args.cache_dir, args.fetch))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    try:
        with temporary.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        load_evidence([temporary])
        temporary.replace(args.output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({"evidence_rows": len(rows), "status_counts": {
        status: sum(row["status"] == status for row in rows)
        for status in sorted({row["status"] for row in rows})}}, indent=2))


if __name__ == "__main__":
    main()
