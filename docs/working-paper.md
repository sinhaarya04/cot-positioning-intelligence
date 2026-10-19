# What Does a COT Release Add? Public Positioning and Risk in Energy Futures

**Aryan Sinha**

**Preliminary research design and methods draft - 16 October 2026 (UTC); data-acquisition update 18 October 2026 (America/New_York)**

**Status:** This document specifies a proposed empirical study. It contains no completed forecasting experiment, estimated economic effect, or evidence of trading profitability. It has not been submitted or peer reviewed. The accompanying code currently implements data ingestion, availability checks and descriptive evaluation; the proposed forecasting study remains to be implemented.

## Abstract

This study will examine whether a newly published Commitments of Traders (COT) report improves energy-futures risk forecasts beyond information already available in prices, volatility, the futures curve, inventories and previous positioning disclosures. An availability-aware panel of WTI crude oil and Henry Hub natural gas will support comparisons between otherwise identical forecasts with and without the new report. A rolling position-inference model will separate predictable positioning from model-unanticipated report content. The primary outcome will be joint lower- and upper-quantile forecast loss over five trading sessions; physical tightness will be a prespecified source of heterogeneity. Chronological estimation, publication delays, revisions and dependent observations will be addressed explicitly. The study will seek either reproducible incremental forecasting value or informative bounds on that value. No result is asserted in this draft. Generative AI assisted the literature search, research design, writing and software development; author verification and responsibility are required before submission.

## 1. Motivation and relationship to existing work

The forecasting value of public positioning depends on whether it adds information beyond the chosen variables that explain both positions and subsequent market outcomes. The project therefore asks: **At a feasible post-publication decision time, does the latest COT disclosure improve next-week risk forecasts relative to an otherwise identical public-information baseline?**

This is narrower than asking whether large traders predict prices. Sanders, Irwin and Merrin [1] find limited forecasting evidence and substantial trend-following behavior in agricultural positions. Kang, Rouwenhorst and Tang [2] distinguish slow hedging and fast liquidity demands with different return implications. Their subsequent crowding study [3] links speculative pressure to factor returns. Boos and Grob [4] show that lagged returns explain a substantial component of speculative positioning. These studies motivate strong benchmarks and caution against treating raw positioning as independent information.

Publication timing is also established prior work. Proskurin [5] examines machine-learning forecasts from COT data; the publisher's issue introduction explicitly contrasts hypothetical Tuesday availability with actual Friday information. Nikitopoulos, Thomas and Wang [6] study hedging pressure, inventories and oil volatility. Thus neither timing correction, machine learning, position inference, nor an inventory interaction alone establishes novelty.

The candidate contribution is the combined measurement of **incremental disclosure information**, conditional risk forecasting and physical-state heterogeneity under auditable information timing. This is a hypothesis about a research opportunity, not a priority claim. The bibliography is selective; some findings were checked through abstracts or publisher summaries rather than complete articles. The closest full papers must be assessed before submission.

## 2. Data, availability and outcomes

The initial markets will be WTI crude oil and Henry Hub natural gas. CFTC futures-only Disaggregated reports will supply managed-money positions; Legacy data can support prespecified robustness comparisons. Disaggregated publication began in September 2009. Earlier history was published retrospectively and cannot be treated as contemporaneously available [9].

Each observation will retain its observation date, actual release timestamp, source, retrieval time, content hash and vintage classification. Holiday and exceptional publication delays require documented release evidence. A current historical API value with a verified publication date is still a latest-vintage observation, not proof of the original released value. EIA petroleum and gas archives will be used to reconstruct inventory releases where feasible [10]. A latest-vintage approximation will be reported separately if complete original values cannot be recovered.

All baseline inputs will be frozen immediately before COT publication. Both competing forecasts will use the same first admissible price benchmark strictly after publication. With daily data, the entire publication date will be excluded. This conservative convention estimates predictive usefulness after a delay; it cannot identify immediate announcement effects or guarantee an executable fill.

The intended price panel requires contract identities, expiry dates, multipliers and a maturity curve. The main contract will be the nearest maturity with at least ten exchange sessions remaining at entry and will be held for five sessions. Outcomes will use contract-dollar price changes divided by a strictly positive, past-estimated dollar-volatility scale. Percentage or log returns are unsuitable when prices cross zero. Contract selection, scale estimation and exceptional-date rules will be frozen before evaluation. Costs, slippage and roll accounting are necessary for the secondary economic exercise.

The primary targets will be the 10th and 90th conditional quantiles of this five-session outcome. Their equally weighted pinball losses will be averaged with equal market weights. Individual-tail losses and calibration will also be reported so that an average cannot conceal a deterioration in one tail. Mean-return prediction, longer horizons and economic usefulness will be secondary outcomes. Sparse 1% tails will not be a primary claim.

