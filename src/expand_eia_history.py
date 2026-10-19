"""Expand date-only EIA release evidence from archived documents.

Never synthesizes a publication timestamp, downloads API inventory values, or
writes to the research database. Use --offline to reproduce from local snapshots.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import date, datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import threading
from urllib.parse import urljoin, urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
INDEXES = {
    "wpsr": "https://www.eia.gov/petroleum/supply/weekly/archive/",
    "ngwu": "https://www.eia.gov/naturalgas/weekly/includes/archive.php",
}
COLUMNS = ["evidence_id", "dataset", "market", "report_date", "release_date",
           "release_at", "status", "source", "note"]
SOURCE_COLUMNS = ["family", "source", "retrieved_at", "sha256", "bytes", "http_status",
                  "parse_status", "evidence_ids", "quarantined_evidence_id", "error"]
DATE_WORDS = r"[A-Za-z]+\.?\s+\d{1,2},?\s+\d{4}"
MONTHS = {name: index for index, names in enumerate([
    (), ("jan", "january"), ("feb", "february"), ("mar", "march"),
    ("apr", "april"), ("may",), ("jun", "june"), ("jul", "july"),
    ("aug", "august"), ("sep", "sept", "september"), ("oct", "october"),
    ("nov", "november"), ("dec", "december")]) for name in names}
_THREAD = threading.local()


class Document(HTMLParser):
    """Collect visible text, links and table cells without executing HTML."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.rows = [], [], []
        self.skip = 0
        self.row = None
        self.cell = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1
        if self.skip:
            return
        attrs = dict(attrs)
        if tag == "tr":
            self.row = []
        if tag in {"td", "th"}:
            if self.row is None:
                self.row = []
            self.cell = {"parts": [], "links": []}
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
            if self.cell is not None:
                self.cell["links"].append(attrs["href"])

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)
        if self.skip:
            return
        if tag in {"td", "th"} and self.cell is not None:
            if self.row is not None:
                self.row.append({"text": normalized(" ".join(self.cell["parts"])),
                                 "links": self.cell["links"]})
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, value):
        if not self.skip:
            self.parts.append(value)
            if self.cell is not None:
                self.cell["parts"].append(value)

    @property
    def text(self):
        return normalized(" ".join(self.parts))


def normalized(value):
    return re.sub(r"\s+", " ", value).strip()


def parse_date(value):
    value = normalized(value)
    match = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", value)
    if match and match[1].lower() in MONTHS:
        return date(int(match[3]), MONTHS[match[1].lower()], int(match[2]))
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unrecognized document date: {value}")


def archive_links(html, family, start_year, as_of):
    """Return only actual index links; URL dates select downloads, not evidence."""
    document = Document(html)
    pattern = (r"/petroleum/supply/weekly/archive/(\d{4})/\d{4}_(\d{2})_(\d{2})(?:_data)?/wpsr_[^/]+\.(?:php|html)$"
               if family == "wpsr" else
               r"/naturalgas/weekly/archivenew_ngwu/(\d{4})/(\d{2})_(\d{2})/?$")
    links = {}
    for href in document.links:
        url = urljoin(INDEXES[family], href)
        parsed = urlsplit(url)
        match = re.fullmatch(pattern, parsed.path)
        if parsed.hostname != "www.eia.gov" or not match:
            continue
        issue_hint = date(*map(int, match.groups()))
        if start_year <= issue_hint.year and issue_hint <= as_of:
            links[url.rstrip("/") + ("/" if family == "ngwu" else "")] = {"issue_hint": issue_hint}
    if family == "wpsr":
        for cells in document.rows:
            for pos, cell in enumerate(cells[:-1]):
                for href in cell["links"]:
                    url = urljoin(INDEXES[family], href)
                    if url not in links:
                        continue
                    hint = links[url]["issue_hint"]
                    release_day = cell["text"]
                    if not re.fullmatch(r"\d{1,2}", release_day):
                        continue
                    index_release = date(hint.year, hint.month, int(release_day))
                    links[url]["index_release_date"] = index_release
                    raw = cells[pos + 1]["text"]
                    # Index rows label the month. Cross-month observations are
                    # explicitly printed M/D; no weekday is inferred.
                    if re.fullmatch(r"\d{1,2}/\d{1,2}", raw):
                        month, day = map(int, raw.split("/"))
                        year = hint.year - (month > hint.month)
                    elif re.fullmatch(r"\d{1,2}", raw) and int(raw) <= index_release.day:
                        year, month, day = hint.year, hint.month, int(raw)
                    else:
                        continue
                    candidate = date(year, month, day)
                    links[url]["index_report_date"] = candidate
    if not links:
        raise ValueError(f"No dated {family} archive links in requested range")
    return links


