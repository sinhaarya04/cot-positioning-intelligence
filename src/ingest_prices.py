"""Daily Yahoo price proxies and EIA inventory ingestion.

Yahoo continuous prices are descriptive proxies, not contract-level traded P&L.
EIA_API_KEY is read from the environment; no credentials belong in source.
"""
import json
import os
import numpy as np
import pandas as pd
import requests

from src.availability import attach_release_metadata
from src.db import MARKET_CONFIG, init_schema, write_frame
from src.provenance import save_snapshot

EIA_PAGE_SIZE = 5000


def parse_futures_prices(frame: pd.DataFrame, market: str) -> pd.DataFrame:
    """Normalize daily bars without inventing an intraday availability time."""
    if frame.empty:
        raise ValueError(f"No daily prices returned for {market}")
    df = frame.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if not df.columns.is_unique or "Close" not in df:
        raise ValueError("Expected one ticker with a unique Close column")
    dates = pd.to_datetime(df.index, errors="raise")
    values = pd.to_numeric(df["Close"], errors="raise")
    if np.isinf(values.to_numpy(dtype=float, na_value=np.nan)).any():
        raise ValueError("Infinite price")
    result = pd.DataFrame({"price_date": dates.date, "market": market,
                           "close_price": values.to_numpy()})
    volume = pd.to_numeric(df.get("Volume", pd.Series(np.nan, index=df.index)), errors="raise")
    valid = volume.dropna()
    if ((valid < 0) | (valid % 1 != 0) | ~np.isfinite(valid)).any():
        raise ValueError("Invalid price volume")
    result["volume"] = pd.array(volume.to_numpy(), dtype="Int64")
    result["price_at"] = pd.NaT
    result["price_kind"] = "daily_close_proxy"
    result["source"] = "yahoo_finance"
    result["ingested_at"] = pd.Timestamp.now(tz="UTC")
    if result.duplicated(["price_date", "market"]).any():
        raise ValueError("Duplicate daily price dates")
    result = result.dropna(subset=["close_price"]).sort_values("price_date").reset_index(drop=True)
    if result.empty:
        raise ValueError("No nonmissing closing prices")
    return result


def ingest_futures_prices(markets=None):
    import yfinance as yf
    init_schema()
    counts, failures = {}, []
    for market in markets or MARKET_CONFIG:
        try:
            ticker = MARKET_CONFIG[market]["yf_ticker"]
            raw = yf.download(ticker, period="max", interval="1d", auto_adjust=False, progress=False)
            if raw.empty:
                raise ValueError("Empty download")
            save_snapshot("yahoo_daily", market, json.loads(raw.reset_index().to_json(date_format="iso")))
            normalized = parse_futures_prices(raw, market)
            # Upsert daily bars while the storage helper removes only obsolete
            # weekly rows. A shortened provider response cannot erase daily history.
            write_frame("futures_prices", normalized)
            counts[market] = len(normalized)
            print(f"{market}: {len(normalized)} daily close proxies (not contract-level prices)")
        except Exception as error:
            failures.append(f"{market}: {type(error).__name__}")
    if failures:
        raise RuntimeError("Price ingestion incomplete: " + "; ".join(failures))
    return counts