## 3. Prespecified comparisons

The main models will use a common parsimonious regularized quantile-regression specification, with comparable tuning opportunities:

| Model | Information available at the forecast cutoff | Comparison |
|---|---|---|
| M0 | Lagged price changes, momentum, realized volatility, curve slope, released inventories, seasonality and previous COT disclosures | Public-information baseline |
| M1 | M0 plus the newly released managed-money net position/open interest | Primary test: incremental value of the report |
| M2 | M1 plus a prespecified interaction with seasonal physical tightness | Secondary test: state-dependent value |

Historical quantiles, volatility-scaled historical quantiles and a heavy-tailed volatility model will provide simpler benchmarks. Seasonal inventory references must be estimated using past information; a full-sample seasonal mean would leak future observations. The repository's present inventory z-score interaction is not this seasonal measure.

The primary inventory-tightness proxies will be negative standardized anomalies in released Cushing crude stocks and Lower-48 working gas, relative to the preceding five years' same calendar week plus or minus two weeks. These proxies do not directly measure scarcity: low stocks and storage-capacity pressure can imply different risks. Position changes and separate gross long/short measures will be secondary specifications. The precise state definitions and additional comparisons must be frozen before evaluation.

For interpretation, let `q_t` denote newly reported managed-money net positions divided by open interest. A past-only position model will predict `q_hat_t` from information available before release, and define `u_t = q_t - q_hat_t`. Historical training residuals for downstream models must themselves be generated chronologically, rather than fitted in sample.

Because `q_t = q_hat_t + u_t`, residualization creates no new information conditional on the same inputs. It can aid interpretation and impose a modeling restriction. `u_t` is a model forecast error, not an observed consensus surprise, private-information measure, instrument or causal shock. Apparent gains could reflect model misspecification. Comparison with position-replication and slow/fast-pressure benchmarks [2,4] will help establish what is incremental.

## 4. Evaluation and interpretation

The proposed protocol will use a minimum five-year initial window with complete required coverage, followed by expanding chronological estimation and annual outer evaluation blocks. Both markets will share calendar folds. Inner tuning will use earlier data only. Scaling, seasonal references, position inference and feature selection will be fitted within training windows; labels ending after a forecast cutoff will be excluded.

The primary estimand will be the average M1-minus-M0 loss difference. Common-date block resampling will preserve serial dependence, overlapping outcomes and cross-market shocks. Two commodities do not justify conventional many-cluster inference. Conditional predictive-ability methods [7] will inform the final test specification. A small prespecified secondary family will receive multiplicity correction, and every attempted specification will enter a trial ledger; financial discovery and power concerns motivate this discipline [8].

The protocol will define a minimum useful improvement using training-period simulations and the intended risk application before evaluating held-out blocks. Confidence intervals must distinguish an informative small-effect bound from an imprecise non-significant result. Availability, vintage, execution-delay and contract-selection sensitivity analyses will be reported even when unfavorable.

Existing historical exploration means the study must be described as pseudo-out-of-sample. After the protocol is frozen, forecasts will be archived prospectively before outcomes occur. A short prospective record demonstrates operation, not statistical proof. Stronger models will not be added merely because initial results are disappointing.

## 5. Implementation and present evidence

The corrected repository implements strict source-field validation, transactional writes, raw-response archives, sourced publication metadata, backward availability joins, prior-only thresholds, explicit daily entry/exit selection and event audits. It also provides locked dependencies, offline tests, CI, freshness checks and validated optional LLM explanations. LLM directional opinions are outside the proposed forecasting experiment.

The current engine produces descriptive conditional underlying-return summaries. It does **not** implement the M0-M2 experiment, seasonal tightness, contract-level dollar outcomes, dependence-aware inference, or a costed portfolio. Continuous Yahoo close proxies lack the contract identity needed for the proposed design. Nonpositive-price windows are currently excluded, not economically modeled.

The subsequent [research-data audit](research-data-audit.md) adds a bounded publication-evidence ledger and read-only coverage diagnostics. It does not establish a complete common sample or change evaluation eligibility. Current crude inventory is the national commercial-stock series; the proposed Cushing seasonal-state test requires a separate series. Archived gas issues also demonstrate revisions, so publication dates and original values require separate verification.

The data-acquisition extension provides reproducible CFTC notice and EIA archive extraction, explicitly separating official index evidence from verified issue headers and recording unavailable or contradictory documents. CFTC actual-publication coverage and gas-release coverage remain sparse. A separate contract importer preserves signed settlements, original export bytes and checksums; its validation is not an exchange-calendar or first-vintage certification. The [Bloomberg lab protocol](bloomberg-export-guide.md) starts with six individual 2020 contracts before a broader historical request. An existing local natural-gas workbook has individual securities but lacks verified price-field and expiry metadata, so its values have not entered an experiment.

