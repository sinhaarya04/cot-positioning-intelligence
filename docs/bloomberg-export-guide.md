# Bloomberg lab visit: CL and NG contract data

Updated 19 October 2026 for the public-news/disclosure comparison. This is an acquisition checklist, not evidence that a Bloomberg account, historical field, export entitlement or complete sample has been tested. Start with the small pilot below. The objective is individual NYMEX WTI crude oil and Henry Hub natural gas futures, with identified delivery months and daily settlements.

## Exact acquisition target for the revised experiment

**First priority: individual-contract daily settlements and contract metadata for both markets.** The initial feasible specification uses public inputs available by Wednesday 00:00 New York (the Tuesday snapshot) and by 00:00 on the actual COT release date (normally the Thursday snapshot). All risk forecasts are issued after actual publication for the same subsequent contract outcome. Daily data support this conservative version; they do not establish the value of a report against every piece of information available immediately before Friday's announcement.

### Required Bloomberg price package

| Item | Exact request | Why it is needed |
|---|---|---|
| Markets | Standard NYMEX WTI crude oil futures, root CL; standard NYMEX Henry Hub natural gas futures, root NG; individually identified delivery contracts | Matches the two study markets and permits holding the same contract |
| Trade-date range | 1 January 2008 through the last fully completed exchange session at the visit | A price-history buffer for 50-week momentum/volatility features before the post-September-2009 disclosure study; earlier prices do not make backfilled COT contemporaneously public |
| Maturity coverage | Contracts needed to represent the first twelve listed monthly maturities on each historical date, including expired contracts and future delivery years at the end of the sample | Supports expiry selection and curve construction; twelve is an acquisition envelope, not twelve independent COT observations or twelve frozen model features |
| Contract histories | Each resolved contract's available daily history within the requested date range; do not limit its history to its delivery year | Supplies same-contract history and overlapping maturities |
| Price | Official daily settlement, `PX_SETTLE`, with exchange trade date | Constructs outcomes, price changes, volatility and curve spreads |
| Identity and expiry | Exact Bloomberg security, stable ID if available, market/exchange, full delivery year/month, actual last-trade date, first-trade/listing date if available | Prevents decade ambiguity, continuous-series rolls and use of unlisted maturities |
| Units | Currency, quote unit, contract size and dollar multiplier; tick size as supplementary metadata | Converts signed price changes into consistent contract-dollar outcomes |
| Calendar | Historical NYMEX energy trading sessions, holidays, early closes and timezone | Counts the five-session horizon and ten-sessions-to-expiry rule |
| Query/field evidence | Original formulas, date/frequency/missing-value options, exact returned field names and definitions, retrieval time, settlement status and historical availability documentation | Establishes what each value means and which snapshot may use it |

The first-twelve target is a coverage request, not permission to use generic `CL1`–`CL12` or `NG1`–`NG12` without the underlying individual identities. If quotas constrain collection, validate the six-contract pilot first and request a coverage estimate for the full panel before batching. Do not silently replace the target with a shorter curve or sample.

**Request daily volume and open interest alongside settlements if available.** They strengthen the public comparator, but the importer allows missing values. Save their observation dates, publication timing and revision conventions. A trade-date label does not mean the final count was known that day. Unknown availability means excluding or conservatively lagging that field under a frozen rule, never treating it as available by default. Do not sum the first twelve contracts' open interest and call it the all-maturity COT denominator.

### Release information: ask for coverage and one original example first

These are required research inputs, but do not all need to be acquired from Bloomberg. Official CFTC/EIA archives are the primary route; the lab is useful if it provides original issues, timestamps or better historical coverage.

