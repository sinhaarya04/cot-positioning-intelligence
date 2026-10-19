# Engineering validation record

This record documents software verification. It does not establish return predictability, trading profitability or publication readiness.

## Offline regression suite

The corrected pipeline passed **141 tests** in the locked local Python 3.13.11 environment. Coverage includes source-field mapping, malformed and missing data, pagination, atomic rollback, publication-time joins, future-data invariance, same-release-batch exclusion, stale-output invalidation, daily-price preservation, LLM output validation, and fresh/populated Streamlit startup.

Reproduce the offline suite from the repository root:

```bash
python -m pip install -r requirements.lock
python -m pytest -q
```

The suite uses isolated temporary databases and mocked external requests. The optional LLM was not downloaded or executed. The GitHub Actions workflow runs the same suite on Python 3.13; a local passing run does not by itself establish that remote CI has passed.

## Live data check

A separate local validation database was populated on **16 October 2026 UTC** (15 October in New York). CFTC ingestion used an explicit observation-date lower bound of `2009-09-01`. EIA checks used its public demonstration key, not the previously exposed user credential.

| Dataset | Crude oil rows | Natural gas rows | Observed coverage |
|---|---:|---:|---|
| Legacy futures-only COT | 893 | 893 | 2009-09-01 to 2026-10-06 |
| Disaggregated futures-only COT | 893 | 893 | 2009-09-01 to 2026-10-06 |
| Yahoo daily close proxies | 6,565 | 6,562 | Crude: 2000-08-23 onward; gas: 2000-08-30 onward; both through 2026-10-15 |
| EIA inventory observations | 2,298 | 876 | Crude: 1982-08-20 onward; gas: 2010-01-01 onward; both through 2026-10-09 |

The resulting feature computation produced **1,786 descriptive signal rows**. No verified publication calendar was supplied, so **zero rows were eligible for corrected return evaluation and zero return summaries were produced**. The run status was `needs_release_evidence_or_history`. This is the expected fail-closed behavior.

Raw data, local databases and event-level exports are not included in the repository. Their redistribution and historical-vintage suitability have not been established. Each new pipeline run writes its own local manifest and source-response archive; live-source coverage can change.

## Source quality findings

The full crude-oil Legacy history contains an upstream negative nonreportable-long count for `1987-02-27`. Strict parsing rejects that observation with its identity rather than silently replacing it. The explicitly scoped research-era data passed validation. A bounded research sample is not a claim that the complete historical source is clean.

## Remaining empirical requirements

- Sourced actual publication dates and an audit of original versus revised values.
- Contract-level prices, maturities, multipliers and roll/cost handling.
- Implementation and evaluation of the prespecified incremental-information models in the working-paper draft.
- Dependence-aware uncertainty estimates and a prospective forecasting record.

No synthetic test result or ingestion count should be reported as a financial result in the manuscript.

## Release-evidence audit follow-up

On 18 October 2026 (America/New_York), the added read-only audit matched eight confirmed CFTC publication dates per market/report type, six crude-inventory issue dates and three secondary gas-publication available-by bounds against this same validation database. There are no exact timestamps in the pilot. No database metadata, signal eligibility or evaluation output was changed.

The expanded suite passed **170 tests**, including date precision, daylight-saving boundaries, conflicting evidence, superseded schedules, conservative pre-release joins, input/output collision protection and database preservation. See the [audit report](research-data-audit.md) for coverage and remaining limitations. These checks establish diagnostic behavior, not readiness for the forecasting experiment.

## History expansion and contract acquisition

The 18 October 2026 follow-up passed **275 tests** in the locked Python 3.13 environment. New coverage includes reviewed CFTC notices and catch-up tables, EIA issue/index date extraction, contradictory-source quarantine, cache integrity and replay, persistent access-denial handling, and a separate contract-export importer. The importer tests signed settlements, exact identifiers and Bloomberg ticker/metadata consistency, expiry months, acquisition-date bounds, duplicates, provider error strings, immutable source copies and cleanup after failed writes.

The expanded read-only audit matches 16 Legacy and 17 Disaggregated publication dates per study market, plus three available-by observations for each report type. It matches 792 crude inventory dates and five gas available-by observations. All bundled evidence remains date-only. Both history expanders reproduce their ledgers from preserved local snapshots; EIA replay also reproduces its source manifest byte-for-byte. Source denial and contradictory documents remain visible rather than being repaired with assumed publication dates.

The validation database SHA-256 is unchanged before and after the expanded audit: `aac489f907df514d465f294ec66520f8fe5b0d224fd638a3dc57b4e5a341f564`. Existing evaluation eligibility remains zero. An existing natural-gas workbook was inspected read-only; its original field and expiry metadata remain unresolved, and no real prices were imported into the new package format. These are software and provenance checks, not an executed forecasting experiment.
