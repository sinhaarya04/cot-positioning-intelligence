# Existing natural-gas contract workbook

Inspected read-only on 18 October 2026 (America/New_York). A local workbook named `natgasfutures_prices.xlsx` was found in the author's earlier commodity research project. The original file was unchanged. This note records aggregate diagnostics; the workbook and its prices are not redistributed.

| Check | Result |
|---|---|
| Worksheet | `Sheet1` |
| Individual security headers | 216 unique columns, `NGF15 Comdty` through `NGZ32 Comdty` |
| Dated rows | 4,081 unique dates, 2014-12-01 through 2026-02-01 |
| Numeric price observations | 375,015 across all 216 security columns |
| Dates containing numeric prices | 2014-12-01 through 2026-01-30 |
| Literal provider error cells | 246,511 cells containing `#N/A N/A` |
| Blank price cells on dated rows | 259,970 |
| Negative / zero numeric prices | 0 / 0 |
| Weekend numeric prices | 0 |
| Stored formulas | None in the price cells |
| Original price field | Unknown |
| Contract expiry metadata | Absent |

Source SHA-256: `26f138f0ed29806729fe3d756822aff2a68d686d3485970ed703729583296b59`.

Counts cover the entire dated sheet, including its first price row. Date range alone does not establish complete trading-session coverage. The provider errors and blanks mix dates outside a contract's life with potentially missing observations; neither is automatically a missing settlement or a zero. Security names resemble Bloomberg individual futures identifiers, but the saved values alone do not authenticate their source, delivery year resolution or price field.

The May 2020 column, `NGK20 Comdty`, has 1,362 numeric observations from 2014-12-01 through 2020-04-28. Its last observed price is not used as expiry evidence. The final column, `NGZ32 Comdty`, contains observations from 2019-11-27 through 2026-01-30; future delivery years are consistent with a curve panel and do not mean future observations were downloaded.

## What to resolve in the Bloomberg lab

1. Locate the original query workbook or acquisition notes to identify the historical field and options. If unavailable, retrieve a new `PX_SETTLE` sample for overlapping securities/dates. Agreement on a few rows is a diagnostic, not proof of the original field across the full file.
2. Resolve exact security identities and obtain delivery months, actual last-trade dates, units and multipliers. Do not infer expiry from the last nonmissing observation.
3. Confirm permitted research use and storage of this existing file. Preserve errors and missing cells in the raw source; normalize only supported observations after provenance is resolved.
4. Obtain missing early gas history for the proposed 2009-onward sample and refresh later observations only through completed sessions. Crude oil still needs an individual-contract panel.

The [lab guide](bloomberg-export-guide.md) provides the six-contract acquisition pilot and required metadata. The local inspection also produced per-contract coverage and a 216-security metadata-request CSV under the ignored `output/local-contract-audit/` directory. These are diagnostic aids, not an accepted contract package. No rows from this workbook have been imported as settlements or admitted to an experiment.

A separate local crude-oil CSV contains only `Date,Last Price` and no individual contract identity. It cannot supply the required crude contract panel.
