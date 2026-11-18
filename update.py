#!/usr/bin/env python3
"""Keep data/<timeframe>/<SYM>_USD_<timeframe>_full.csv complete from HISTORY_START to the last closed candle."""
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
# Daily candles go back further so slow filters (e.g. a 200-day average) are warmed up by 2023.
HISTORY_START = {"1h": datetime(2023, 1, 1, tzinfo=timezone.utc), "1d": datetime(2021, 1, 1, tzinfo=timezone.utc)}
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


def parse_timestamp(text):
    return int(datetime.strptime(text, TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc).timestamp())


def format_row(ts, values):
    return [datetime.fromtimestamp(ts, timezone.utc).strftime(TIMESTAMP_FORMAT), *values]


def read_rows(path):
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.reader(f))[1:]


def fetch_range(asset, start, end, granularity):
    rows = {}
    window_start = start
    while window_start < end:
        window_end = min(window_start + MAX_CANDLES_PER_REQUEST * granularity, end)
        for ts, low, high, open_, close, volume in fetch_candles(
                f"{asset}-USD", window_start, window_end, granularity):
            if start <= ts < end:
                rows[ts] = [open_, high, low, close, volume]
        window_start = window_end
        time.sleep(0.35)
    return rows


def update_series(asset, timeframe, granularity, data_dir):
    """Prepend history back to HISTORY_START if missing, then append closed candles. Returns rows added."""
    path = data_dir / timeframe / f"{asset}_USD_{timeframe}_full.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_rows(path)
    history_start = int(HISTORY_START[timeframe].timestamp())
    # Stop before the in-progress candle so every stored row is final.
    end = int(time.time()) // granularity * granularity

    if not existing:
        older, first, last = fetch_range(asset, history_start, end, granularity), None, None
    else:
        first, last = parse_timestamp(existing[0][0]), parse_timestamp(existing[-1][0])
        older = fetch_range(asset, history_start, first, granularity) if first > history_start else {}
    newer = fetch_range(asset, last + granularity, end, granularity) if last is not None else {}

    if older or not existing:
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(HEADER)
            writer.writerows(format_row(ts, older[ts]) for ts in sorted(older))
            writer.writerows(existing)
            writer.writerows(format_row(ts, newer[ts]) for ts in sorted(newer))
    elif newer:
        with path.open("a", newline="") as f:
            csv.writer(f).writerows(format_row(ts, newer[ts]) for ts in sorted(newer))
    return len(older) + len(newer)


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
