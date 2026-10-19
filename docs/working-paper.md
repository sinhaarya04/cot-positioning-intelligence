# What Remains in a Delayed COT Report? Public News and Energy Risk

**Aryan Sinha**

**Preliminary research design and methods draft - contribution revision 19 October 2026 (America/New_York)**

**Status:** Proposed empirical study. No forecasting experiment, estimated information value or evidence of trading profitability. This draft has not been submitted or peer reviewed. The software implements data ingestion, validation and descriptive evaluation; the comparisons below remain to be implemented. The pending Proskurin full-text review is a prerequisite to freezing the experiment.

## Abstract

Does public information arriving between the observation and publication of trader positions substitute for the official disclosure, or make it more useful? This study proposes a controlled forecasting comparison for WTI crude oil and Henry Hub natural gas. Four forecasts use an earlier or later public information set, each with and without the same newly disclosed managed-money statistic. Every forecast is issued after publication and evaluated on the same subsequent five-session contract outcome. The primary contrast measures how the incremental contribution of the statistic changes when information arriving during the reporting lag is admitted. Separate position reconstructions test whether that information also makes the statistic easier to estimate. The design distinguishes reconstructibility from risk relevance without assuming that information sources must be substitutes. It uses chronological estimation, actual publication evidence, original vintages and a common quantile-loss score. This is a proposed empirical contribution about information redundancy and complementarity, not a new estimator or a causal evaluation of earlier disclosure. Novelty, data feasibility and statistical precision remain unresolved.

## 1. Research question and contribution

**Does news arriving during the COT reporting lag make the eventual positioning disclosure redundant for energy risk forecasts, or make it more informative?**

The economic object is the marginal usefulness of a delayed position statistic in a changing public information environment. The report is freely available after publication, so avoiding access to it is not the motivation. The question is whether its contribution survives the intervening news, and whether better ability to infer positions explains its predictive redundancy. A position can be difficult to infer yet irrelevant to the chosen risk outcome. Conversely, a report may become easier to estimate but more useful when new information provides context. Neither possibility follows from a reconstruction accuracy score.

The CFTC's May 2026 consultation explicitly asked about the reporting lag and more frequent publication [19, questions 1, 2 and 6–7]. This provides institutional motivation. Our experiment holds publication and outcomes fixed; it cannot estimate the welfare effect of publishing earlier, assess confidentiality costs, or recommend a new release schedule.

**Proposed contribution paragraph.** We examine whether public information arriving during a positioning report's publication lag substitutes for or complements the reported statistic in forecasting subsequent energy risk. We hold the forecast origin, contract and outcome fixed and vary access to intervening public information and the newly disclosed statistic. We separately measure whether intervening information improves reconstruction of that same statistic. The contribution sought is evidence distinguishing a report becoming easier to infer from it becoming less useful for risk assessment. These are empirical questions, not claims that a new statistical method has been invented.

The [literature assessment](literature-gap-review.md) records versions, inspected sections and access limitations. Boos and Grob [4] reconstruct positions before publication. Wang [18] relates expected and unexpected positions to contemporaneous volatility. Kang, Rouwenhorst and Tang [2] examine post-publication returns and rolling momentum residuals. Pradkhan [12] studies position information at return quantiles. Yu et al. [14] adds hedging-pressure momentum to return forecasts; Nikitopoulos et al. [6], Lin et al. [15] and Ganepola et al. [16] address related risk and state questions. None of these ingredients is our novelty claim.

Mulligan and Steenkamp [20] already discuss limited information after publication and evaluate foreign-exchange forecasts. Proskurin's editorial summary [5] describes hypothetical Tuesday versus Friday availability. Our proposed contrast is a common-origin, common-outcome information comparison, not a comparison of Tuesday and Friday trading horizons. Its exact separation from Proskurin remains unverified until the article arrives. A four-model comparison by itself is routine; a robust, economically interpretable result is required for a substantial contribution. A focused search cannot certify priority or publication prospects.

## 2. Data, information clocks and target

