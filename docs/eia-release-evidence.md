# EIA release evidence pilot

Reviewed October 18, 2026 (America/New_York). Source retrievals were at
2026-10-19 02:13–02:15 UTC. This is a bounded audit, not a complete historical
publication calendar or a reconstruction of first-release values.

The ledger is [config/release_evidence_eia.csv](../config/release_evidence_eia.csv).
It contains six confirmed WPSR issue dates and three **available-by** dates from
archived Natural Gas Weekly Updates (NGWU). All nine `release_at` fields are
empty: none of the inspected historical issue pages establishes a dated,
timezone-aware publication instant. A generic release schedule was not used to
fill the gap. These rows must not automatically become verified timestamps in
the existing evaluation pipeline.

## Match the evidence to the configured series

| Market | Configured series | Actual inventory concept |
| --- | --- | --- |
| `CRUDE_OIL` | `PET.WCESTUS1.W` | U.S. ending crude-oil stocks excluding the Strategic Petroleum Reserve, in thousand barrels |
| `NATURAL_GAS` | `NG.NW2_EPG0_SWO_R48_BCF.W` | Lower 48 working natural gas in underground storage, in billion cubic feet |

The crude series is national commercial inventory. **It is not Cushing
inventory.** The official [EIA series page](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=WCESTUS1&f=W)
establishes this identity. The working paper's proposed Cushing storage-state
interaction therefore requires a separate series and its own audit; changing a
label on the existing data would be incorrect. This pilot preserves the current
configuration.

## Evidence recorded

The WPSR archive header explicitly pairs the inventory week with the issue's
release date. The six rows include ordinary Wednesday issues and Thursday and
Friday issues during holiday periods. Each date below was read from the issue
itself rather than derived from the weekday of the observation.