def fetch_eia_records(series_id: str, api_key: str, page_size=EIA_PAGE_SIZE) -> list[dict]:
    if not api_key or not 1 <= page_size <= EIA_PAGE_SIZE:
        raise ValueError("EIA key and a page size between 1 and 5000 are required")
    records, offset, expected = [], 0, None
    seen = set()
    while True:
        params = {"api_key": api_key, "frequency": "weekly", "data[0]": "value",
                  "sort[0][column]": "period", "sort[0][direction]": "asc",
                  "length": page_size, "offset": offset}
        try:
            response = requests.get(f"https://api.eia.gov/v2/seriesid/{series_id}", params=params, timeout=60)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            # requests exceptions can contain the URL, including the key.
            raise RuntimeError("EIA request failed; check connectivity, series and credentials") from None
        if not isinstance(payload, dict) or payload.get("error"):
            raise ValueError("EIA returned an error or malformed payload")
        body = payload.get("response", {})
        batch = body.get("data")
        if not isinstance(batch, list):
            raise ValueError("EIA response is missing its data array")
        if body.get("total") is not None:
            total = int(body["total"])
            if total < 0 or (expected is not None and total != expected):
                raise ValueError("EIA total changed during pagination; retry the download")
            expected = total
        save_snapshot("eia", series_id, payload)
        for row in batch:
            if not isinstance(row, dict) or not row.get("period"):
                raise ValueError("EIA row has no period")
            if row["period"] in seen:
                raise ValueError("Duplicate EIA periods or repeated pagination page")
            seen.add(row["period"])
        records.extend(batch)
        offset += len(batch)
        if expected is not None:
            if offset > expected:
                raise ValueError("EIA returned more rows than its declared total")
            if offset == expected:
                break
            if not batch:
                raise ValueError("EIA ended before its declared total")
        elif len(batch) < page_size:
            break
    if not records:
        raise ValueError("EIA returned no inventory history")
    return records


def parse_eia_records(records, market, series_id, calendar_path=None):
    if not records:
        raise ValueError("No EIA records")
    frame = pd.DataFrame(records)
    if not {"period", "value"}.issubset(frame.columns):
        raise ValueError("EIA records require period and value fields")
    dates = pd.to_datetime(frame.period, format="%Y-%m-%d", errors="raise")
    raw_values = frame.value.replace({"": None, "NA": None, "N/A": None, "--": None, "null": None})
    values = pd.to_numeric(raw_values, errors="raise").astype(float)
    if np.isinf(values).any() or (values.dropna() < 0).any():
        raise ValueError("Inventory levels must be finite and nonnegative")
    result = pd.DataFrame({"report_date": dates.dt.date, "commodity": market,
                           "series_id": series_id, "inventory_level": values})
    if result.report_date.duplicated().any():
        raise ValueError("Duplicate EIA observation periods")
    result = result.sort_values("report_date").reset_index(drop=True)
    result["weekly_change"] = result.inventory_level.diff()
    consecutive = pd.to_datetime(result.report_date).diff().eq(pd.Timedelta(days=7))
    result.loc[~consecutive, "weekly_change"] = np.nan
    return attach_release_metadata(result, "eia", market_column="commodity", calendar_path=calendar_path)


def ingest_eia_inventory(api_key=None, markets=None, calendar_path=None):
    api_key = api_key or os.environ.get("EIA_API_KEY")
    if not api_key:
        raise ValueError("Set EIA_API_KEY in the environment, or run with --skip-eia")
    init_schema()
    failures, counts = [], {}
    for market in markets or MARKET_CONFIG:
        series_id = MARKET_CONFIG[market]["eia_series"]
        if not series_id:
            continue
        try:
            records = fetch_eia_records(series_id, api_key)
            frame = parse_eia_records(records, market, series_id, calendar_path)
            write_frame("eia_inventory", frame)
            counts[market] = len(frame)
            print(f"{market}: {len(frame)} latest-vintage inventory rows; "
                  f"{frame.release_quality.eq('verified').sum()} sourced release dates")
        except Exception as error:
            failures.append(f"{market}: {type(error).__name__}")
    if failures:
        raise RuntimeError("EIA ingestion incomplete: " + "; ".join(failures))
    return counts


def ingest_all(skip_eia=False, markets=None, calendar_path=None):
    if not skip_eia and not os.environ.get("EIA_API_KEY"):
        raise ValueError("Set EIA_API_KEY, or explicitly use --skip-eia")
    result = {"prices": ingest_futures_prices(markets)}
    if not skip_eia:
        result["inventory"] = ingest_eia_inventory(markets=markets, calendar_path=calendar_path)
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-eia", action="store_true", help="Explicitly ingest prices only")
    parser.add_argument("--markets", nargs="+", choices=list(MARKET_CONFIG))
    parser.add_argument("--calendar", help="Sourced publication-calendar CSV")
    args = parser.parse_args()
    try:
        print(ingest_all(args.skip_eia, args.markets, args.calendar))
    except (ValueError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")
