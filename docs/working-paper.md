# Can Public Data Replace a COT Release? The Value of Delayed Positioning Disclosures

**Aryan Sinha**

**Preliminary research design and methods draft - literature/design revision 19 October 2026 (America/New_York)**

**Status:** Proposed empirical study. No completed forecasting experiment, estimated disclosure value or evidence of trading profitability. This draft has not been submitted or peer reviewed. The software implements data ingestion, validation and descriptive evaluation; the forecasting comparisons below remain to be implemented.

## Abstract

This study proposes to measure the loss in energy-futures risk-forecast accuracy when an official Commitments of Traders (COT) disclosure is replaced by an estimate constructed from earlier public information. For WTI crude oil and Henry Hub natural gas, forecasts using reconstructed and reported positions will be trained and evaluated at matched decision times with common public predictors. An additional comparison will test whether the report improves a baseline already containing its reconstruction. The primary outcome is joint 10th- and 90th-quantile loss over five exchange sessions. A prespecified secondary test asks whether disclosure value increases with reconstruction uncertainty measured before publication. The contribution sought is decision-specific evidence on the substitutability of delayed disclosures, rather than a new position-reconstruction method. Chronological estimation, release batches, contract identity and original data vintages are central design requirements. Literature access, sample size and data feasibility remain unresolved. No result or priority claim is asserted.

## 1. Research question and contribution

**For a risk forecast made after publication, can a public-information estimate substitute for the newly reported position without a practically important loss in accuracy? When does the report still help?**

The distinction is between reconstructing a position and replacing its usefulness for a decision. A high position-prediction score does not establish that the missed component is economically irrelevant. A large error need not matter for future risk either. The study will quantify this distinction for a declared forecasting task.

The [full literature assessment](literature-gap-review.md) records versions, methods, table locators and remaining access gaps. Pre-release position reconstruction with disclosure lags is already explicit in Boos and Grob [4]. Uhl [11] relates positioning alignment to momentum performance and examines an investment application. Kang, Rouwenhorst and Tang [2] examine returns after public release and separate momentum-related positioning. Pradkhan [12] studies position information at return quantiles. These are essential comparators, not gaps to claim as discoveries.

Nikitopoulos, Thomas and Wang [6] make positioning, inventories and oil risk close prior art; Bosch [13] studies COT/WASDE publication and anticipation. Proskurin [5] and Yu et al. [14] remain particularly important full-text access gaps. Newer tail-connectedness and natural-gas studies [15,16] further narrow any broad claim about speculation and extreme outcomes. Risk calibration in energy futures is also established [17].

The candidate contribution is a **matched disclosure-substitution experiment**, a useful-effect bound, and a prespecified test of when the substitute fails. It is an applied information-value study, not a new forecasting estimator, a demonstration of private information, or a causal disclosure-policy study. Originality remains conditional on checking the unavailable papers and final versions.

## 2. Data, information clocks and target

The initial markets are WTI crude oil and Henry Hub natural gas. Futures-only Disaggregated COT managed-money net positions divided by total open interest define `q_t`. The subscript refers to the report's observation date, usually Tuesday. The reconstruction `q_hat_t` targets that same observation date; it is not an estimate of current exposure on Friday. Legacy commercial slow/fast pressure and previously released managed-money data enter the public comparator where coverage permits.

Disaggregated publication began in September 2009 [9]. Earlier backfilled history was not publicly available at its observation dates. It may enter later training only after its documented release, under a separately declared protocol. Each value needs observation time, availability evidence, retrieval time, hash and vintage class. A current API historical value is not proof of the originally disclosed number.

Define three distinct times: the position observation time, the actual disclosure time, and the forecast/entry time. The preferred public feature cutoff is immediately before verified disclosure; each feature must have its own availability evidence. When only daily dates are defensible, use a separate conservative specification: freeze public inputs at 00:00 America/New_York on the release date, and exclude the whole release date from price entry. This specification omits some public information available later that day and cannot establish the report's value against the complete pre-release information set. Date-only evidence must not be converted into an invented exact release timestamp or silently admitted to the current timestamp-based engine.

All competing forecasts use the same first admissible settlement after the publication date, and are issued before that benchmark. Both forecasts keep the same public inputs. A declared sensitivity analysis refreshes both models' public features through the previous admissible session before entry, excluding the new COT fields from the reconstruction baseline; this measures whether subsequent public information substitutes for the report. Neither convention identifies the immediate announcement response or guarantees an executable fill.

Exceptional backlogs require a publication-batch identifier. The primary target is the newest observation in the batch; prior reports in that batch must not leak into its pre-release reconstruction. Use one forecast per market and publication batch. If a later batch would reuse an entry session, retain the latest batch under a fixed rule. Older reports and multiple maturities are not extra independent announcements. Batch cases are sensitivity results, not natural experiments.

