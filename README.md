# COT Positioning Intelligence

An auditable Python pipeline for CFTC positioning data, EIA inventories, descriptive signals, and conditional forward-return analysis across eight commodity markets.

**Research status:** the old README's numerical performance claims have been withdrawn because they were not supported by a reproducible, correctly timed evaluation. The corrected code is a research foundation. Its current continuous-price analysis is not an executable strategy or evidence of alpha.

## Working paper and research documents

**[What Does a COT Release Add? Public Positioning and Risk in Energy Futures](docs/working-paper.md)** is the current preliminary research-design and methods draft. It separates implemented software from the proposed forecasting experiment. Empirical results remain pending; this is not a completed or peer-reviewed empirical paper.

- [Working-paper draft](docs/working-paper.md): research question, related work, hypotheses, proposed methods and outstanding evidence.
- [Original research proposal (PDF)](docs/research-proposal.pdf): the 15 October 2026 planning brief, preserved as written before the correction pass. Its code-audit roadmap describes the earlier repository state; use this README and the working-paper draft for current implementation status.
- [Validation record](docs/validation.md): engineering checks and live-data coverage, with no performance claims.

The intended contribution is the incremental forecasting information in a newly released COT report beyond a prespecified public-information baseline. Novelty and publication readiness still require empirical evidence and a fuller review of the closest papers.

## What the pipeline does

- Ingests Legacy and Disaggregated **futures-only** COT for gold, silver, crude oil, natural gas, corn, wheat, soybeans and copper. TFF parsing is available, but these physical commodities do not have TFF coverage.
- Validates required fields, integer counts, identity and position totals; missing source fields cannot silently become zeros. Invalid provider records fail with their market/date.
- Archives source responses with content hashes, retrieval times and credential redaction.
- Stores observation dates separately from sourced release timestamps. Missing publication evidence remains unknown; no automatic Tuesday-to-Friday assumption is used.
- Computes rolling min-max COT indices, z-scores, calendar-based positioning changes, divergence, managed-money positioning, and an exploratory inventory interaction.
- Evaluates conditional underlying returns using prior-only thresholds and explicit entry/exit dates, with same-period baseline statistics and an event-level audit CSV.
- Provides a Streamlit dashboard and an optional, strictly validated LLM explanation layer.

## Install

Python 3.13 is the locked/tested environment; project metadata supports Python 3.12+.
Run the documented commands from the cloned repository checkout. The current pipeline resolves configuration and provenance files relative to that checkout; standalone wheel deployment is not supported.

```bash
git clone https://github.com/sinhaarya04/cot-positioning-intelligence.git
cd cot-positioning-intelligence
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pytest -q
```

Alternatively, with uv: `uv venv --python 3.13` followed by `uv pip sync requirements.lock`.
The lockfile includes the application and test dependencies. GPU/model packages are optional: `python -m pip install '.[llm]'` when needed. Optional LLM dependencies are not part of the core lockfile.

## Configuration and publication evidence

