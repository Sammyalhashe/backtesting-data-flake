#!/usr/bin/env python3
"""Append completed Coinbase candles to data/<timeframe>/<SYM>_USD_<timeframe>_full.csv."""
import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ASSETS = [
    "AAVE", "AVAX", "BTC", "ETH", "FET", "HBAR", "INJ", "LINK", "LTC", "NEAR",
    "ONDO", "POL", "RENDER", "SOL", "SUI", "TAO", "TIA", "UNI", "VVV", "XRP",
]
TIMEFRAMES = {"1h": 3600, "1d": 86400}
HISTORY_START = datetime(2025, 2, 1, tzinfo=timezone.utc)
MAX_CANDLES_PER_REQUEST = 300
HEADER = ["timestamp", "open", "high", "low", "close", "volume"]
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def fetch_candles(product_id, start_ts, end_ts, granularity):
    url = (f"https://api.exchange.coinbase.com/products/{product_id}/candles"
           f"?granularity={granularity}"
           f"&start={datetime.fromtimestamp(start_ts, timezone.utc).isoformat()}"
           f"&end={datetime.fromtimestamp(end_ts, timezone.utc).isoformat()}")
    request = urllib.request.Request(url, headers={"User-Agent": "backtesting-data-flake"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise
        except urllib.error.URLError:
            pass
        time.sleep(2 ** attempt)
    raise RuntimeError(f"giving up on {product_id} {start_ts}-{end_ts}")


def last_timestamp(path):
    if not path.exists():
        return None
    with path.open() as f:
        rows = list(csv.reader(f))
    if len(rows) < 2:
        return None
    parsed = datetime.strptime(rows[-1][0], TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def update_series(asset, timeframe, granularity, data_dir):
    path = data_dir / timeframe / f"{asset}_USD_{timeframe}_full.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    last = last_timestamp(path)
    start = last + granularity if last is not None else int(HISTORY_START.timestamp())
    # Stop before the in-progress candle so every stored row is final.
    end = int(time.time()) // granularity * granularity

    new_rows = {}
    window_start = start
    while window_start < end:
        window_end = min(window_start + MAX_CANDLES_PER_REQUEST * granularity, end)
        for ts, low, high, open_, close, volume in fetch_candles(
                f"{asset}-USD", window_start, window_end, granularity):
            if start <= ts < end:
                new_rows[ts] = [open_, high, low, close, volume]
        window_start = window_end
        time.sleep(0.35)

    if not new_rows:
        return 0
    write_header = last is None
    with path.open("a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(HEADER)
        for ts in sorted(new_rows):
            stamp = datetime.fromtimestamp(ts, timezone.utc).strftime(TIMESTAMP_FORMAT)
            writer.writerow([stamp, *new_rows[ts]])
    return len(new_rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent / "data")
    parser.add_argument("--assets", nargs="+", default=ASSETS)
    parser.add_argument("--timeframes", nargs="+", default=list(TIMEFRAMES), choices=list(TIMEFRAMES))
    args = parser.parse_args()

    for timeframe in args.timeframes:
        for asset in args.assets:
            added = update_series(asset, timeframe, TIMEFRAMES[timeframe], args.data_dir)
            print(f"{asset} {timeframe}: +{added} candles")


if __name__ == "__main__":
    main()