### 2.1 Statistic and information sets

The initial markets are WTI crude oil and Henry Hub natural gas. Futures-only Disaggregated COT managed-money net positions divided by total open interest define `q_t`. The subscript denotes the observation date, usually Tuesday. Reconstructions always target that same Tuesday statistic; they do not estimate positions currently held on Friday. COT aggregates across maturities, so contract-specific risk outcomes do not imply contract-specific position observations.

Define an early cutoff `c_E`, a late cutoff `c_L` before actual publication, the actual publication time `r_t`, and one common forecast time `f_t` after publication. For regular Tuesday observations, the daily protocol uses Wednesday 00:00 America/New_York for `c_E`, admitting only data demonstrably available by then. It is not permission to include Tuesday exchange open interest published later. Exceptional observations require the corresponding next-calendar-day cutoff and documented availability.

`X_E` contains only the public values available at the early cutoff. `Z` contains prespecified updates first available between the two cutoffs: same-contract price changes, volatility and curve updates, exchange volume/open interest where available, and released inventory information. `X_L = (X_E, Z)` retains the early values explicitly; it does not overwrite them. Neither set may contain any field first disclosed in the current COT publication batch. Previously released commercial slow/fast pressure, managed-money positions, momentum and seasonality belong in the public controls.

The preferred late cutoff is immediately before verified publication. With date-only evidence, the conservative daily variant uses 00:00 on the actual release date. This excludes release-day public news and cannot represent the complete pre-release information set. Each comparison must identify which variant it uses. Never invent timestamps or silently admit date-only evidence to the current timestamp-based software.

All four forecasts are constructed at the same `f_t`, using the same eligible historical training labels and tuning rules. The early-set forecasts deliberately withhold the intervening predictors; they are diagnostic information restrictions at the common forecast origin. **The early-set model containing `q_t` is not a feasible Tuesday forecast or an estimate of what early publication would have achieved.** No current report is supplied to any model before it actually arrives.

### 2.2 Availability and publication batches

Disaggregated publication began in September 2009 [9]. Earlier backfilled history was not publicly available at its observation dates. It may enter subsequent training only after documented release under a declared alternative. Each value needs observation time, availability evidence, retrieval time, hash and vintage class. Current historical API values do not establish first-release values. Without defensible original vintages, label the affected analysis a revised-data sensitivity rather than a real-time disclosure test.

Use regular, individually published observations for the primary comparison. Holiday shifts with documented single releases remain eligible if `c_E < c_L < r_t < f_t`. Exceptional backlogs are a prespecified sensitivity: identify the publication batch, target its newest observation and exclude every newly published field from the public inputs. Use one forecast per market and batch; if batches reuse an entry session, retain the latest under a fixed rule. Multiple old reports and maturities are not independent announcements. Delay episodes are not a natural experiment.

### 2.3 Contract and risk outcome

All models share the first admissible settlement strictly after the release date, with forecasts issued before that benchmark. This estimates predictive usefulness surviving the daily entry convention, not the immediate announcement response or an executable fill. A separately declared sensitivity refreshes public information for all models consistently before entry; it cannot replace the prespecified lag-information contrast.

Select the nearest contract with at least ten exchange sessions to expiry at entry, using scheduled metadata known at the early cutoff, and hold that same contract for five sessions. Exclude cases where the common contract cannot be selected without later market data. The outcome is its signed contract-dollar price change divided by a strictly positive dollar-volatility scale fixed using only early-cutoff information. That common early scale prevents later volatility from entering the restricted forecasts through normalization. Same-contract increments form predictors; neither rolls nor division by a price crossing zero is admissible.

Forecast the conditional 10th and 90th percentiles of this outcome. Average their pinball losses equally and aggregate with equal market weights on common eligible dates. Show each tail, market and calibration result as well. These are moderate tail-risk forecasts, not evidence about rare 1% disasters. Mean returns, other horizons and costed trading exercises are outside the primary claim.

## 3. A test that distinguishes the competing explanations

