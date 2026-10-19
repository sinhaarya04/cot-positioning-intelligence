# EIA release evidence and archive coverage

Reviewed October 18, 2026 (America/New_York), with an explicit evidence cutoff of
2026-10-18. Snapshots were retrieved October 19 in UTC. The date ledger is
[config/release_evidence_eia.csv](../config/release_evidence_eia.csv); its source
hashes, retrieval times and failures are in
[config/eia_history_sources.csv](../config/eia_history_sources.csv).

The expansion preserves the original nine pilot records and adds dated archive
evidence. It contains **797 rows: 792 crude-inventory observations and five
natural-gas observations**. Every `release_at` remains empty. These are dates or
availability bounds, not verified intraday timestamps or first-release values.

## What is established

| Evidence | Observation dates | Accepted rows | Interpretation |
| --- | --- | ---: | --- |
| WPSR issue headers | Subset of the range below | 221 | The archived issue pairs its inventory observation and actual release date; checked against the index when available |
| WPSR archive index | Remaining observations from 2011-07-29 through 2026-10-09 | 571 | Explicit `Release date` and `Data ending` columns establish date-only evidence; individual issue header unverified |
| NGWU storage tables | 2023-02-17, 2023-02-24, 2023-03-03, 2024-11-08, 2024-11-15 | 5 | The inventory was documented **by** the NGWU publication date; original WNGSR release date/time is not established |

The WPSR ledger covers each Friday observation in the inspected index range
except **2026-06-19 and 2026-10-02**, which are quarantined because the downloaded
issue and index conflict. This is coverage of the currently inspected archive,
not proof of historical first-vintage completeness.

| Observation year | Accepted WPSR dates |
| --- | ---: |
| 2011, from July 29 | 23 |
| 2012–2015 | 52 in each year |
| 2016 | 53 |
| 2017–2020 | 52 in each year |
| 2021 | 53 |
| 2022–2025 | 52 in each year |
| 2026, through October 9 | 39 |

The archive index is itself a dated public record, and its provenance is kept
separate from issue-header verification. For example, its entries explicitly
pair the 2022-06-17 observation with June 29 publication and the 2023-11-03
observation with November 15 publication. Their URLs contain `_data` and use the
observation date. The parser reads the printed release-day cells; it does not
assume that a URL date or the usual weekday is the publication date.

## Fetch failures and contradictory records

The reproducible discovery pass found 794 WPSR issue links and 730 NGWU issue
links. Two index snapshots plus these issue records produce **1,526 source
manifest rows**. Of the 1,524 issue records:

- 226 contain successfully parsed documents: 221 WPSR and five NGWU.
- 1,285 have cached HTTP 403 responses: 560 WPSR and 725 NGWU.
- Nine WPSR requests have cached transport failures.
- Two delayed WPSR pages are absent from the offline cache; their index evidence
  is retained without claiming to have downloaded the issue.
- Two downloaded WPSR pages contain conflicting or invalid date evidence and
  have `parse_status=conflict`, with an explicit `quarantined_evidence_id`.