The contract panel requires individual securities, expiry, multipliers and contemporaneous curve information. Select the nearest contract with at least ten exchange sessions to expiry at entry, using metadata known at forecast issuance, and hold the same contract for five sessions. The outcome is its signed contract-dollar price change divided by a strictly positive dollar-volatility scale estimated before issuance. This accommodates zero and negative prices. Daily same-contract increments, not roll jumps, must form any historical dollar-change predictors; spread features must also avoid division by a price that can cross zero.

The primary targets are the conditional 10th and 90th percentiles of this outcome. Average their pinball losses with equal weights; aggregate with equal market weights on common eligible publication dates. Also show each market, each tail, coverage and calibration. A 10% tail is a risk-forecast target, not evidence about rare 1% disasters. Mean-return forecasts, other horizons and costed economic exercises are secondary.

## 3. Models and falsifiable comparisons

### 3.1 Public reconstruction

Use a small, fixed candidate set: persistence/lagged-position autoregression; a Boos–Grob-inspired smooth daily-trend model; and a regularized extension with already released inventories, curve spreads, volatility and seasonality. An Uhl-style volatility-scaled trend measure is a benchmark. Any adaptation to signed dollar changes must be labeled an adaptation, not an exact replication. Reproduce the published construction on a suitable positive-price sample separately where data permit.

Choose the reconstruction using earlier chronological validation of position error only, before downstream held-out risk outcomes are inspected. Its inputs may include publicly available exchange open interest only if its availability is verified; using the newly disclosed COT open-interest denominator to construct an earlier estimate would leak information. Evaluate both level error and change error against persistence. Report stability, bias and interval coverage by market.

Generate historical `q_hat_t` sequentially. Each training target must already have been disclosed at that historical cutoff. Define `u_t = q_t - q_hat_t` and a pre-release uncertainty proxy `s_t`, calculated from a fixed rolling window of earlier out-of-sample errors. Freeze that window and any calibration within training data. Do not use current `abs(u_t)`, future errors or full-sample standardization to label a report uncertain beforehand. If `s_t` is poorly calibrated, describe it as a proxy and do not interpret its groups as reliable confidence levels.

### 3.2 Risk forecasts

Use a common regularized quantile-regression family with identical outer folds and comparable tuning budgets. Let `X_t` contain price-change history, multiple trend horizons, realized volatility, signed curve spreads, released inventories, seasonality and previously disclosed positioning, including commercial slow/fast pressure. A declared flexible nonlinear public-only sensitivity guards against a weak linear baseline. All transformations and tuning are past-only.

| Model | Inputs | Purpose |
|---|---|---|
| P0 | `X_t, s_t` | Direct public-information comparator |
| PR | `X_t, s_t, q_hat_t` | Forecast using the reconstructed position |
| PQ | `X_t, s_t, q_t` | Matched-dimension forecast using the official position |
| PA | `X_t, s_t, q_hat_t, u_t` | Adds the report's correction to a baseline already containing the reconstruction |

PR and PQ are trained separately on their corresponding historical inputs. Do not train a model on true positions and then replace them with estimates only at test time: that introduces an avoidable training/deployment mismatch. PA contains the same information as adding `q_t` to PR. Historical generated features for PR and PA must be chronological, not in-sample fits.

Historical quantiles, volatility-scaled historical quantiles and a heavy-tailed volatility model supply basic checks. Direct public-only models must be competitive: gains from adding `q_hat_t`, which is a function of the public information set, can reflect representation or regularization rather than new information. Residualization itself does not create information. The report's error `u_t` is not a consensus surprise, private-information measure, instrument or causal shock.

### 3.3 Estimands

Let `L` be the equal-tail pinball loss. The **primary substitution cost** is `D = mean(L(PR) - L(PQ))`; positive values favor access to the official position. Report its confidence interval and a relative-loss version with a positive denominator fixed by the declared scoring convention.

The required incremental check is `A = mean(L(PR) - L(PA))`. If a finding does not survive both the matched replacement comparison and the augmented-baseline check, do not attribute it confidently to incremental disclosure content. Even agreement estimates usefulness within the chosen models and information set, not the optimal value of information under every possible forecasting rule.

Before evaluation, define a practically useful loss margin `delta` in consultation with the intended risk application, supported by training-period simulations. A confidence interval whose upper endpoint is below `delta` supports practical substitutability under that margin; a wide interval containing zero is inconclusive. A positive point estimate alone is insufficient evidence of useful disclosure value.

One prespecified secondary hypothesis asks whether PA's gain over PR is larger when `s_t` is higher. Estimate a continuous relationship or a single training-defined high/low split, chosen in the frozen protocol. This is falsifiable: high reconstruction uncertainty can simply be noise unrelated to future risk. Current realized errors can support descriptive diagnostics after publication, but cannot justify an ex-ante selection rule.