### 3.1 Four risk forecasts

Use one prespecified regularized quantile-regression family, comparable tuning budgets and identical chronological outer folds. Public controls include signed price changes, momentum, volatility, curve spreads, released inventories, seasonality and previously disclosed positioning. Match the 1, 2, 4, 12, 24 and 50-week price-momentum horizons emphasized by Yu [14], along with release-safe commercial hedging-pressure momentum. Its denominator differs from `q_t`; document the distinction. Signed-price adaptations are not exact replications.

| Forecast | Inputs | Question |
|---|---|---|
| E0 | `X_E` | What can the earlier public predictors explain? |
| E1 | `X_E, q_t` | What does the newly published statistic add to those predictors? |
| L0 | `X_E, Z` | What can the updated public predictors explain? |
| L1 | `X_E, Z, q_t` | What does the statistic add after those updates? |

The risk models use direct public predictors, not estimated positions. All four are trained separately for their corresponding inputs. A prespecified nonlinear sensitivity must permit interactions in both public-only and report-augmented models; otherwise a result about complementarity could merely reflect an overly restrictive additive specification. Fix this model class and its tuning budget using training data, not whichever choice produces a preferred contrast. Historical quantiles, volatility-scaled quantiles and a heavy-tailed volatility model provide basic adequacy checks.

### 3.2 Primary contrast and remaining report value

For the common loss `L`, define:

```text
V_E = mean[L(E0) - L(E1)]
V_L = mean[L(L0) - L(L1)]
H   = V_E - V_L
```

`H` is the **single primary contrast**, estimated directly from the paired four-model loss differences. It asks whether adding intervening public predictors reduces or increases the marginal contribution of the disclosed statistic. Publish all four loss levels, both gains and their joint uncertainty. A difference between two separately reported p-values is not a test of `H`.

- `H > 0` is consistent with predictive substitution: the statistic helps less with the updates present.
- `H < 0` is consistent with predictive complementarity: the statistic helps more with the updates present.
- An imprecise `H` does not distinguish these explanations.

Interpret the component gains before applying these labels. For example, a positive `H` produced solely by severe deterioration in L1 is a model failure warning, not convincing evidence that news replaces the report. Require competitive public baselines and robustness to the prespecified model family. `V_L` is the required companion estimate of how much usefulness remains with the late public set. These are forecast-procedure-specific quantities; learned models can deliver negative gains even though an ideal decision maker could ignore an unhelpful extra signal.

Use the unscaled paired difference as the primary estimand. If reporting percentage effects, divide every component by the same strictly positive training-fixed loss reference; different denominators would distort the interaction. Freeze meaningful margins for `H` and `V_L` using the intended risk application and training-period simulations. A tight upper confidence bound for `V_L` below its practical margin supports limited incremental value within this design. Insignificance alone does not establish redundancy. A statistically detectable but practically trivial contrast is insufficient for the substantive claim.

**Identification boundary.** All four models face the same actual publication time, future horizon, contract, outcome scale and training opportunities. This removes changes in those objects from the comparison. It does not randomize news, identify causal market learning, measure private information or estimate the effect of reducing the reporting lag. Intervening news may change how positions matter rather than reveal positions. Public inputs are a declared, finite set, not everything all market participants knew.

### 3.3 Separate reconstruction diagnostic

Independently estimate `q_hat_E` from `X_E` and `q_hat_L` from `X_E, Z`, targeting the same `q_t`. The second model must not have more recently disclosed training labels than the first for that event. Fit both using labels available at the early cutoff and freeze the resulting functions before observing the intervening inputs; apply the late model only when those inputs arrive. This isolates updating the inputs from updating the estimation sample. At historical training events, every feature must have the availability it would then have had.

Compare persistence, a simple lagged-position autoregression/ARIMA motivated by Wang, a Boos–Grob-inspired smooth trend model, and one regularized public-feature extension. Choose specifications by earlier chronological position-error validation alone. Do not select replicas for a favorable downstream risk result. Account for availability of the open-interest denominator and label signed-price adaptations. Kang's rolling decomposition includes the current position in estimation; our pre-release reconstructions cannot.