| Dataset | Values and event linkage needed | Date range |
|---|---|---|
| COT, Disaggregated futures-only | NYMEX WTI code `067651` and NYMEX Henry Hub code `023651`; managed-money long and short counts, total open interest, observation date, actual release date/time if evidenced, first-release values and corrections, publication-batch identity | September 2009 onward for the primary public-availability study; save any earlier backfill separately with its actual release evidence |
| COT, Legacy futures-only controls | Same markets; commercial long and short counts and total open interest, with original releases/availability | Request 2008 onward where available to support lagged public controls |
| EIA crude inventory | U.S. commercial crude stocks excluding the Strategic Petroleum Reserve, level and reported weekly change; observation week, actual issue date/time, units, values as first reported and revisions | Request 2008 onward, preserving actual available coverage |
| EIA gas inventory | Lower-48 working gas in storage, level and reported weekly net change; observation week, actual issue date/time, Bcf units, values as first reported and revisions | Request 2008 onward, preserving actual available coverage |

Preserve the previous-period figure printed in each inventory issue as well as the reported change. If that prior level was revised, subtracting two first-release levels from different issues need not reproduce the change announced in the later issue. Keep each original issue or its source identifier. The COT and EIA series need their own release clocks, not a weekly date join. [CFTC reports](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm) · [EIA petroleum reports](https://www.eia.gov/petroleum/supply/weekly/) · [EIA gas reports](https://ir.eia.gov/ngs/ngs.html)

The current primary model uses released inventories as public information. Cushing stocks and physical-tightness regimes are deferred; national crude stocks must not be relabelled Cushing. Original values are still a gate: a present-day historical download is not proof of what was announced then. If Bloomberg has only revised historical values, record that limitation rather than using them as first-release observations.

### Optional additions, in this order

1. **Archived EIA survey medians.** For the change in U.S. commercial crude stocks and the Lower-48 gas-storage change, request the median expectation recorded before each announcement, its units/sign convention, reference week, survey cutoff and actual release linkage. Keep the first actual figure beside it. This enables an inventory-surprise extension; it is not required for the initial four-model comparison. A later survey revision is not a pre-announcement expectation. No Bloomberg economic-series ticker or survey field is prescribed until its terminal definition and historical vintage support have been checked.
2. **Intraday coverage feasibility.** Ask whether individual CL/NG contract histories spanning the research years include timestamped five-minute trade bars (OHLC, volume, bar-start/end convention and timezone) through actual COT release cutoffs, including holiday and delayed releases. Start with one event. This could support a separate exact-pre-release version; do not infer full historical coverage from a recent intraday screen. Exclude any bar extending past the chosen cutoff. Exact historical release times and public-feature availability remain necessary. The current daily study does not require a bulk tick-data export.

### Workbook to retain

Save the original Bloomberg workbook and a separate value-only copy in the lab-approved location. Use sheets named `Queries`, `Contract_Master`, `Daily_Prices`, `Sessions`, `Field_Definitions`, and `Availability_Notes`. Add `Release_History` and `Inventory_Surveys` only if those requests succeed. Record unsuccessful fields and date gaps. A wide layout is acceptable if every column keeps its contract, field and unit; preserve each date column.

The two normalized CSVs below already have a validator. The session, availability, release and survey sheets are supporting evidence and do not yet have importers; do not append their columns to the strict price CSV. From this package we compute momentum, volatility, spreads, early/late snapshots and future outcomes ourselves. Daily prices must cover all sessions, including the days after release, rather than only Tuesdays and Fridays. Keep original signs, blanks and error messages; do not fill prices across missing days or contract expiries.

## First visit: the deliverable

Bring back a permitted, value-only pilot dataset and the original workbook containing its queries. If the institution requires Bloomberg data to remain on the lab machine, keep the files there and run the research tools in that approved environment instead. Establish the permitted location before transferring raw data. Penn's current guide documents a Desktop API portability restriction and directs users to `DAPI <GO>` for applicable guidelines and exceptions; it does not establish the rules of this user's institution. Confirm the local arrangement with the lab librarian. [Penn Bloomberg API guide](https://guides.library.upenn.edu/bloomberg/excel)

The minimum pilot is:

| Market | Individual delivery contracts | Daily dates requested | Purpose |
|---|---|---|---|
| WTI crude oil | May, June and July 2020 | 2 March–8 May 2020, within each contract's life | Identity, overlapping maturities, expiry and negative prices |
| Henry Hub natural gas | April, May and June 2020 | 2 March–8 May 2020, within each contract's life | More than one expiry transition and simultaneous contracts |

For each, get daily settlement plus contract identity, delivery month, actual last-trade date, currency, price unit and contract multiplier. Volume and open interest are useful optional additions after settlement works. Retrieve the NYMEX energy session/holiday calendar for the pilot too; an absent price alone does not identify a closed session.

**Pilot control:** WTI May 2020 settled at **-37.63 USD/barrel on 20 April 2020** and expired the following day. Preserve that negative number. This is an ingestion check; the proposed ten-sessions-to-expiry strategy might not hold that particular maturity on that date. [CFTC event report announcement](https://www.cftc.gov/PressRoom/PressReleases/8315-20)

## Find the exact securities

1. Open `CLA <Comdty> CT <GO>` for WTI, and `NGA <Comdty> CT <GO>` for Henry Hub. `CT` is the contract table; use `SECF <GO>` if the product is not found. Open `DES <GO>` on a selected contract to inspect its identity. Calgary documents these commodity entry points and the historical-data wizard. [Calgary commodity-futures guide](https://libguides.ucalgary.ca/ld.php?content_id=10215519)
2. Use the terminal's historical/expired-contract discovery controls, or its help, to find the delivery months in the pilot. A current active-contract list is insufficient. Record the exact resolved security string and any stable provider identifier alongside the description and delivery month.
3. Bloomberg documents the shape `root + month code + year + optional session + Comdty`, with examples such as `CLZ2 COMB Comdty`. It also documents the bulk field `FUT_CHAIN`, usable through `BDS`. The public guide does not validate today's expired-year disambiguation or historical-chain overrides for this account. **Do not generate hundreds of tickers by assuming `CLK20 Comdty`, `CL K20 Comdty`, or a one-digit year will resolve correctly.** Copy terminal-resolved identities and confirm their full years in `DES`. A ticker that loads can still refer to the wrong decade. [Bloomberg Core User Guide, pp. 23–25](https://data.bloomberglp.com/professional/sites/4/BLPAPI-Core-User-Guide.pdf)
4. `K` is May and `M` is June. The twelve delivery codes are `F G H J K M N Q U V X Z` for January through December. Generic `CL1`/`NG1` and active `CLA`/`NGA` aliases are navigation aids; they are not the contract identifiers to export for the experiment. [Calgary ticker reference](https://libguides.ucalgary.ca/c.php?g=255311&p=1703177)

For bulk discovery, use `FLDS <GO>` on `FUT_CHAIN` to check the supported expired-contract and as-of-date options, then let the wizard produce the formula. Save its exact field names, override values and result. If the terminal cannot expose earlier contracts, record that gap rather than substituting a continuous series.

## Confirm fields before requesting history

**`PX_SETTLE` is verified in Bloomberg's own documentation as its official settlement-price field.** Confirm historical availability for one pilot contract and compare it with the terminal's settlement display. Do not substitute `PX_LAST` merely because it returns a value. [Bloomberg futures benchmark statement, input data](https://assets.bbhub.io/professional/sites/10/Benchmark-Statement-Bloomberg-Futures-Tracker-Indices.pdf)

Use `FLDS <GO>` with the exact security loaded for the remaining attributes. Search the descriptions below, open the field definition, and save the returned mnemonic, units, historical support and relevant overrides. These Bloomberg metadata mnemonics have **not** been independently verified here, so this guide does not prescribe them:

| Required meaning | What to establish in the lab |
|---|---|
| Security identity | Exact API security string, stable identifier if available, NYMEX product and full name |
| Delivery month | Four-digit year and month; distinguish delivery month from the earlier last-trade date |
| Last trade | Actual date for this contract; separately retain first notice and delivery dates if available |
| Multiplier | Contract dollars per one quoted price-unit change, plus underlying contract size |
| Currency / quote unit | USD; dollars per barrel for CL and dollars per MMBtu for NG |
| Volume / open interest | Contract counts; whose trading date the observation describes and when it becomes available |
| Session calendar | Correct NYMEX energy calendar, historical holidays, early closes and timezone |
| Price status / availability | Preliminary versus final/revised, settlement measurement time and dissemination evidence, where available |

CME's rules specify a standard CL contract of 1,000 barrels and NG contract of 10,000 MMBtu. With prices in USD/barrel and USD/MMBtu, the expected dollar multipliers are 1,000 and 10,000 respectively. Verify every resolved security is the standard contract and record the historical specification used; micro, financially settled or differently quoted contracts must not be silently included. [CL rulebook](https://www.cmegroup.com/rulebook/NYMEX/2/200.pdf) · [NG rulebook](https://www.cmegroup.com/rulebook/NYMEX/2/220.pdf)

## Export through Excel

While logged into Bloomberg, use the Bloomberg Excel ribbon's historical end-of-day import wizard. Select the resolved individual securities, `PX_SETTLE`, daily frequency and explicit start/end dates. Put dates in real Excel date cells, for example `=DATE(2020,3,2)` and `=DATE(2020,5,8)`, to avoid regional ambiguity. The formula structure is:

```excel
=BDH(security_cell,"PX_SETTLE",start_date_cell,end_date_cell)
```

This is a structural example, **not the complete production formula**: configure the wizard's day and missing-data options explicitly. Use actual trading observations and missing values for unavailable data, with no previous-price or zero filling. Save the generated formula and options. Bloomberg's API guide identifies `ACTIVE_DAYS_ONLY` and `NIL_VALUE` as the corresponding API values; Excel option spelling must come from the installed wizard/help. For dates on output, format cells `yyyy-mm-dd`; this display format is separate from Bloomberg's relative-date option. [Bloomberg Core Developer Guide, pp. 92–94](https://data.bloomberglp.com/professional/sites/4/BLPAPI-Core-Developer-Guide.pdf)

Keep the raw workbook with separate sheets for queries, metadata, prices, field definitions and acquisition notes. Save a value-only copy as well, so opening it outside an active session does not replace observations with formula errors. Preserve `#N/A` and authorization/limit errors in the raw copy and describe them; never coerce them to zero. Use small batches and the lab's download limits rather than repeated full-history refreshes.

The final research CSVs use the schema below. A wide Bloomberg workbook is acceptable raw material: preserve each security/field header and its own date column so it can be reshaped locally. Do not align unrelated contracts by spreadsheet row number.

### `contract_master.csv`

```csv
contract_id,market,delivery_month,last_trade_date,multiplier,currency,price_unit
```

- `contract_id`: exact provider security string, consistently reused in prices; never a continuous alias.
- `market`: `CRUDE_OIL` or `NATURAL_GAS`.
- `delivery_month`: `YYYY-MM`; `last_trade_date`: `YYYY-MM-DD`.
- `multiplier`: finite positive dollar value for a one-unit settlement move.
- `currency`: `USD`; `price_unit`: `USD/barrel` or `USD/MMBtu` as appropriate.

For Bloomberg imports, use the resolved individual ticker with its `Comdty` suffix. The importer checks that its CL/NG root, delivery-month letter and year suffix agree with the declared metadata; it accepts session qualifiers and one-, two- or four-digit years. A one-digit year still needs the terminal's full-year confirmation. A syntactic match does not verify the security against Bloomberg. Last trade must fall in the immediately preceding calendar month for these two products; the exact day remains a sourced metadata requirement, not a holiday calculation performed by the importer.

### `contract_prices.csv`

```csv
contract_id,price_date,settlement,volume,open_interest
```

`volume` and `open_interest` are optional. Each row identifies one contract and exchange trade date (`YYYY-MM-DD`). Settlement must be a finite signed number; zero and negative values are permitted. Missing observations are absent rows or explicit blanks in the raw export, not fabricated settlements. Keep currency formatting and thousands separators out of normalized numeric cells.

Retain supplementary metadata in the raw workbook or a sidecar: exchange, Bloomberg stable ID, description, tick size, first-trade date, calendar ID, field definitions, status and time evidence. Record `source` (Bloomberg plus the institutional access channel), `price_field=PX_SETTLE`, UTC retrieval timestamp, date range, generated query and the permitted storage/usage arrangement. The importer records acquisition provenance separately from the two minimal tables. A retrieval timestamp is not historical publication time.

On the authorized processing machine, from the repository checkout, validate the two normalized CSVs with:

```sh
python -m src.contract_data \
  --master /approved/path/contract_master.csv \
  --prices /approved/path/contract_prices.csv \
  --source "Bloomberg institutional lab" \
  --price-field PX_SETTLE \
  --output-dir /approved/path/contract_packages
```

Replace the example paths with the permitted local locations. Optionally provide `--retrieved-at` with the actual export time as a timezone-aware ISO timestamp; without it, the importer records import time. Each successful import creates a new UUID directory containing original CSV bytes, normalized tables, coverage diagnostics and a checksum manifest. Invalid inputs fail without creating a package. The existing descriptive price database is untouched. Header-only templates are [contract_master.example.csv](../config/contract_master.example.csv) and [contract_prices.example.csv](../config/contract_prices.example.csv); they intentionally contain no observations.

The manifest distinguishes an explicit export timestamp from the import-time default and labels metadata as caller-declared. Future retrieval timestamps and price dates later than the export's New York calendar date are rejected. This check establishes chronological consistency only; it does not establish the price's historical dissemination time, original vintage or license rights.

## After the pilot passes

Request trade dates from **1 January 2008 through the latest completed session available at acquisition**. This extends the earlier guide's January-2009 start to provide a full 50-week price-feature buffer before the post-September-2009 disclosure sample; it does not move the COT publication start earlier. Cover every monthly CL/NG maturity needed to construct the nearest eligible contract and the prespecified curve feature, including maturities beyond 2026 if needed for curves near the sample end. Begin with a target of the first twelve listed maturities at each historical date; this is an acquisition target, not a frozen model feature.

For efficient collection, split requests by market and delivery year, retrieving each contract's available history intersected with the research date interval. Obtain the contract master first and reconcile expected delivery months against actual returned contracts. A contract may have traded long before its delivery year. Do not request only observations in the delivery year or infer old chains solely from today's active contracts. Check calendar coverage and point-in-time listing/expiry evidence separately.

The pilot passes only when identities and units agree, prices stop at the actual last-trade date, duplicate keys are resolved without silent overwrites, the negative-price control is present, adjacent maturities overlap, and missing dates are classified. Full-scale acceptance then requires an auditable common sample, supported calendars, original-file hashes and documented latest-vintage limitations. Historical Bloomberg retrieval alone does not establish first-release values or intraday availability.

## Additional useful lab request

Ask the librarian which accessible Bloomberg sources preserve **actual historical CFTC COT publication dates/times linked to report observation dates**, including shutdown backlogs and delayed issues, and original EIA release issues/revisions. Request a small example with its source and field definitions before any bulk request. A current economic calendar, scheduled release time or Tuesday observation date is not evidence of an actual historical publication. Do not assume `ECO` or a COT historical series supplies the required event linkage.

The broader source comparison and remaining data limitations are in [contract-data-feasibility.md](contract-data-feasibility.md).
