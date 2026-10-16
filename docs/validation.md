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