def publication_date(text):
    values = [parse_date(value) for value in re.findall(
        rf"(?:Release\s+Date|Released)\s*:\s*({DATE_WORDS})", text, re.I)]
    if len(set(values)) != 1:
        raise ValueError("Missing or ambiguous actual document release header")
    return values[0]


def evidence_row(family, observation, publication, source, note):
    return {"evidence_id": f"eia-{family}-{publication.isoformat()}", "dataset": "eia",
            "market": "CRUDE_OIL" if family == "wpsr" else "NATURAL_GAS",
            "report_date": observation.isoformat(), "release_date": publication.isoformat(),
            "release_at": "", "status": "confirmed" if family == "wpsr" else "available_by",
            "source": source, "note": note}


def parse_wpsr(html, source, as_of, index_report_date=None, index_release_date=None):
    text = Document(html).text
    publication = publication_date(text)
    observations = {parse_date(value) for value in re.findall(
        rf"(?:for\s+)?week\s+ending\s*:?\s*({DATE_WORDS})\s*\|?\s*Release\s+Date\s*:", text, re.I)}
    fallback = False
    if not observations and index_report_date is not None:
        observations = {index_report_date}
        fallback = True
    if len(observations) != 1:
        raise ValueError("Missing or ambiguous WPSR observation header")
    observation = observations.pop()
    if publication > as_of or not 0 <= (publication - observation).days <= 21:
        raise ValueError("WPSR publication/observation date ordering is invalid")
    if index_report_date is not None and observation != index_report_date:
        raise ValueError("WPSR issue header disagrees with archive index observation")
    if index_release_date is not None and publication != index_release_date:
        raise ValueError("WPSR issue release header disagrees with archive index")
    note = ("Archived WPSR issue header establishes observation and issue release dates. "
            if not fallback else
            "Archived WPSR Released header establishes issue date; official archive index establishes observation date. ")
    note += ("PET.WCESTUS1.W is US commercial crude stocks excluding SPR; not Cushing. "
             "No historical intraday time evidenced; no first-vintage claim.")
    return evidence_row("wpsr", observation, publication, source, note)


def parse_ngwu(html, source, as_of):
    text = Document(html).text
    publication = publication_date(text)
    table = re.search(r"Working\s+(?:natural\s+)?gas\s+in\s+underground\s+storage\s+Stocks\s+"
                      r"billion\s+cubic\s+feet\s*\(bcf\)\s+Region\s+"
                      r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\s+"
                      r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\s+change\b(.*?)"
                      r"(?:Source\s*:|Data\s+source\s*:)", text, re.I)
    if not table:
        raise ValueError("Missing identifiable current working-gas storage table")
    observation, prior = parse_date(table[1]), parse_date(table[2])
    if not re.search(r"\bTotal\s+[\d,]+\s+[\d,]+\s+[−–-]?\d+\b", table[3], re.I):
        raise ValueError("Storage table has no identifiable total")
    if publication > as_of or not 0 <= (publication - observation).days <= 15 or prior >= observation:
        raise ValueError("NGWU storage table publication/observation date ordering is invalid")
    return evidence_row("ngwu", observation, publication, source,
                        "Available-by bound: archived NGWU publishes Lower48 working-gas stocks for this inventory date. "
                        "Document date is NGWU publication; original WNGSR date/time and first-vintage status not independently established. "
                        "NGWU headline week ending is not the inventory date.")