The correction pass passed **141 offline tests**. A local engineering validation run, `20261016T014316Z-934738f8`, recorded:

| Input or output | Count |
|---|---:|
| CFTC rows: two markets, Legacy and Disaggregated | 3,572 |
| Daily continuous-price bars | 13,127 |
| EIA inventory observations | 3,174 |
| Descriptive signal rows | 1,786 |
| CFTC records with supplied verified releases | 0 |
| Eligible return evaluations / summary rows | 0 / 0 |

The run correctly reported `needs_release_evidence_or_history`. These counts validate ingestion and fail-closed behavior, not financial forecasts. Data coverage differs by input, so they do not define a common research sample. No Sharpe ratio, predictive gain, significance level or trading result is currently supported.

## 6. Limitations and publication readiness

Major unresolved constraints are historical release evidence, original inventory vintages, licensed contract/curve access and statistical power in two weekly markets. COT categories aggregate traders and maturities; changes can reflect classification as well as trading. Neither conditional associations nor disclosure timing alone establishes causality. Additional markets should be a declared extension, not a search for favorable results.

Before a completed working paper or journal submission:

- [ ] Audit release calendars, original values, exclusions and data rights.
- [ ] Implement and freeze the model protocol, contract targets and experiment ledger.
- [ ] Reproduce the closest feasible benchmarks and establish the contribution precisely.
- [ ] Generate all estimates, uncertainty, calibration and sensitivity tables reproducibly.
- [ ] Record prospective forecasts and obtain independent methodological review.
- [ ] Complete author verification, disclosures, references and venue-specific requirements.

An eligible completed manuscript could be circulated as a preprint and considered for a focused finance note or a commodity/futures journal. This repository draft is research documentation, not a completed empirical paper or a publication claim.

## References

1. Sanders, D. R., Irwin, S. H., and Merrin, R. P. (2009). *Smart Money: The Forecasting Ability of CFTC Large Traders in Agricultural Futures Markets.* [Author-institution record](https://experts.illinois.edu/en/publications/smart-money-the-forecasting-ability-of-cftc-large-traders-in-agri/).
2. Kang, W., Rouwenhorst, K. G., and Tang, K. (2020). *A Tale of Two Premiums: The Role of Hedgers and Speculators in Commodity Futures Markets.* [Institutional manuscript](https://www.carloalberto.org/wp-content/uploads/2018/11/Liquidityprovision-Luxembourg2.pdf).
3. Kang, W., Rouwenhorst, K. G., and Tang, K. (2021). *Crowding and Factor Returns.* [University-hosted working paper](https://acfr.aut.ac.nz/__data/assets/pdf_file/0003/634971/SSRN-id3803954.pdf).
4. Boos, D., and Grob, L. (2023). *Tracking Speculative Trading.* [Institutional record](https://digitalcollection.zhaw.ch/items/611d9f41-b601-4aad-a9bf-360b6b5dca2d).
5. Proskurin, O. (2021). *Does the CFTC Report Have Predictive Power: Machine Learning Approach.* DOI: 10.3905/jfds.2021.1.065. Timing comparison checked against the [publisher's issue introduction](https://www.pm-research.com/content/iijjfds/3/3/1.full.pdf); full article access was restricted.
6. Nikitopoulos, C. S., Thomas, A. C., and Wang, J. (2024). *Hedging Pressure and Oil Volatility: Insurance versus Liquidity Demands.* [Published article](https://doi.org/10.1002/fut.22470).
7. Giacomini, R., and White, H. (2006). *Tests of Conditional Predictive Ability.* [Published article](https://doi.org/10.1111/j.1468-0262.2006.00718.x).
8. Harvey, C. R., and Liu, Y. (2020). *False (and Missed) Discoveries in Financial Economics.* [arXiv:2006.04269](https://arxiv.org/abs/2006.04269).
9. CFTC (2009). Disaggregated historical-data release and original publication context. [Official announcement](https://www.cftc.gov/PressRoom/PressReleases/5737-09). See also [exceptional release announcements](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm).
10. EIA. [Weekly Petroleum Status Report archives](https://www.eia.gov/petroleum/supply/weekly/archive/) and [Weekly Natural Gas Storage Report methodology](https://ir.eia.gov/ngs/methodology.html).

## AI-assistance disclosure

OpenAI Codex assisted with source discovery, draft organization, methodological suggestions, code corrections and tests. AI-generated material can contain errors. The named author must verify references, implementation, data provenance, analysis and final wording before academic circulation or submission. No AI system is listed as an author, and no empirical results were generated or inferred by this draft.