Physical tightness is deferred. A later extension may use past-only seasonal anomalies in Cushing crude stocks and Lower-48 gas. Low inventories and capacity pressure are different states; the current national-crude series does not establish either a Cushing measure or original-vintage scarcity information. Adding this extension now would multiply hypotheses and reduce the usable sample.

## 4. Evaluation, feasibility and interpretation

Use chronological expanding estimation and annual outer evaluation blocks, with common calendar folds across markets. A minimum five-year initial reconstruction window is followed by a minimum five-year downstream training window containing genuinely chronological generated features. Under a conservative post-September-2009 start, evaluation cannot begin before approximately late 2019, or 2020 for complete annual blocks. The additional history needed to calibrate `s_t` and missing-data exclusions can move this later. A documented backfill-assisted alternative can start earlier only if each training value was actually available at its historical use time. Do not silently count the same five years twice.

The feasibility report must count unique publication batches, training observations, evaluation observations, tail events and exclusions separately. Two weekly markets, incomplete release evidence and successive burn-in stages may leave inadequate precision. Power simulations precede held-out analysis. Failure of this gate means simplifying the scope or reporting a pilot, not retrospectively lowering the training requirements to obtain favorable results.

Exclude training labels whose five-session outcomes have not finished at the forecast cutoff, including during inner tuning. Fit scaling, reconstruction, uncertainty calibration, seasonal measures and risk-model tuning entirely inside the allowed training history. Archive the model version, inputs, cutoff, report identifier, forecasts and outcome end date for every prediction.

Use common-calendar block resampling to preserve serial dependence, overlapping outcomes and cross-market shocks. Do not treat two commodities or contract maturities as a large independent cluster sample. The final interval procedure must specify whether inference conditions on the realized forecast sequence or re-estimates the learning process; validate its finite-sample behavior in simulation rather than assuming a standard test handles nested generated regressors. Conditional predictive-ability methods [7] inform this choice.

Predeclare one primary comparison and a small secondary family; report both individual tails and multiplicity-adjusted secondary results. Log every attempted specification [8]. Include sensitivity to original versus latest vintages, input/entry delay, reconstruction strength, contracts, exceptional releases and missingness. Report the shared-date sample for each comparison; do not compare losses computed on different dates.

Historical inspection means the study is pseudo-out-of-sample. After protocol freeze, timestamp prospective forecasts before outcomes occur. A short live record verifies the process, not statistical significance. Failure to find daily predictive value does not establish that the report had no immediate market impact, no value to other users, or no regulatory purpose.

## 5. Implementation and present evidence

The corrected repository implements strict source-field validation, transactional writes, raw-response archives, sourced publication metadata, backward availability joins, prior-only thresholds, explicit daily entry/exit selection and event audits. It also provides locked dependencies, offline tests, CI, freshness checks and validated optional LLM explanations. LLM directional opinions are outside the proposed forecasting experiment.

The current engine produces descriptive conditional underlying-return summaries. It does **not** implement the PR/PQ/PA experiment, chronological position reconstruction, seasonal tightness, contract-level dollar outcomes, dependence-aware inference, or a costed portfolio. Continuous Yahoo close proxies lack the contract identity needed for the proposed design. Nonpositive-price windows are currently excluded, not economically modeled.

The subsequent [research-data audit](research-data-audit.md) adds a bounded publication-evidence ledger and read-only coverage diagnostics. It does not establish a complete common sample or change evaluation eligibility. Current crude inventory is the national commercial-stock series; the proposed Cushing seasonal-state test requires a separate series. Archived gas issues also demonstrate revisions, so publication dates and original values require separate verification.

The data-acquisition extension provides reproducible CFTC notice and EIA archive extraction, explicitly separating official index evidence from verified issue headers and recording unavailable or contradictory documents. CFTC actual-publication coverage and gas-release coverage remain sparse. A separate contract importer preserves signed settlements, original export bytes and checksums; its validation is not an exchange-calendar or first-vintage certification. The [Bloomberg lab protocol](bloomberg-export-guide.md) starts with six individual 2020 contracts before a broader historical request. An existing local natural-gas workbook has individual securities but lacks verified price-field and expiry metadata, so its values have not entered an experiment.

The initial correction pass passed **141 offline tests**; the subsequent data-acquisition branch passed **275 offline tests**. These are engineering checks, not tests of the proposed research hypotheses. The literature/design revision changes documentation only.

A local engineering validation run, `20261016T014316Z-934738f8`, recorded:

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