The [June 24, 2026 issue](https://www.eia.gov/petroleum/supply/weekly/archive/2026/2026_06_24/wpsr_2026_06_24.php)
says that data end June 19 but gives a release date of June 14, before the
observation. The
[October 7, 2026 issue](https://www.eia.gov/petroleum/supply/weekly/archive/2026/2026_10_07/wpsr_2026_10_07.php)
contains a September 25 observation and September 30 release header, while the
index pairs October 2 with October 7. Neither index row is admitted to the
confirmed ledger. Reruns also remove previously generated index fallback rows
for these quarantined observations; curated pilot entries are preserved.

Access-denied responses were encountered during expansion, so a complete gas
history was **not** obtained. The final downloader stops further network requests
when it encounters HTTP 401, 403 or 429, reuses cached pages, and never retries
cached denied or rate-limited responses. No denied pages were retried. Historical
NGWU coverage remains a research-data blocker, and holidays also cause genuine
missing NGWU editions. Its archive cannot be treated as a complete WNGSR calendar.

## Match the evidence to the configured series

| Market | Configured series | Inventory concept |
| --- | --- | --- |
| `CRUDE_OIL` | `PET.WCESTUS1.W` | U.S. commercial crude-oil stocks excluding SPR, thousand barrels |
| `NATURAL_GAS` | `NG.NW2_EPG0_SWO_R48_BCF.W` | Lower 48 working natural gas in underground storage, Bcf |

The crude series is national inventory, **not Cushing inventory**. The official
[EIA series page](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=WCESTUS1&f=W)
establishes this identity. The proposed Cushing storage-state interaction needs a
separate numerical series and its own audit. This expansion changes neither
inventory values nor the database's release metadata.

NGWU's headline week describes market commentary, typically through Wednesday.
The relevant inventory observation is the date in the **working-gas storage
table**. The parser uses that table, checks that observation precedes publication,
and requires an identifiable total. It does not use the headline or reconstruct
the Friday by subtracting days. A dated table in an NGWU document establishes an
upper bound on availability, not the original WNGSR publication instant.

## Revisions remain a separate problem

The archived [November 14, 2024 NGWU](https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/2024/11_14/)
shows 3,974 Bcf for November 8. The prior-week column in the
[November 21 issue](https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/2024/11_21/)
shows 3,972 Bcf for the same observation. Both source snapshots are preserved;
neither value has been promoted to a first-release database value.

EIA's [2024 sample-reselection notice](https://ir.eia.gov/ngs/faqsamplechanges2024.html)
announced revisions to eight observation weeks, September 20 through November 8.
Its inconsistent November 14/15 wording for the next observation does not
supersede the November 21 issue's table, which explicitly uses November 15.
The [WNGSR revision policy](https://ir.eia.gov/ngs/revisions.html) permits routine
and out-of-cycle revisions. Attaching an old release date to a current API value
therefore does not reconstruct what a forecaster saw then.

A future vintage table needs observation date, document publication date, value,
series identity, retrieval time, content hash and revision relationship. The
[WNGSR methodology](https://ir.eia.gov/ngs/methodology.html) also documents the
2002 transition from AGA to EIA and the 2015 transition to five reporting regions;
retrospective regional histories need separate checks.

## Reproduce and inspect

Run from a repository checkout:

```sh
python -m src.expand_eia_history --as-of 2026-10-18 --workers 3
```

The command discovers actual links in the official indexes, filters future links,
uses no more than four workers, and writes raw pages plus retrieval metadata
under ignored `data/eia_release_history/`. It records failures instead of guessing
dates. Exit status 2 means the ledger was written but issue-level gaps remain;
it does not mean the entire history was verified. The command never writes to
DuckDB or promotes date-only evidence into the timestamp-based evaluation path.

To reproduce the completed local expansion without network access:

```sh
python -m src.expand_eia_history --as-of 2026-10-18 --offline \
  --seed-manifest data/release_evidence_eia/manifest.json
```

The optional seed manifest reuses earlier pilot snapshots after checking their
hashes and original retrieval metadata. Raw snapshots are local and are not
included in Git, so a fresh checkout does not have an offline cache. The tracked
manifest records what was retrieved, what was rejected, and which generated
index IDs are quarantined. SHA-256 identifies retrieved content; it does not
prove the historical publication instant or prevent later revision of the
provider's archive.

Tests cover holiday and delayed publications, `_data` archive paths, malformed
index HTML, misleading headline dates, conflicting/invalid source pairs,
quarantine across reruns, missing headers, cache integrity, access denial and
preservation of curated records. The next data task is obtaining original WNGSR
history and archived numerical values, while adjudicating the two contradictory
WPSR records. Until then, these dates support a coverage audit rather than a
first-vintage forecasting claim.
