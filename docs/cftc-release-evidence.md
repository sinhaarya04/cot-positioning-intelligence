# CFTC release evidence and reproducible expansion

Reviewed 18 October 2026, America/New_York. The accompanying
[evidence CSV](../config/release_evidence_cftc.csv) contains **105 records**, up
from 22 in the pilot. Its 33 confirmed records cover **17 report/publication
pairs**: 16 in both Legacy and Disaggregated series, plus the Disaggregated launch
week. Six `available_by` records cover three further weeks. The remaining 32
scheduled and 34 superseded records preserve plans without treating them as
completed publications. All `release_at` fields remain blank.

The coverage remains sparse and insufficient for the planned experiment. Each
row links an observation date to publication evidence; none certifies the
values originally available. The [CFTC's own FAQ, section 5](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm)
says it does not maintain a historical release-date list and only the recent
13 months of release dates are available on its website. Expanding the whole
2009-onward sample therefore requires more than downloading observation-date
archives or regenerating ordinary Fridays.

## Confirmed dates

Except for the launch week, the dates below are directly paired in notices on the official
[COT Historical Special Announcements page](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm).
The CSV notes identify the relevant notice for each record. A general weekly
publication notice is represented once for each of `legacy` and `disagg`, with
`market=*`; this does not assert that every possible contract had a record.

| Report date | Confirmed publication date | Notice identifying the pair | Reason included |
| --- | --- | --- | --- |
| 2009-09-01 | 2009-09-04 | Launch notice and retrospective CFTC history | Disaggregated launch only; September 1 observation link is explicit |
| 2009-12-29 | 2010-01-04 | 2010-01-07 | Year-end observation and delayed Monday release; later Henry Hub Swap correction |
| 2010-04-20 | 2010-04-23 | 2010-04-28 | Explicit publication pair; later inclusion of two omitted contracts |
| 2010-05-18 | 2010-05-21 | 2010-05-27 | Explicit pair in correction notice |
| 2010-08-17 | 2010-08-20 | 2010-09-02 | Explicit pair in corn options correction notice |
| 2011-03-08 | 2011-03-11 | 2011-03-11 | Report explicitly published that day; platinum open-interest adjustment |
| 2011-05-24 | 2011-05-27 | 2011-05-27 | Report explicitly published that day; energy and currency adjustments |
| 2011-10-11 | 2011-10-14 | 2011-10-14 | Reports explicitly published that day; agricultural adjustments |
| 2012-01-10 | 2012-01-13 | 2012-01-13 | Report explicitly published that day; ICE gas adjustment |
| 2018-09-18 | 2018-09-21 | 2018-09-25 | Ordinary Friday publication, later Legacy concentration-ratio correction |
| 2019-03-26 | 2019-03-29 | 2019-04-03 | Ordinary Friday publication, later contract-specific corrections |
| 2019-10-15 | 2019-10-18 | 2019-10-24 | Ordinary Friday publication, later contract-specific corrections |
| 2020-12-21 | 2020-12-28 | 2020-12-28 | Monday observation and Monday publication around a holiday |
| 2023-01-31 | 2023-02-24 | 2023-02-24 | ION delay; report and publication dates both explicit |
| 2023-02-07 | 2023-03-03 | 2023-03-03 | ION delay; report and publication dates both explicit |
| 2023-02-14 | 2023-03-08 | 2023-03-08 | ION delay; report and publication dates both explicit |
| 2023-02-21 | 2023-03-10 | 2023-03-10 | ION delay; report and publication dates both explicit |

The launch row combines the explicit observation-date link in
[press release 5710-09](https://www.cftc.gov/PressRoom/PressReleases/5710-09)
with the retrospective confirmation of the September 4 launch in
[CFTC history](https://www.cftc.gov/About/HistoryoftheCFTC/history_2000s.html).
The prospective announcement alone would only support a planned launch.

These are report-wide publication facts. A notice describing a correction to a
different physical contract identifies the weekly publication event, without
claiming the correction applied to crude oil or NYMEX natural gas. The April 2010
late inclusions concern ICE Henry Hub `023391` and cocoa, rather than the study's
NYMEX natural gas `023651` and WTI `067651`. Market-specific omissions and field
revisions still require checking against the original report before modeling.

The ION notices describe issuance on their dated publication day and identify
the observation date in discussion of adjustments. Those explicit pairs support
the rows. The earlier [16 February 2023 postponement announcement](https://www.cftc.gov/PressRoom/PressReleases/8662-23)
expressed an intention to resume publication; it alone would not establish an
actual release. Similarly, the [10 February statement](https://www.cftc.gov/PressRoom/PressReleases/8655-23)
reported a continuing delay, not a completed release.

## Available-by bounds remain distinct

Three notices establish that some version of a report was already available by
the notice date, without identifying the original publication date:

| Report date | Available by notice date | Evidence |
| --- | --- | --- |
| 2012-11-27 | 2012-12-04 | Notice discusses missing trader classifications in the existing reports and plans an update |
| 2015-06-16 | 2015-06-22 | Notice describes formatting changes in the already released COT files and a forthcoming revision |
| 2017-03-28 | 2017-04-04 | Notice states that updated reports were published that day |

These six ledger rows are `available_by`, never `confirmed`. The audit may give
an upper bound at the end of the document's New York date, but there is no
known lower bound for the original release. They cannot anchor the proposed
pre-release forecast cutoff or an event study, and they do not make the current
database values original-vintage observations.

## Intended dates remain distinct

The expansion includes the complete two 2025 catch-up tables and preserves
the distinction between a plan and confirmed publication:

- The 17 June 2021 notice planned publication on 21 June for observations dated
  15 June. Both series remain `scheduled` because that prospective wording alone
  does not confirm the event.
- The 18 November 2025 catch-up table planned 12 December publication for the
  report dated **Monday, 10 November**. Those records are `superseded` because
  the later table changed the intended date.
- The 9 December 2025 table changed that intended publication to 10 December.
  Those records remain `scheduled`: the table explicitly describes intended
  publication dates. A past scheduled date is not automatically confirmed.

The December table has 13 report dates and the November table has 17. Each
appears for both Legacy and Disaggregated series. The full November plan version
is marked `superseded`, including unchanged dates and its now-obsolete proposed
January catch-up dates: the December plan anticipates a return to the normal
schedule on December 29. Both versions retain the original scheduled publication
date in the note. No row from either table becomes confirmed merely because its
calendar date is in the past.

Two additional explicit plans are included: the November 4, 2011 MF Global
notice schedules the November 8 observations for November 14, and
[press release 7864-19](https://www.cftc.gov/PressRoom/PressReleases/7864-19)
schedules the Monday December 24, 2018 observations for February 1, 2019.
The subsequent twice-weekly catch-up cadence in that release is not expanded
into presumed actual publications.

The two 2025 tables appear on the same
[official announcements page](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm).
Their changed plans illustrate why selecting the most recent date from a
schedule without preserving its status would be unsafe.

## Deliberately unresolved

The ION notices dated 14, 16 and 21 March 2023 confirm releases corresponding to
originally planned publication dates of 3, 10 and 17 March. They do not explicitly
give observation dates in those paragraphs. This pilot therefore excludes those
three mappings rather than subtracting three days or assuming a Tuesday. The
[historical viewable archive](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalViewable/index.htm)
explicitly labels its dates as report dates, not release dates; its existence does
not independently prove publication timing.

No time of day is inferred from the normal 3:30 p.m. convention. A confirmed
publication date cannot support an intraday availability timestamp. A future
daily-data policy may use an explicitly conservative bound after the whole
publication day, but that bound must remain labeled as a policy-derived bound,
not an observed release time.

Later corrections, adjusted ION reports and latest-vintage API values create a
separate vintage problem. Even after these dates are matched, research claiming
first-release information needs archived original values or a clearly stated
latest-vintage limitation. The wildcard rows concern report publication only;
they do not certify every field, every contract, or a later correction date.

## Source preservation

The announcements page was fetched successfully and archived locally under the
ignored directory `data/release_evidence_cftc/`. Its manifest records the source
URL, retrieval time, byte count and SHA-256. The archived HTML had 125,398 bytes
and SHA-256
`686f73dccf0dc0f9901a5325c833ed424b16b5ac748ba5bcbe641597ffe2d0de`.
Retrieval was 2026-10-19 02:10:44 UTC, which was 18 October in New York. The
snapshot is local supporting material and is not distributed with the CSV.

To expand the calendar, preserve source provenance, confirm the observation-date
link separately from the publication event, and keep prospective announcements
out of confirmed evidence. Historical coverage should be counted by matched
observations, with missing and conflicting records visible.

The additional four source pages were retrieved sequentially at
2026-10-19 02:51:16–17 UTC (18 October in New York). The content-addressed HTML
snapshots and `expansion-manifest.json` are under that same ignored directory.
The announcement snapshot for this expansion has SHA-256
`727e4ff3e8ffb2ef4eee557c76fb3f6d4940611f713df63fbd8cf5b163b37a46`.
Its byte count is 125,398; dynamic page bytes can differ from the earlier pilot
snapshot without changing the reviewed notice text. All four hashes, byte counts,
URLs and UTC retrieval times are recorded in the local manifest.

## Reproduce or extend

From the cloned repository, fetch the four reviewed official pages and write a
candidate ledger:

```bash
python -m src.expand_cftc_history --fetch --output output/cftc-evidence-expanded.csv
```

Omit `--fetch` to replay the locally archived bytes. The parser verifies the
snapshot hashes, requires each reviewed notice's date and publication-language
anchors, and checks the table headings, notice context, row counts and explicit
dates. A changed source fails instead of silently guessing. Existing IDs retain
their original notes; a conflicting fact under an existing ID fails. Successful
output is validated using the same ledger validator as the research audit.
The existing ledger is changed only when explicitly selected as `--output`.

The next acquisition step is a contemporaneous release archive: archived CFTC
announcement emails or a vendor's historical economic-release log, with report
reference dates and actual event timestamps. At the Bloomberg lab, ask whether
such history is available, how rescheduled and corrected observations are
represented, and whether exports may be retained for this research. The presence
of an ordinary date in a vendor calendar alone is not proof that it records the
actual event. Match and manually audit the 2013, 2018–19, 2023 and 2025 disruptions
before trusting any broad calendar reconstruction. This repository has not yet
acquired that history.
