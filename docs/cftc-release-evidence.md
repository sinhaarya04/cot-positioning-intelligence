# CFTC release evidence pilot

Reviewed 18 October 2026, America/New_York. The accompanying
[evidence CSV](../config/release_evidence_cftc.csv) contains 22 records: 16 confirmed
records covering eight publication dates in both Legacy and Disaggregated series,
four scheduled records, and two superseded schedule records. All evidence is
date-only: `release_at` is deliberately blank throughout.

This is a bounded audit fixture, not a complete historical calendar or a usable
training sample. Each row links a report's observation date to evidence about
publication. It does not certify the values originally available at publication.

## Confirmed dates

The dates below are directly paired in dated notices on the official
[COT Historical Special Announcements page](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm).
The CSV notes identify the relevant notice for each record. A general weekly
publication notice is represented once for each of `legacy` and `disagg`, with
`market=*`; this does not assert that every possible contract had a record.

| Report date | Confirmed publication date | Notice identifying the pair | Reason included |
| --- | --- | --- | --- |
| 2018-09-18 | 2018-09-21 | 2018-09-25 | Ordinary Friday publication, later Legacy concentration-ratio correction |
| 2019-03-26 | 2019-03-29 | 2019-04-03 | Ordinary Friday publication, later contract-specific corrections |
| 2019-10-15 | 2019-10-18 | 2019-10-24 | Ordinary Friday publication, later contract-specific corrections |
| 2020-12-21 | 2020-12-28 | 2020-12-28 | Monday observation and Monday publication around a holiday |
| 2023-01-31 | 2023-02-24 | 2023-02-24 | ION delay; report and publication dates both explicit |
| 2023-02-07 | 2023-03-03 | 2023-03-03 | ION delay; report and publication dates both explicit |
| 2023-02-14 | 2023-03-08 | 2023-03-08 | ION delay; report and publication dates both explicit |
| 2023-02-21 | 2023-03-10 | 2023-03-10 | ION delay; report and publication dates both explicit |

The ION notices describe issuance on their dated publication day and identify
the observation date in discussion of adjustments. Those explicit pairs support
the rows. The earlier [16 February 2023 postponement announcement](https://www.cftc.gov/PressRoom/PressReleases/8662-23)
expressed an intention to resume publication; it alone would not establish an
actual release. Similarly, the [10 February statement](https://www.cftc.gov/PressRoom/PressReleases/8655-23)
reported a continuing delay, not a completed release.

## Intended dates remain distinct

Three schedule facts are included to exercise the distinction between a plan
and confirmed publication:

- The 17 June 2021 notice planned publication on 21 June for observations dated
  15 June. Both series remain `scheduled` because that prospective wording alone
  does not confirm the event.
- The 18 November 2025 catch-up table planned 12 December publication for the
  report dated **Monday, 10 November**. Those records are `superseded` because
  the later table changed the intended date.
- The 9 December 2025 table changed that intended publication to 10 December.
  Those records remain `scheduled`: the table explicitly describes intended
  publication dates. A past scheduled date is not automatically confirmed.

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