| Inventory observation date | WPSR release date | Direct archived issue |
| --- | --- | --- |
| 2023-02-17 | 2023-02-23 | [February 23](https://www.eia.gov/petroleum/supply/weekly/archive/2023/2023_02_23/wpsr_2023_02_23.php) |
| 2023-02-24 | 2023-03-01 | [March 1](https://www.eia.gov/petroleum/supply/weekly/archive/2023/2023_03_01/wpsr_2023_03_01.php) |
| 2023-03-03 | 2023-03-08 | [March 8](https://www.eia.gov/petroleum/supply/weekly/archive/2023/2023_03_08/wpsr_2023_03_08.php) |
| 2024-11-08 | 2024-11-14 | [November 14](https://www.eia.gov/petroleum/supply/weekly/archive/2024/2024_11_14/wpsr_2024_11_14.php) |
| 2024-11-22 | 2024-11-27 | [November 27](https://www.eia.gov/petroleum/supply/weekly/archive/2024/2024_11_27/wpsr_2024_11_27.php) |
| 2024-12-20 | 2024-12-27 | [December 27](https://www.eia.gov/petroleum/supply/weekly/archive/2024/2024_12_27/wpsr_2024_12_27.php) |

The gas records have a weaker and deliberately separate interpretation. Each
NGWU issue explicitly publishes a table containing the observation date and
Lower 48 working-gas total. Its publication date proves the data were available
by that date. It does **not** independently establish the original WNGSR
publication date or time. These rows use `status=available_by`; their
`release_date` is the NGWU document date, not a first-release assertion.

| Inventory observation date | NGWU publication date / available-by date | Total shown (Bcf) | Direct archived issue |
| --- | --- | --- | --- |
| 2023-02-17 | 2023-02-23 | 2,195 | [February 23](https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/2023/02_23/) |
| 2023-02-24 | 2023-03-02 | 2,114 | [March 2](https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/2023/03_02/) |
| 2023-03-03 | 2023-03-09 | 2,030 | [March 9](https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/2023/03_09/) |

NGWU's headline week ends on a Wednesday and describes the market commentary.
The relevant inventory observation is the Friday date inside its storage table.
Confusing those dates would introduce a second alignment error. The quantities
above identify the inspected table; this pilot does not load archived values
into the database or certify the database's values as the same vintage.

## Revision evidence is separate from original publication evidence

A concrete example shows why issue dates alone are insufficient. For the same
2024-11-08 inventory observation, the archived
[November 14 NGWU](https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/2024/11_14/)
shows **3,974 Bcf**, while the prior-week column in the archived
[November 21 NGWU](https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/2024/11_21/)
shows **3,972 Bcf**. Both are preserved as separate source snapshots. Neither
number is overwritten or promoted to a canonical first-release value here.

EIA's [sample-reselection notice](https://ir.eia.gov/ngs/faqsamplechanges2024.html)
was originally issued October 31, 2024 and updated November 18, 2024. It
announced revisions to eight observation weeks, September 20 through November 8,
and a transition to the new sample. The FAQ contains inconsistent November 14
and November 15 wording for the next observation week; the November 21 issue's
storage table explicitly uses November 15. The announced revision time is not
converted into an actual release record in this ledger.

The [WNGSR revision policy](https://ir.eia.gov/ngs/revisions.html), labeled last
updated January 26, 2017, also allows routine and out-of-cycle changes. The
current API download is therefore a latest-vintage source. Joining one of the
dates above to a current API value does not recreate what a forecaster saw then.
An eventual vintage table needs observation date, source-document publication,
value, series identity, retrieval time, content hash and revision relationship.

## Coverage and reproducibility limits

The inspected [WPSR archive index](https://www.eia.gov/petroleum/supply/weekly/archive/)
contains issue links for 2011–2026. This is the range observed in that index,
not a claim that every issue was inspected or that older archives do not exist.
The [NGWU archive index](https://www.eia.gov/naturalgas/weekly/includes/archive.php)
lists years back to 1996, but NGWU is a separate publication and has missing
holiday editions. It cannot replace the WNGSR calendar without additional
evidence.

The [WNGSR methodology](https://ir.eia.gov/ngs/methodology.html), labeled last
updated September 10, 2018, explains the 2002 transition from AGA to EIA and the
2015 transition from three reporting regions to five. Five-region estimates
before that transition include retrospectively derived history. Extending the
repository's current 2010-onward gas pull therefore requires both series
continuity checks and a vintage audit, rather than treating a longer current
spreadsheet as contemporaneously published history.

Raw HTML and a retrieval manifest are stored locally under the ignored
`data/release_evidence_eia/` directory. The manifest records source URL, UTC
retrieval time, byte length and SHA-256. The ledger and these source hashes are
tracked; raw downloads are not. A hash identifies the downloaded page, not the
historical publication instant, and the current archive can itself be revised.

| Evidence ID | SHA-256 of downloaded HTML |
| --- | --- |
| `eia-wpsr-2023-02-23` | `0a3a057e94e4203fd900b892f5e3825069f7bea458b52c1fed44995be9c5e0cc` |
| `eia-wpsr-2023-03-01` | `5d95f290a1d20ff83082cb4c111aafca7063e0aab1f7ff1be24db6180921f728` |
| `eia-wpsr-2023-03-08` | `5728e43e3002c6e6ddd3dca541abbbd94fe4dbaf4ece4ebd1d4f7dd4eac447e7` |
| `eia-wpsr-2024-11-14` | `bb8ead386028b18685a890a1d1a65a99d85f33a971984212c51681398cd4ee6a` |
| `eia-wpsr-2024-11-27` | `0807efb2eabc83e3da9612819b73f2cc2e4d7dcf710f6d68febb5df9789c9c91` |
| `eia-wpsr-2024-12-27` | `54f5996fcb0271671c88b6f9c0f3a4131e80282d062e8625aadee0a84053cc1f` |
| `eia-ngwu-2023-02-23` | `c26c2d0b471b98fe7bab251c8cfb226c3323812d5eb9eef2a261e90dd55dd965` |
| `eia-ngwu-2023-03-02` | `14303458525254c6d65c062160a43f3be4e7eef958ba6e2c91ab3103b039982b` |
| `eia-ngwu-2023-03-09` | `5f30a01d6a6baa3d9df2e4e8c2fecd8476001bc534cbb31b504b016d1bec3310` |
| `revision-comparison-ngwu-2024-11-14` | `59b7f10fa8a7c9c9b2252c28fb46fd9ae63b50f2944b1a041ade1e78ffb2b85b` |
| `revision-comparison-ngwu-2024-11-21` | `319472d0657f1a1bdca104daeb764c29a42f0e900d655101587f874d101a09a3` |

The next expansion should reconstruct source values alongside dates for the
overlapping February–March 2023 CFTC pilot, retain successive revisions, and
seek dated original WNGSR notices or report snapshots. The present evidence
can support a coverage audit; it cannot support an intraday event study or
publication-quality first-vintage forecasting claims.