On the same eligible events, report level and change errors, bias and:

```text
R = mean[(q_t - q_hat_E)^2 - (q_t - q_hat_L)^2]
```

A positive `R` means the added inputs improved reconstruction in the declared models. It need not accompany positive `H`. Improving our estimate of a statistic and reducing its usefulness for predicting another outcome are different propositions.

| Pattern, subject to uncertainty and model adequacy | Defensible interpretation |
|---|---|
| `R > 0`, `H > 0`, and small tightly bounded `V_L` | Consistent with intervening public inputs making positions easier to reconstruct and the disclosure predictively redundant. It does not establish causal mediation. |
| `R > 0` with a materially positive `V_L` | Better reconstruction still leaves useful risk information in the report. |
| Materially negative `H` and positive `V_L` | Public updates and the position statistic are predictive complements; an automatic information-decay story is inadequate. |
| Large reconstruction errors at both cutoffs and small tightly bounded `V_L` | Hard-to-reconstruct positions need not be relevant to this risk target. This does not prove positions became stale or never mattered. |
| Wide intervals or instability across credible models | The proposed mechanism is unresolved; report a pilot or redesign before any broader claim. |

These are rival possible outcomes, not findings. The contribution requires interpretable effect sizes and uncertainty, not choosing whichever row looks interesting afterward. A positive reconstruction score alone is not a paper about disclosure value.

### 3.4 Scope discipline

The earlier reported-versus-reconstructed forecast comparison is retained only as a potential secondary extension. It requires chronological generated features and additional downstream training history; it cannot silently inherit the larger primary sample. Likewise, reconstruction-uncertainty regimes, inventory-tightness interactions, different trader categories and additional maturities are deferred. They are not alternative paths to statistical significance if the primary contrast is weak.

An empirical claim about redundancy of this managed-money statistic does not value every field in a COT release. A claim of private information, causal price pressure, crowding amplification or optimal disclosure policy would require a different identification design. A theoretical value-of-information decomposition is not claimed as new here.

## 4. Evaluation, feasibility and decision gates

Use chronological expanding estimation, annual outer evaluation blocks and common calendar folds across markets. The four direct risk models require at least five years of historical event/outcome pairs before evaluation. With a conservative post-September-2009 start, complete annual evaluation blocks could begin in 2015, subject to original-vintage coverage, feature availability, validation history and finished labels. This is an earliest design boundary, not a count of currently eligible data.

This differs from the earlier two-stage proposal for a specific reason: the primary risk models now contain no generated position estimates. Reconstructions are parallel diagnostics, not regressors in a downstream training stage. Any later forecast trained on reconstructed positions still needs both burn-ins; under the earlier five-plus-five-year rule its earliest full annual evaluation is about 2020. Freeze sample rules before opening outcomes and never compare model losses on different event sets. If the reconstruction diagnostic has fewer eligible dates, also recompute the four-model contrast on that shared subset and label it separately.

Before estimation, count unique publication events, training rows, evaluation rows, tail observations and exclusions by market and vintage. Run training-based or synthetic power simulations for the paired four-model contrast, preserving common shocks and serial dependence. If the sample cannot distinguish a practical contrast, simplify the model or report a pilot; do not search extra commodities or regimes for significance. Ordinary events, not a handful of exceptional delays, must support the main result.

Purge any historical label whose five-session outcome is unfinished at the forecast cutoff, including inner tuning. Fit transformations and model choices within permitted training history. Archive the report/batch, both public snapshots, contract, common scale, model versions, forecasts and outcome end time for each event. The simulation audit must include redundant and complementary information cases, so that model limitations or the inference procedure cannot mechanically predetermine the sign of the primary contrast.

