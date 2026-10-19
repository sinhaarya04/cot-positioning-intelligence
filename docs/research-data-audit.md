# Release evidence and research-data feasibility

Audited 18 October 2026, America/New_York. **A research-ready common sample has not been established.** This first audit delivers a bounded, sourced pilot and a repeatable way to measure the gaps before fitting the proposed forecasting models.

## What is now available

- [CFTC ledger](../config/release_evidence_cftc.csv) and [source review](cftc-release-evidence.md): eight actual publication dates, ordinary releases, a Monday holiday observation and four ION-delayed reports. Schedules and superseded schedules remain separate.
- [EIA ledger](../config/release_evidence_eia.csv) and [source review](eia-release-evidence.md): six petroleum issue dates and three secondary gas-document dates that establish availability bounds.
- [Contract-data specification](contract-data-feasibility.md): required contract identities, prices, expiries, timing, curve coverage and access checks.
- `src/research_audit.py`: an offline, read-only diagnostic with input hashes and observation-level evidence classifications.

There are 31 ledger records: 22 confirmed date records, three available-by records, four scheduled records and two superseded records. CFTC dates are represented separately for Legacy and Disaggregated reports and apply to matching markets; these counts do not represent 31 independent release events. All `release_at` fields are blank.

## Reproduce the diagnostic

Use an existing database created by the documented pipeline, or a checkpointed research snapshot. The local validation snapshot is not distributed with the repository.

```bash
python -m src.research_audit --db data/cot_intelligence.duckdb
# To audit the prior local validation snapshot, when present:
python -m src.research_audit --db data/validation.duckdb --output-dir output/research-audit
```

The tool creates three local outputs:

| File | Contents |
|---|---|
| `research-audit.json` | Database, code and ledger hashes; source coverage; declared vintages; price types; conservative inventory-date overlap; limitations |
| `release-coverage.csv` | Every CFTC/inventory observation in the two study markets, including evidence IDs, classification, bounds and metadata conflicts |
| `research-audit.md` | Human-readable coverage summary |

The command does not fetch data, create a missing database, apply a calendar, compute forecasts or modify stored metadata. It refuses an active WAL snapshot and input/output path collisions. Missing tables are reported. Exit zero means the audit ran successfully, not that the research sample passed a readiness gate.

## Precision and conflict rules

The ledger columns are `evidence_id,dataset,market,report_date,release_date,release_at,status,source,note`. URLs and notes support manual review; syntax validation does not independently authenticate source claims.

| Status | Interpretation |
|---|---|
| `confirmed` | Source explicitly establishes the actual publication date. An exact timestamp may be supplied only with separate supporting evidence. |
| `available_by` | An EIA secondary issue contains the observation. `release_date` is that document's publication date; the original report date/time remains unknown. |
| `scheduled` | Intended publication only, even if the scheduled date is in the past. |
| `superseded` | A historical schedule replaced by another announcement. |

A confirmed date is represented by the interval from midnight to the following midnight in `America/New_York`, including daylight-saving transitions. Its upper endpoint is exclusive. An available-by document supplies only that exclusive upper bound, with no inferred lower bound or original release date. Neither representation becomes an exact `release_at`.

Different confirmed dates or timestamps produce a conflict. Confirmed original releases that contradict an earlier available-by document also produce a conflict. Market-specific confirmed evidence takes precedence over wildcard evidence. Planned records never override confirmed evidence. Contradictory existing database timestamps are flagged and excluded from the overlap diagnostic.

For inventory overlap, the tool selects the newest evidenced observation known strictly before the earliest possible COT publication time. Date bounds ending exactly at that cutoff qualify because their upper endpoint is exclusive; exact simultaneous publication timestamps do not qualify. Same-day date-only inventory is conservatively unavailable. The report exposes inventory age and does not assume freshness. This check establishes timing overlap only: numerical values, original vintages, features and price targets remain unaudited.

These ledgers are intentionally separate from the pipeline's exact-timestamp release calendar. Do not copy a bound into that calendar or label it an observed publication instant.

## Results on the existing validation snapshot

The audit used the database from the earlier engineering validation, without re-downloading or modifying it. Its SHA-256 was `aac489f907df514d465f294ec66520f8fe5b0d224fd638a3dc57b4e5a341f564`. Coverage is conditional on this deliberately small ledger; missing evidence here does not imply that historical publication did not occur.

| Dataset | Market | Stored rows | Confirmed date evidence | Available-by only | Without usable evidence |
|---|---|---:|---:|---:|---:|
| Legacy | Crude oil | 893 | 8 | 0 | 885 |
| Legacy | Natural gas | 893 | 8 | 0 | 885 |
| Disaggregated | Crude oil | 893 | 8 | 0 | 885 |
| Disaggregated | Natural gas | 893 | 8 | 0 | 885 |
| EIA inventories | Crude oil | 2,298 | 6 | 0 | 2,292 |
| EIA inventories | Natural gas | 876 | 0 | 3 | 873 |

The four evidenced 2023 delayed COT releases have earlier inventory-publication evidence in both markets. At the 8 March COT release, the date-only 8 March petroleum issue cannot enter a pre-release baseline: the prior evidenced inventory observation is 12 days old. The other three delayed-release comparisons use seven-day-old inventory observations. These are timing checks, not eight independent forecasts or financial results.

All stored raw inputs still declare latest vintage; the pilot has no exact publication timestamps. Price coverage remains 6,565 crude and 6,562 gas daily continuous proxies. No existing signal became eligible through this audit.

## Findings that affect the research design

1. **Series identity:** current crude ingestion uses U.S. commercial stocks excluding SPR, not Cushing stocks. The proposed seasonal-state test needs its own Cushing series and source/vintage audit.
2. **Revisions:** the archived gas issues reviewed in the [EIA evidence note](eia-release-evidence.md) show different quantities for the same 8 November 2024 observation. Current API values plus historical publication dates cannot establish the original information set.
3. **Warmup:** current gas history starts in 2010. Five past years for seasonality and five further years of complete-feature training can push the seasonal-interaction evaluation toward 2020. Earlier comparable vintages or a shorter declared evaluation period must be assessed explicitly.
4. **Prices:** the current table cannot represent multiple contracts, expiry selection, price revisions or a curve. Contract data access and permitted research use remain unverified.

The 170-test suite checks the new diagnostic and prior pipeline behavior. The database hash before and after auditing is identical. No forecasting experiment, common-sample sufficiency or economic effect is asserted.

## Next acceptance gates

Expand documented release evidence and reconcile archived values over a declared contiguous period, preserving uncertainty rather than filling missing dates mechanically. Resolve contract-data access with a representative CL/NG sample that includes expiry changes, holidays and April 2020. Then calculate the common usable period and chronological training/evaluation windows.

Proceed to the primary M0-versus-M1 experiment only after those inputs support the proposed targets and timing rules. Keep the seasonal M2 extension separate until its series and warmup constraints are resolved. If original vintages remain incomplete, narrow the claim explicitly and report latest-vintage results separately. A nonempty overlap table alone is not a go decision.
