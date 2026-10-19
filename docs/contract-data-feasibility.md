# Contract data feasibility and acquisition specification

Reviewed 18 October 2026. This is a documentation audit, not evidence of an existing subscription or a complete research sample. No account was created, purchase made, or licensed dataset downloaded.

## Current gap

`src/ingest_prices.py` downloads `CL=F` and `NG=F` daily closes, labels them `daily_close_proxy`, and leaves `price_at` unknown. `futures_prices` is keyed by `(price_date, market)`: it cannot represent simultaneous maturities or price vintages. There is no contract identifier, expiry, multiplier, exchange-session calendar, or curve. Consequently, these rows cannot enforce the paper's ten-sessions-to-expiry selection rule, hold one identified contract for five sessions, or distinguish a price change from a provider's contract switch. A continuous close is also insufficient evidence of a settlement or executable fill.

Use a separate contract panel; preserve the existing descriptive series. Require the following before admitting a research outcome:

| Component | Minimum fields and checks |
|---|---|
| Contract master | `contract_id`, provider identifier, exchange, root, delivery year/month, last-trade date/time, currency, quote unit, multiplier, tick size, effective dates and source |
| Prices | Contract, exchange trade date, finite signed settlement, price type/status, settlement-window end, actual dissemination timestamp when evidenced, provider-access availability, volume and open-interest observation dates |
| Revisions/provenance | Provider/file ID, original file, retrieval timestamp, checksum, version/ETag, preliminary/final classification; preserve versions instead of overwriting |
| Sessions/curve | Historical sessions and early closes; all maturities needed for selection and slope, with common as-of cutoffs; distinguish absent contracts from missing settlements |
| Outcome audit | Forecast cutoff, selected contract, sessions to expiry, entry/exit benchmarks, past-only dollar-volatility scale, exclusion reason, data-license reference |

## Verified candidate sources

**CME DataMine is the direct-source candidate.** Its End of Market Summary Standard documentation lists individual delivery year/month, settlement, volume, open interest and last-trade date. Some fields are only available after November 2010; coverage must be checked by product and period. It also documents absent settlements for expiries with neither trading nor open interest. Historical one-time orders provide final files, so they do not establish the initially disseminated vintage. [Dataset and layout](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457225547/End+of+Market+Summary+-+Standard)

DataMine requires an account, license agreement and an order; API retrieval requires an entitled API ID. Existing university access, product/date entitlements, full-curve coverage and redistribution permissions remain unverified. Check institutional holdings before requesting a priced acquisition. No cost or completeness estimate is asserted here. [Ordering](https://www.cmegroup.com/datamine.html) · [API access](https://www.cmegroup.com/datamine/datamine-api.html)

**LSEG/Datastream is an institutional-access candidate.** LSEG's own example reconstructs expired individual futures identifiers, allowing a researcher to choose a roll rule. Copenhagen Business School documents active, expired and continuous futures coverage in Datastream. These establish a credible access route, not this author's entitlement or complete CL/NG history. Require actual contract samples, field definitions and export rights before choosing it. [LSEG example](https://github.com/LSEG-API-Samples/Article.RD.Python.ReconstructingRICsForExpiredFuturesContracts) · [Institutional guide](https://libguides.cbs.dk/c.php?g=669247&p=4749987)

## Contract identity and information time

NYMEX CL has a 1,000-barrel unit. Its normal expiry rule refers to the third business day before the preceding month's 25th, with adjustments when that date is not a business day. NG has a 10,000-MMBtu unit and normally stops trading three business days before the delivery month's first day. Both rules contain holiday exceptions; retain sourced historical expiries rather than reconstructing everything from today's calendar. [CL rules](https://www.cmegroup.com/rulebook/NYMEX/2/200.pdf) · [NG rules](https://www.cmegroup.com/rulebook/NYMEX/2/220.pdf)

CME lists normal energy settlement windows as 14:28–14:30 Eastern; early closes can change these. That measurement window is distinct from publication. CME's current access policy delays website settlements until midnight Central, with different licensed delivery channels. Neither today's schedule nor a file's trade date proves historical availability. Preserve separate measurement, dissemination and access times; where evidence is absent, use the paper's conservative next-session convention and state the limitation. [Settlement times](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457085528/Daily+Settlement+Time+Details) · [Access policy](https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html)

The paper's target is `(exit_price - entry_price) * multiplier / past_dollar_volatility`, with a finite strictly positive denominator. Accept valid zero and negative prices; do not use log/percentage returns, clip values, or silently discard those episodes. The current descriptive backtest excludes nonpositive windows and therefore does not implement this target. A settlement benchmark alone does not prove achievable execution or net profitability.

## Inventory and sample constraints

The [validation record](validation.md) shows gas inventory starting in January 2010. A complete five-year seasonal reference makes the proposed seasonal feature available only around 2015; another five years of complete-feature training can move M2 evaluation toward 2020. These are approximate implications, not verified fold dates. Obtain earlier comparable released vintages or explicitly accept a shorter common sample; do not backfill missing early seasonal features with future information.

Crude ingestion currently selects `PET.WCESTUS1.W`, the U.S. stock series, whereas the paper specifies Cushing. EIA's separate Cushing series begins in April 2004 on its historical page. Its original vintages and release evidence still need auditing; the current 1982 crude coverage does not establish Cushing coverage. Preserve both series with explicit identities and units. [EIA Cushing history](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=W_EPC0_SAX_YCUOK_MBBL&f=W)

Next acceptance gate: obtain an authorized sample covering several CL/NG maturities, expiry transitions, holidays and April 2020; validate schema, timestamps, signed prices and rights, then measure common coverage before implementing the forecasting experiment.