class Cache:
    def __init__(self, path, offline=False, retry_failures=False):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.offline, self.retry_failures = offline, retry_failures
        self.network_stopped = threading.Event()
        if any(json.loads(path.read_text()).get("http_status") in {401, 403, 429}
               for path in self.path.glob("*.json")):
            self.network_stopped.set()

    def seed(self, manifest):
        """Reuse previously archived successful pages with their original hashes/times."""
        for record in json.loads(Path(manifest).read_text()):
            url = record["source"]
            if urlsplit(url).hostname != "www.eia.gov":
                continue
            if "wpsr_" not in url and "/archivenew_ngwu/" not in url:
                continue
            raw_path = Path(record["path"])
            raw = (raw_path if raw_path.is_absolute() else ROOT / raw_path).read_bytes()
            if hashlib.sha256(raw).hexdigest() != record["sha256"] or len(raw) != record["bytes"]:
                raise ValueError("Seed snapshot integrity failure")
            key = hashlib.sha256(url.encode()).hexdigest()
            metadata, body = self.path / f"{key}.json", self.path / f"{key}.html"
            if metadata.exists():
                previous = json.loads(metadata.read_text())
                if previous["http_status"] == 200:
                    continue
                attempts = self.path / "attempts"
                attempts.mkdir(exist_ok=True)
                (attempts / f"{key}-{previous['sha256']}.json").write_text(metadata.read_text())
                if body.exists():
                    (attempts / f"{key}-{previous['sha256']}.html").write_bytes(body.read_bytes())
            meta = {field: record[field] for field in ("source", "retrieved_at", "sha256", "bytes")}
            meta.update(http_status=200, error="")
            body.write_bytes(raw)
            metadata.write_text(json.dumps(meta, sort_keys=True, indent=2) + "\n")

    def get(self, url):
        key = hashlib.sha256(url.encode()).hexdigest()
        metadata, body = self.path / f"{key}.json", self.path / f"{key}.html"
        if metadata.exists():
            meta = json.loads(metadata.read_text())
            raw = body.read_bytes() if body.exists() else b""
            if meta["source"] != url or hashlib.sha256(raw).hexdigest() != meta["sha256"]:
                raise ValueError("Local cached snapshot integrity failure")
            if meta["http_status"] in {401, 403, 429}:
                self.network_stopped.set()
            if meta["http_status"] in {200, 401, 403, 429} or not self.retry_failures or self.offline:
                return raw.decode("utf-8", errors="replace"), meta
        if self.offline:
            raise ValueError("Snapshot not present in offline cache")
        if self.network_stopped.is_set():
            raise ValueError("Network stopped after source denied or rate-limited archive retrieval")
        if not getattr(_THREAD, "session", None):
            _THREAD.session = requests.Session()
        try:
            response = _THREAD.session.get(url, timeout=(5, 12))
            raw, status, error = response.content, response.status_code, ""
            if status in {401, 403, 429}:
                self.network_stopped.set()
        except requests.RequestException as exc:
            raw, status, error = b"", 0, type(exc).__name__
        meta = {"source": url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                "http_status": status, "error": error}
        body.write_bytes(raw)
        metadata.write_text(json.dumps(meta, sort_keys=True, indent=2) + "\n")
        return raw.decode("utf-8", errors="replace"), meta


