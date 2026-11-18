# backtesting-data-flake

Hourly and daily Coinbase OHLCV candles (from 2023-01-01, or each asset's Coinbase listing if later) for
[trading-bot-flake](https://github.com/Sammyalhashe/trading-bot-flake) backtests.

```
data/1h/<SYM>_USD_1h_full.csv
data/1d/<SYM>_USD_1d_full.csv
```

Columns: `timestamp,open,high,low,close,volume` (UTC, completed candles only).

## Use from a flake

```nix
inputs.backtesting-data.url = "github:Sammyalhashe/backtesting-data-flake";
# ${backtesting-data.packages.${system}.default}/1h
```

The x86_64-linux package is built and pushed to `starllama.cachix.org` by CI.

## Updating

A weekly GitHub Action runs `update.py`, which appends only the candles that are
missing, and commits the result. To refresh by hand: `python3 update.py`.
Edit `ASSETS` in `update.py` to track a new asset; its history backfills on the next run.