The EIA key must be supplied as `EIA_API_KEY` in the environment. Get a replacement from [EIA](https://www.eia.gov/opendata/register.php). A key appeared in earlier commits; **removing it from current source does not revoke it or remove it from Git history**. Rotate/revoke that exposed key through its provider account. Do not paste it into Python files or issue reports.

`.env.example` documents optional variables; it is not loaded automatically. Optional paths are `COT_DB_PATH` and `COT_RAW_DIR`. `COT_START_DATE` restricts CFTC observation history, and `COT_RELEASE_CALENDAR` identifies a sourced CSV with:

| Column | Meaning |
|---|---|
| `dataset` | `legacy`, `disagg`, `tff`, or `eia` |
| `market` | Configured market name; `*` means the same release applies to all markets in that dataset |
| `report_date` | Observation date in `YYYY-MM-DD` format |
| `release_at` | Actual publication timestamp with an explicit UTC offset |
| `source` | URL documenting that publication date/time |

Copy the header-only `config/release_calendar.example.csv` and populate it from verified evidence. Market-specific rows override `*` rows. Duplicate keys, naive timestamps and publication dates before observation dates are rejected. The software checks the format; the supplied source still needs human verification. `release_quality=verified` means evidence was supplied in this calendar, not that the software independently authenticated the URL.

Use the [CFTC release schedule](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm), [exception announcements](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm), [EIA petroleum archives](https://www.eia.gov/petroleum/supply/weekly/archive/) and [gas storage reports](https://ir.eia.gov/ngs/ngs.html). Observation-date archives are not release calendars. Holidays and exceptional delays must be recorded explicitly.

Disaggregated reports began publication in September 2009; the 2006-2009 history was backfilled later. Do not assign those observations contemporaneous release dates. Current API values are labelled `latest` vintage even when release dates are known: a sourced date does not establish that a downloaded historical value is the original first release.

```bash
export COT_RELEASE_CALENDAR=/absolute/path/to/verified-releases.csv
# Set EIA_API_KEY through your local environment or secret manager.
```

Ingestion works without a calendar for descriptive inspection, but corrected evaluation excludes records without release evidence. No guessed calendar is bundled.

## Run

Full pipeline with an explicit research-era start:

```bash
python -m src.pipeline --start-date 2009-09-01
```

For CFTC and prices without EIA credentials:

```bash
python -m src.pipeline --start-date 2009-09-01 --skip-eia
```

Without enough verified release history, data/features are saved and the pipeline exits **2** with an actionable message; provider/validation failures exit **1**. Each run writes an `output/run-*.json` manifest with source hash, Git commit, package versions, scope, status and coverage, plus an event audit when signals exist. `--skip-eia` omits the network stage; it does not delete previously ingested inventory.

Individual stages:

```bash
python -m src.db
python -m src.ingest_cftc --start-date 2009-09-01
python -m src.ingest_prices --skip-eia
python -m src.availability --calendar /absolute/path/to/verified-releases.csv
python -m src.signals
python -m src.backtest
streamlit run src/dashboard.py
```

To ingest EIA too, omit `--skip-eia` after configuring its key. Price ingestion accepts `--markets CRUDE_OIL NATURAL_GAS` for a smaller download. Recompute existing inputs with `python -m src.pipeline --skip-ingest`.

Without `--start-date` or `COT_START_DATE`, CFTC ingestion requests all provider history. One verified upstream issue is a negative nonreportable-long count in crude-oil Legacy data on 1987-02-27. The strict parser rejects it instead of changing it. Restrict scope explicitly or investigate the source; do not silently drop bad observations.

## Evaluation semantics

The names `1w`, `2w`, and `4w` currently mean **5, 10, and 20 later observed daily sessions**. They are retained for display compatibility.

- Yahoo downloads use daily, unadjusted continuous close proxies. Intraday timestamps and contract identities are unavailable. Entry excludes the entire New York publication date and uses the first subsequent daily bar.
- Timestamped settlement inputs require a timestamp strictly after release. The engine does not implement contract selection or rolled portfolio P&L.
- Exits are counted from the actual selected entry. Four-calendar-day price-gap checks reject stale/weekly series; they are not a full exchange-calendar validation.
- Tail thresholds use at least 50 strictly earlier, verified signal observations. Reports released in the same batch cannot set one another's thresholds. At least 10 completed tail outcomes are required for a summary.
- `positive_return_rate` is the fraction of underlying returns above zero. `mean_over_std` is a descriptive ratio, **not a strategy Sharpe**. Baselines use the same signal's eligible evaluation dates.
- Missing or nonpositive prices anywhere in a holding window are excluded from percentage-return analysis and recorded in the event audit. A contract-dollar P&L engine is still needed for negative prices.
- The audit includes release/entry/exit dates, thresholds, source labels and exclusion reasons. Outcomes may overlap; no standard errors, significance claims, costs, margin or portfolio performance are produced.

The 52/156 COT-index windows count available report observations and use rolling min-max normalization, not percentile ranks. Four-week momentum requires the exact earlier calendar observation. Inventory joins use verified publication times backward from the decision time. The inventory interaction is a rolling level z-score multiplied by a positioning z-score; it is **not** an inventory surprise, seasonal tightness estimate or directional crowding signal.

## Data safety and freshness

Schema migrations are additive. Old rows are marked unknown/legacy. Inserts name columns explicitly and replace keys in transactions; failed inserts roll back deletions. Empty writes preserve prior data. A refresh with no new calendar match preserves an existing verified release timestamp.

Successful input changes mark dependent signals, results and explanations stale in the same transaction. The dashboard hides obsolete outputs until they are recomputed. Current results are still descriptive latest-vintage analyses. Original release vintages require a separate archive reconstruction.

The dashboard shows the latest row **per market**, report age, publication quality and dated model outputs. It can start with an empty database. Optional model explanations are excluded from the scientific forecasting test; their directional scores and confidence are uncalibrated opinions. Model packages load only on explicit invocation:

```bash
python -m src.llm_anomaly
```

Set `COT_LLM_MODEL_REVISION` to a fixed revision for reproducible model runs. Model name, resolved revision, prompt version, generation settings and timestamp are stored with validated explanations.

## Research work still required

1. Reconstruct and audit release calendars and original data vintages, with documented uncertainty.
2. Obtain contract-level price, expiry, multiplier and curve data with appropriate usage rights.
3. Implement seasonal inventory tightness, price/curve/volatility baselines and the prespecified incremental-COT quantile experiment.
4. Add chronological model selection, dependence-aware uncertainty, cost/roll accounting and prospective forecast records.
5. Generate reproducible manuscript tables and figures. No prior numerical performance claim should be reused without re-estimation.

## Layout

`src/availability.py` validates release calendars; `src/provenance.py` archives responses;
`src/ingest_cftc.py` and `src/ingest_prices.py` ingest inputs; `src/db.py` manages schema and transactional writes;
`src/signals.py` is the single signal implementation; `src/backtest.py` produces descriptive evaluations;
`src/pipeline.py` saves run manifests; `src/dashboard.py` displays results; `src/llm_anomaly.py` is optional.
Root `signals.py` is a compatibility wrapper. `tests/` contains offline regression and Streamlit smoke tests.

CI runs the locked Python 3.13 test suite. To refresh the lock deliberately:
`uv pip compile pyproject.toml --extra dev --python-version 3.13 --output-file requirements.lock`.