def write_csv(path, columns, rows, validator=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    if validator is not None:
        validator([temporary])
    temporary.replace(path)


def merge_evidence(existing, additions, quarantined_ids=()):
    """Preserve curated entries; do not silently replace a conflicting record."""
    rows = {row["evidence_id"]: row for row in existing
            if not (row["evidence_id"].startswith("eia-wpsr-index-")
                    and row["evidence_id"] in quarantined_ids)}
    for row in sorted(additions, key=lambda item: (item["evidence_id"], item["report_date"], item["source"])):
        key = row["evidence_id"]
        if key in rows:
            semantic = ("dataset", "market", "report_date", "release_date", "release_at", "status")
            if any(row[field] != rows[key][field] for field in semantic):
                # Delayed WPSR publications may contain two observation weeks.
                key += "-observed-" + row["report_date"]
                row = {**row, "evidence_id": key}
                if key in rows and any(row[field] != rows[key][field] for field in semantic):
                    raise ValueError(f"Conflicting evidence: {key}")
            else:
                continue
        rows[key] = row
    return sorted(rows.values(), key=lambda row: (row["market"], row["report_date"], row["release_date"], row["evidence_id"]))


def expand(cache, start_year, as_of, workers=3):
    sources, jobs, rows, index_rows = [], [], [], []
    for family, url in INDEXES.items():
        try:
            html, meta = cache.get(url)
            record = {**meta, "family": family + "_index", "parse_status": "ok", "evidence_ids": ""}
            if meta["http_status"] != 200:
                raise ValueError(f"Index HTTP status {meta['http_status']}")
            links = archive_links(html, family, start_year, as_of)
            jobs.extend((family, url, context) for url, context in links.items())
            if family == "wpsr":
                for issue_url, context in sorted(links.items()):
                    observation = context.get("index_report_date")
                    publication = context.get("index_release_date")
                    if observation is None or publication is None or publication > as_of:
                        continue
                    if not 0 <= (publication - observation).days <= 21:
                        continue
                    row = evidence_row("wpsr", observation, publication, INDEXES["wpsr"],
                        "Date-only evidence from official WPSR archive index Release date and Data ending columns; "
                        "issue header unverified. No inferred intraday time or first-vintage claim. "
                        "PET.WCESTUS1.W is national commercial crude stocks, not Cushing. Linked issue: " + issue_url)
                    row["evidence_id"] = "eia-wpsr-index-" + observation.isoformat()
                    index_rows.append(row)
        except ValueError as exc:
            raise ValueError(f"Cannot discover {family} archive: {exc}") from exc
        sources.append(record)

    def process(job):
        family, url, context = job
        record = {"family": family, "source": url, "retrieved_at": "", "sha256": "", "bytes": 0,
                  "http_status": 0, "parse_status": "failed", "evidence_ids": "", "error": ""}
        row = None
        try:
            html, meta = cache.get(url)
            record.update(meta)
            if meta["http_status"] != 200:
                raise ValueError(f"HTTP status {meta['http_status']}; {meta['error']}")
            row = (parse_wpsr(html, url, as_of, context.get("index_report_date"), context.get("index_release_date")) if family == "wpsr"
                   else parse_ngwu(html, url, as_of))
            if family == "ngwu" and row["release_date"] != context["issue_hint"].isoformat():
                raise ValueError("Release header disagrees with dated archive link")
            record.update(parse_status="ok", evidence_ids=row["evidence_id"], error="")
        except (ValueError, OSError) as exc:
            status = "conflict" if record["http_status"] == 200 else "failed"
            record.update(parse_status=status, error=str(exc))
            if status == "conflict" and family == "wpsr" and context.get("index_report_date"):
                record["quarantined_evidence_id"] = "eia-wpsr-index-" + context["index_report_date"].isoformat()
            row = None
        return record, row

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(process, job) for job in jobs]
        for number, future in enumerate(as_completed(futures), 1):
            record, row = future.result()
            sources.append(record)
            if row:
                rows.append(row)
            if number % 100 == 0 or number == len(jobs):
                print(f"Processed {number}/{len(jobs)} issue pages; accepted {len(rows)}", flush=True)
    verified = {(row["market"], row["report_date"]) for row in rows}
    quarantined = {row.get("quarantined_evidence_id") for row in sources if row["parse_status"] == "conflict"}
    index_only = [row for row in index_rows if (row["market"], row["report_date"]) not in verified
                  and row["evidence_id"] not in quarantined]
    rows.extend(index_only)
    next(row for row in sources if row["family"] == "wpsr_index")["evidence_ids"] = ";".join(
        row["evidence_id"] for row in index_only)
    return rows, sorted(sources, key=lambda row: (row["family"], row["source"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2011)
    parser.add_argument("--as-of", required=True, type=date.fromisoformat,
                        help="Explicit cutoff date in YYYY-MM-DD; future index links are ignored")
    parser.add_argument("--workers", type=int, choices=(1, 2, 3, 4), default=3)
    parser.add_argument("--cache", type=Path, default=ROOT / "data/eia_release_history")
    parser.add_argument("--ledger", type=Path, default=ROOT / "config/release_evidence_eia.csv")
    parser.add_argument("--manifest", type=Path, default=ROOT / "config/eia_history_sources.csv")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--seed-manifest", type=Path, help="Reuse a prior local retrieval manifest after checksum verification")
    parser.add_argument("--retry-failures", action="store_true",
                        help="Single retry of cached transient errors; denied/rate-limited responses are never retried")
    args = parser.parse_args(argv)
    if args.start_year < 1996 or args.start_year > args.as_of.year:
        parser.error("start-year must be between 1996 and the cutoff year")
    from src.research_audit import load_evidence
    existing = load_evidence([args.ledger])
    cache = Cache(args.cache, args.offline, args.retry_failures)
    if args.seed_manifest:
        cache.seed(args.seed_manifest)
    additions, sources = expand(cache, args.start_year, args.as_of, args.workers)
    quarantined_ids = {row.get("quarantined_evidence_id") for row in sources if row["parse_status"] == "conflict"}
    merged = merge_evidence(existing, additions, quarantined_ids)
    write_csv(args.ledger, COLUMNS, merged, validator=load_evidence)
    write_csv(args.manifest, SOURCE_COLUMNS, sources)
    failures = sum(row["parse_status"] != "ok" for row in sources)
    summary = {"as_of": args.as_of.isoformat(), "start_year": args.start_year,
               "accepted_evidence_rows": len(additions), "failed_issue_documents": failures,
               "existing_rows_before_expansion": len(existing),
               "quarantined_index_rows": len(quarantined_ids - {None}), "ledger_rows": len(merged)}
    (args.cache / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