Use common-calendar block resampling of the four losses together, preserving serial dependence, overlapping outcomes and cross-market shocks. Two markets do not supply a large independent-cluster sample. Specify whether inference conditions on the realized forecasts or re-estimates the learning process, and validate finite-sample behavior in simulation. Conditional predictive-ability methods [7] inform this choice. Report the single primary `H`, companion estimates with simultaneous intervals, and the reconstruction diagnostic as a prespecified secondary family; log every specification [8].

Sensitivity checks cover the declared nonlinear family, original versus latest values, omitted release-day information, entry delay, contracts, missingness and exceptional batches. The held-out comparison must not select the specification or practical margin. A finding confined to one crisis episode or one weak public model does not establish the intended contribution.

The immediate gates are: complete Proskurin; establish the exact distinction from its timing experiment; validate the Bloomberg contract pilot and both public snapshots; audit original vintages and sample size; then freeze models, margins and inference. No held-out empirical experiment starts before these gates. Historical evaluation will remain pseudo-out-of-sample. Prospective forecasts after protocol freeze can verify the process, while a short live record cannot establish statistical significance.

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

Major unresolved constraints are the pending Proskurin full text, historical release evidence, original COT and inventory vintages, licensed contract/curve access and statistical power for the paired four-model contrast in two weekly markets. The expanded full-text review specifies its coverage and uninspected supplements in the literature assessment; it is not an exhaustive novelty certification. No paper's empirical results were independently replicated in this review. COT categories aggregate traders and maturities; changes can reflect classification as well as trading. Neither conditional associations nor disclosure timing alone establishes causality. Additional markets should be a declared extension, not a search for favorable results.

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
2. Kang, W., Rouwenhorst, K. G., and Tang, K. (2020). *A Tale of Two Premiums: The Role of Hedgers and Speculators in Commodity Futures Markets.* The Journal of Finance 75(1), 377–417. [Published article](https://doi.org/10.1111/jofi.12845). Final main article and Internet Appendix Tables IA.V–VI checked through Northeastern University; supersedes the earlier draft-only assessment.
3. Kang, W., Rouwenhorst, K. G., and Tang, K. (2021). *Crowding and Factor Returns.* [University-hosted working paper](https://acfr.aut.ac.nz/__data/assets/pdf_file/0003/634971/SSRN-id3803954.pdf).
4. Boos, D., and Grob, L. (2023). *Tracking Speculative Trading.* [Institutional record](https://digitalcollection.zhaw.ch/items/611d9f41-b601-4aad-a9bf-360b6b5dca2d).
5. Proskurin, O. (2021). *Does the CFTC Report Have Predictive Power: Machine Learning Approach.* DOI: 10.3905/jfds.2021.1.065. Timing comparison checked against the [publisher's issue introduction](https://www.pm-research.com/content/iijjfds/3/3/1.full.pdf); complete article requested through Northeastern interlibrary loan on 19 October 2026, pending receipt and review.
6. Nikitopoulos, C. S., Thomas, A. C., and Wang, J. (2024). *Hedging Pressure and Oil Volatility: Insurance versus Liquidity Demands.* [Published article](https://doi.org/10.1002/fut.22470).
7. Giacomini, R., and White, H. (2006). *Tests of Conditional Predictive Ability.* [Published article](https://doi.org/10.1111/j.1468-0262.2006.00718.x).
8. Harvey, C. R., and Liu, Y. (2020). *False (and Missed) Discoveries in Financial Economics.* [arXiv:2006.04269](https://arxiv.org/abs/2006.04269).
9. CFTC (2009). Disaggregated historical-data release and original publication context. [Official announcement](https://www.cftc.gov/PressRoom/PressReleases/5737-09). See also [exceptional release announcements](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm).
10. EIA. [Weekly Petroleum Status Report archives](https://www.eia.gov/petroleum/supply/weekly/archive/) and [Weekly Natural Gas Storage Report methodology](https://ir.eia.gov/ngs/methodology.html).

11. Uhl, B. (2025). *Speculators and Time Series Momentum in Commodity Futures Markets.* Review of Financial Economics 43(2), 213–230. [Published version](https://www.econstor.eu/bitstream/10419/330168/1/RFE_RFE1228.pdf). DOI: 10.1002/rfe.1228.
12. Pradkhan, E. (2017). *Financial Activity in Agricultural Futures Markets: Evidence from Quantile Regressions.* AJARE 61(4), 610–625. [DOI](https://doi.org/10.1111/1467-8489.12222). Final published main article, Tables 1–4 and methodological notes checked through Northeastern University; supersedes reliance on the 2016 dissertation chapter.
13. Bosch, D. *The Information Content of Fundamental News vs. Traders’ Positions in Grain Futures Markets: Evidence from WASDE and COT Reports.* [SSRN record](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3334880), posted 2019. Reviewed version: the related chapter in *Essays on Pricing and Speculation in Commodity Markets*, printed pp. 90–127.
14. Yu, D., Chen, C., Wang, Y., and Zhang, Y. (2023). *Hedging Pressure Momentum and the Predictability of Oil Futures Returns.* Economic Modelling 121, 106214. [DOI](https://doi.org/10.1016/j.econmod.2023.106214). Full published HTML reviewed through Northeastern University on 19 October 2026: sections 1–7, equations 1–22, Tables 1–13 and methodological footnotes; Table 6 visually checked. See the literature review for timing limitations and comparator implications.
15. Lin, B., Wu, J., and Zheng, Q. (2026). *Speculative Pressure, Extreme Connectedness, and Price Bubbles in Oil and Agricultural Commodity Markets.* Journal of Commodity Markets 42, 100561. [DOI](https://doi.org/10.1016/j.jcomm.2026.100561). Published full-text methods, main results, robustness and embedded appendix reviewed; external Word supplement not inspected.
16. Ganepola, C. N., Zarei, A., and Tony-Okeke, U. (2025). *The Other Side of the Coin: Speculation in Bearish Natural Gas Markets.* Journal of Commodity Markets 40, 100514. [DOI](https://doi.org/10.1016/j.jcomm.2025.100514). Published full-text methods, main results, robustness discussion and embedded appendices reviewed; see the literature assessment for exact scope.
17. Zhang, N., Gong, Y., and Xue, X. (2023). *Less Disagreement, Better Forecasts: Adjusted Risk Measures in the Energy Futures Market.* [Published version](https://ueaeprints.uea.ac.uk/id/eprint/92163/1/Zhang_etal_2023_JFuturesMarkets.pdf). DOI: 10.1002/fut.22412.
18. Wang, C. (2002). *The Effect of Net Positions by Type of Trader on Volatility in Foreign Currency Futures Markets.* Journal of Futures Markets 22(5), 427–450. [Author-deposited published PDF](https://mpra.ub.uni-muenchen.de/36428/1/WangJFMNet2003.pdf). DOI: 10.1002/fut.10021. The repository cover predates publication; the reviewed typeset article is the 2002 version.
19. CFTC (2026). *Review of the Commitments of Traders Reporting Program.* Request for comment, 91 FR 24207–24210, 5 May 2026. [Official notice](https://www.govinfo.gov/content/pkg/FR-2026-05-05/pdf/2026-08743.pdf). Questions 1, 2, 6–7 and 10 motivate the timing issue; the notice does not establish the effects of a changed policy.
20. Mulligan, N., and Steenkamp, D. (2018). *Reassessing the Information Content of the Commitments of Traders Positioning Data for Exchange Rate Changes.* RBNZ Analytical Note AN2018/03. [Official PDF](https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/publications/analytical-notes/2018/an2018-03.pdf). Targeted web-PDF review of sections 4–6, equations 1–3 and Tables 2–6; local retrieval remained denied. Not a full appendix audit.

## AI-assistance disclosure

OpenAI Codex assisted with source discovery, draft organization, methodological suggestions, code corrections and tests. AI-generated material can contain errors. The named author must verify references, implementation, data provenance, analysis and final wording before academic circulation or submission. No AI system is listed as an author, and no empirical results were generated or inferred by this draft.