Major unresolved constraints are full-text verification of the closest forecasting papers, historical release evidence, original COT and inventory vintages, licensed contract/curve access and statistical power after both training stages in two weekly markets. COT categories aggregate traders and maturities; changes can reflect classification as well as trading. Neither conditional associations nor disclosure timing alone establishes causality. Additional markets should be a declared extension, not a search for favorable results.

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
2. Kang, W., Rouwenhorst, K. G., and Tang, K. (2020). *A Tale of Two Premiums: The Role of Hedgers and Speculators in Commodity Futures Markets.* [Institutional manuscript](https://www.carloalberto.org/wp-content/uploads/2018/11/Liquidityprovision-Luxembourg2.pdf). Reviewed copy is the 8 August 2018 draft; final published version remains to be checked.
3. Kang, W., Rouwenhorst, K. G., and Tang, K. (2021). *Crowding and Factor Returns.* [University-hosted working paper](https://acfr.aut.ac.nz/__data/assets/pdf_file/0003/634971/SSRN-id3803954.pdf).
4. Boos, D., and Grob, L. (2023). *Tracking Speculative Trading.* [Institutional record](https://digitalcollection.zhaw.ch/items/611d9f41-b601-4aad-a9bf-360b6b5dca2d).
5. Proskurin, O. (2021). *Does the CFTC Report Have Predictive Power: Machine Learning Approach.* DOI: 10.3905/jfds.2021.1.065. Timing comparison checked against the [publisher's issue introduction](https://www.pm-research.com/content/iijjfds/3/3/1.full.pdf); full article access was restricted.
6. Nikitopoulos, C. S., Thomas, A. C., and Wang, J. (2024). *Hedging Pressure and Oil Volatility: Insurance versus Liquidity Demands.* [Published article](https://doi.org/10.1002/fut.22470).
7. Giacomini, R., and White, H. (2006). *Tests of Conditional Predictive Ability.* [Published article](https://doi.org/10.1111/j.1468-0262.2006.00718.x).
8. Harvey, C. R., and Liu, Y. (2020). *False (and Missed) Discoveries in Financial Economics.* [arXiv:2006.04269](https://arxiv.org/abs/2006.04269).
9. CFTC (2009). Disaggregated historical-data release and original publication context. [Official announcement](https://www.cftc.gov/PressRoom/PressReleases/5737-09). See also [exceptional release announcements](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm).
10. EIA. [Weekly Petroleum Status Report archives](https://www.eia.gov/petroleum/supply/weekly/archive/) and [Weekly Natural Gas Storage Report methodology](https://ir.eia.gov/ngs/methodology.html).

11. Uhl, B. (2025). *Speculators and Time Series Momentum in Commodity Futures Markets.* Review of Financial Economics 43(2), 213–230. [Published version](https://www.econstor.eu/bitstream/10419/330168/1/RFE_RFE1228.pdf). DOI: 10.1002/rfe.1228.
12. Pradkhan, E. (2017). *Financial Activity in Agricultural Futures Markets: Evidence from Quantile Regressions.* AJARE 61(4), 610–625. [DOI](https://doi.org/10.1111/1467-8489.12222). Methods reviewed in the related 2016 dissertation chapter, not verified as identical to the final article; see the literature review.
13. Bosch, D. *The Information Content of Fundamental News vs. Traders’ Positions in Grain Futures Markets: Evidence from WASDE and COT Reports.* [SSRN record](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3334880), posted 2019. Reviewed version: the related chapter in *Essays on Pricing and Speculation in Commodity Markets*, printed pp. 90–127.
14. Yu, D., Chen, C., Wang, Y., and Zhang, Y. (2023). *Hedging Pressure Momentum and the Predictability of Oil Futures Returns.* [DOI](https://doi.org/10.1016/j.econmod.2023.106214). Publisher excerpts only; full-text verification pending.
15. Lin, B., Wu, J., and Zheng, Q. (2026). *Speculative Pressure, Extreme Connectedness, and Price Bubbles in Oil and Agricultural Commodity Markets.* [DOI](https://doi.org/10.1016/j.jcomm.2026.100561). Publisher abstract/sections only.
16. Ganepola, C. N., Zarei, A., and Tony-Okeke, U. (2025). *The Other Side of the Coin: Speculation in Bearish Natural Gas Markets.* [DOI](https://doi.org/10.1016/j.jcomm.2025.100514). Publisher abstract/sections only.
17. Zhang, N., Gong, Y., and Xue, X. (2023). *Less Disagreement, Better Forecasts: Adjusted Risk Measures in the Energy Futures Market.* [Published version](https://ueaeprints.uea.ac.uk/id/eprint/92163/1/Zhang_etal_2023_JFuturesMarkets.pdf). DOI: 10.1002/fut.22412.

## AI-assistance disclosure

OpenAI Codex assisted with source discovery, draft organization, methodological suggestions, code corrections and tests. AI-generated material can contain errors. The named author must verify references, implementation, data provenance, analysis and final wording before academic circulation or submission. No AI system is listed as an author, and no empirical results were generated or inferred by this draft.
