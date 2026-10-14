# Exact theory-lab data reproduction

This branch contains code and aggregate research outputs. Raw market data and full simulated ledgers are kept in the private reproducibility bundle; no brokerage/account information was accessed. **Use the exact archived inputs for reproduction. Downloading the same live URLs again is a new data snapshot, not reproduction:** the GitHub release tag is overwritten nightly and Yahoo/dividend-adjusted histories can be restated.

## Restore the frozen bundle

The current working archive is `/workspace/scratch/a77ef2628c77/theory_lab_inputs.zip`. Its input-only checkpoint was SHA256 `d83b67fab8aca9451a82cfe8d17250e5266e9f9c24411db6efc7de79e392e7f5`; after appending the frozen full run outputs, it is 222,687,475 bytes with SHA256 `6a42a26b25d4b7568f7d7bf51d8caf6715c4ecda2bf471fa6cc0d0ba97ac6efe`. Subsequent archive metadata additions require a newly recorded archive hash; the per-file hashes below remain the input contract.

Extract next to the repository so the resulting layout is `moneyline-upgrade/`, `theory_data/`, `theory_crypto_data/`, `crypto_base/`, and `private/`. The local checkout used here is named `moneyline-theory`; the repository name is immaterial. ZIP members preserve these relative paths:

- `theory_data/`: all 24 ETFs' untouched Yahoo JSON, total-return and split-only normalized CSVs, dividends, exact session audits, full stock `prices.parquet`, PIT membership, and official FF3 raw/normalized factors.
- `theory_crypto_data/`: exact BTC/ETH combined histories, the extension monthly ZIPs/checksum sidecars, manifests and independent audit.
- `crypto_base/`: BTC/ETH original prefix prices and their raw source files, plus the exact original metadata. Other coins referenced by the original metadata are intentionally omitted; they were not used by this study.
- `private/theory_lab/`: full C3–C5 daily paths, transactions, events and schedules.
- `theory_data/stock_results/`: C1–C2 full stock selections, paths, unknown events and run receipt.
- `private/theory_lab_attempt1/`: retained first attempt, not the final result.

`INPUT_ARCHIVE_INDEX.json` contains every input's path, byte size and SHA256. `PRIVATE_RUN_OUTPUT_INDEX.json` contains the appended output inventory. Inspect or extract without any network calls:

```bash
python3 -m zipfile -l theory_lab_inputs.zip
python3 -m zipfile -t theory_lab_inputs.zip
python3 -m zipfile -e theory_lab_inputs.zip restored
```

Do not substitute current prices into the old frozen result tables. Check out the published theory-lab commit and verify both price hashes and implementation hashes in `analysis_2026/results_theory_lab/frozen_inputs.json` and `stock_receipt.json`.

The complete public monthly export is packaged as ordered gzip parts under
`monthly_paths_parts/` to avoid a large text transport. `public_export_packaging.json` records both aggregate hashes and every part;
decompression matches the original run receipt exactly. Restore it with
`python3 -m analysis_2026.theory_lab.restore_exports` from the repository root.
The plot helper reads the parts directly. Runners still emit ordinary CSVs.
The same command restores packaged `stock_monthly_primary.csv` and
`stock_calendar_years.csv`; their decompressed hashes match the stock publication receipt.

## Run from the restored inputs

From the repository root, install `requirements-theory.txt` (NumPy 2.3.5, pandas 2.2.3 and pyarrow 26.0.0 are pinned to the numerical environment used). The original full-ledger destinations were `../private/theory_lab` and `../theory_data/stock_results`. For a rerun, use fresh output directories to retain the archived evidence:

```bash
python3 -m pip install -r requirements-theory.txt
python3 -m analysis_2026.theory_lab.run \
  --etf-folder ../theory_data/total_return \
  --crypto-folder ../theory_crypto_data/prices \
  --output ../private/theory_lab_reproduced/public_outputs \
  --private-output ../private/theory_lab_reproduced
python3 -m analysis_2026.theory_lab.stocks \
  --data ../theory_data \
  --output ../theory_data/stock_results_reproduced \
  --cutoff 2026-09-30
```

The runners regenerate raw study outputs. Regenerate the audited public stock subset and derived plot with the portable helpers:

```bash
python3 -m analysis_2026.theory_lab.publish_stocks \
  --source ../theory_data/stock_results_reproduced \
  --output ../private/theory_lab_reproduced/public_outputs
python3 -m analysis_2026.theory_lab.report \
  --output ../private/theory_lab_reproduced/public_outputs
python3 -m analysis_2026.theory_lab.plot \
  --output ../private/theory_lab_reproduced/public_outputs
```

`stock_public_receipt.json` records the stock publication filter: primary monthly rows retain one-session delay, approximately 3 bp cost, zero levy/cash yield, both missing-price policies and the status column; public unknown events are deduplicated across cost/levy stress cases. Partial unidentified paths remain diagnostics and cannot establish the stock hypotheses. Public `stock_signal_price_coverage.csv` and `stock_signal_coverage_yearly.csv` are supplementary monthly formation coverage counts, distinct from the 37-month eligibility fraction.

## Optional new acquisitions

Both scripts are read-only public-market-data clients and refuse a nonempty output directory. They do not authenticate to or place orders with any broker. These commands create **new snapshots**:

```bash
python3 -m analysis_2026.theory_lab.acquire_etfs \
  --output ../new_theory_data --asof 2026-10-13 --include-stock-inputs
python3 -m analysis_2026.theory_lab.acquire_crypto \
  --base-folder ../crypto_base --output ../new_theory_crypto_data \
  --asof 2026-10-13
```

The ETF script includes actual SSO from fund inception and performs full NYSE-session coverage checks. It stores unmodified responses, dividends, adjustment factors, invalid-bar quarantine and missing-session lists. Total-return OHLC uses daily `adj_close / close` scaling: synthetic reinvestment units, not executable tape prices or tax-lot bases. The named ETF universe contains surviving funds and no dead-fund selection history. There is no synthetic pre-inception leveraged backfill.

The crypto script checks normalized-prefix hashes against the supplied original manifest, validates its daily calendar, redownloads its final month for exact overlap reconciliation, verifies official archive checksums and rejects a missing requested daily candle. It reuses repo-relative `scripts/acquire_crypto_data.py` when that helper exists; this branch otherwise uses a standalone equivalent parser, since the earlier crypto helper belongs to a separate unmerged branch. `--raw-cache ../theory_crypto_data/raw` regenerates the extension from saved archive bytes without network calls. Monthly-only acquisition deliberately stops at 2026-09-30 for the default 2026-10-13 upper bound.

For offline ETF re-normalization use `--raw-cache ../theory_data/raw` with a fresh output directory and omit `--include-stock-inputs`; all 24 raw JSON responses must be present. New manifest timestamps/metadata differ; price-file hashes can be checked against the inventory.

Live sources:

- Yahoo daily chart: `https://query1.finance.yahoo.com/v8/finance/chart/{symbol}` with daily OHLC, dividend/split events and adjusted close.
- Mutable stock prices: `https://github.com/Johnbrick123/sp500-data/releases/download/data/prices.parquet`.
- Mutable PIT membership: `https://github.com/Johnbrick123/sp500-data/releases/download/data/membership_intervals.parquet`; spans are `[start, end)`.
- Official FF3: `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip`.
- Official crypto archives: `https://data.binance.vision/data/spot/monthly/klines/{symbol}/1d/{symbol}-1d-{YYYY-MM}.zip` and `.CHECKSUM`.

## Input fingerprints

Full source/manifest receipts:

| File | SHA256 |
|---|---|
| `theory_data/prices.parquet` | `424aaeb70549e32e03511863fbb483bd754e65502693c6e27d38516a0813dff2` |
| `theory_data/manifest.json` | `ce8aecc03e82127b61947c8a61b6793fefd15023ec13de6cb37f424211a58e3a` |
| `theory_data/SSO_receipt.json` | `e5e0be9f9456363dabe2c7d4e4f2622fad39c64407e985bd0b1abb5bf7d212c0` |
| `theory_data/raw/membership_intervals.parquet` | `8550ccbde3ae82b7a3f07057d6dd30078ccccf103dc7343fa1fd8187e7c90838` |
| `theory_data/raw/membership_intervals_receipt.json` | `ec646e9525af3f71446b45f13987903b9e94042cb138686eb2c9606b4fe97bcd` |
| `theory_data/raw/F-F_Research_Data_Factors_CSV.zip` | `593f4fbef03181bc0b22ff6292f217689dd1fb79355049ca905d95b262040a66` |
| `theory_data/raw/F-F_Research_Data_Factors.csv` | `d7d7fe37b150b5b15c9c069b3ba101dfe1af568c6d7b5db6e73cd0a6c0c9e5e5` |
| `theory_data/ff3_monthly.csv` | `301c912d1df4227e769edfb2e7c10e7510906067e56ce8d95b32db110f0c2308` |
| `theory_data/raw/ff3_receipt.json` | `f4ffa4db7169adcc7f90cbbb4afea95a7c9da9c8d3177c01fcba3944101acb53` |
| `theory_crypto_data/manifest.json` | `4f249ff0f01d3ebb630c38f1daaa22e76187d70ae5e69c6127b3c9697b5ee311` |
| `theory_crypto_data/extension_source_receipts.json` | `1e574d744d55d704006d55cef854a70c54004ef7377bb54ea4afaeedcad42255` |
| `theory_crypto_data/prices/BTCUSDT.csv` | `1d0e41ffd5d7dee267b02340ddb122e607ca9854756410c77e2c3376bfea2019` |
| `theory_crypto_data/prices/ETHUSDT.csv` | `ef90d76d5ab592b40af8b94731300bb1983b9aad54522656ceb0ea44813f938e` |
| `theory_crypto_data/independent_data_audit.json` | `2598f3da3ca7c95083d9a38c1f957cda12a064670bf4cf4b64f659c31f8010b5` |

The 23-ETF original manifest and separate SSO receipt record all raw and normalized hashes for the 24 acquired funds. Exact C3–C5 normalized input hashes are also frozen publicly:

| Input file | SHA256 |
|---|---|
| `EEM.csv` | `36b270506a0705afe0d9916dbf7439b2581d5a4b88ddf02191a925ed0cbb7f06` |
| `EFA.csv` | `67ab1eee9c4c75c0c32ebff0c788e1144157c50c42214de9a244d5142e50e2c0` |
| `GLD.csv` | `79e08952a7d2f576cb3797c153f3069768d90065ee24cb3070054edc6d6e0fef` |
| `IEF.csv` | `1a0c997c3834ed7d6ab8e6c5585708ddafc91d920a66ff48a946ff7df5f566ec` |
| `IWM.csv` | `242f70cfe2ee6da6fa1a4d50701f25d491f8f38d9028cc7ab31891bb5668b8d9` |
| `SPY.csv` | `313381b08e80fb1f70254b14ac232253111b7f9b2c5a836e373bf160c3beb695` |
| `SSO.csv` | `07bb3e50bf65330b354cfaed6ee17806fb1f3d95902cdb6f284393925b641c82` |
| `TLT.csv` | `3ba0e6bf8ce6050486fa86b4aed75b0debff10ba71c27f4a9b5de2828bc2f580` |
| `VNQ.csv` | `53a888a3df606f7938a76e6a1e5122ddd15ae3bba369742a104c791b628fedcf` |
| `BTCUSDT.csv` | `1d0e41ffd5d7dee267b02340ddb122e607ca9854756410c77e2c3376bfea2019` |
| `ETHUSDT.csv` | `ef90d76d5ab592b40af8b94731300bb1983b9aad54522656ceb0ea44813f938e` |

The original crypto-prefix manifest SHA256 is `2755f7aa66b98b0a07950988fb17715c1e449b52caa2dad4d48bb9981d4ca010`; its source-receipts SHA256 is `3c024e13506b26412d6f61a1a0ba6bf6e0a664b0d564ee994998874580050ef9`. The base BTC/ETH normalized hashes are recorded separately in the extension manifest.

## Data interpretation limits

All 24 ETFs have no invalid OHLC or missing NYSE sessions between their observed inception and 2026-10-13; histories before inception are unavailable. Both direct Yahoo and Johnbrick ETF data ultimately use Yahoo, so agreement checks confirm normalization, not independent vendor accuracy. The mutable stock snapshot mixes Yahoo, Tiingo, WIKI, archives and close-only CRSP. Available month-end closes do not guarantee an executable next-session open. Hand-verified `crsp-patch` records may retain another provider's real open; categorical exclusion of every patched row would discard actual bars. No open is invented where absent. An acquired or delisted company's missing terminal price is not evidence of a zero economic payoff; cash acquisitions, stock exchanges and bankruptcy outcomes require reconciliation. Strict unknown results remain unknown.

FF3 ends August 2026, uses revised historical factors and is lagged by the study; it does not supply contemporaneous original factor vintages. BTC/ETH are a fixed major-coin diagnostic set priced in USDT, not a representative all-coin portfolio. USDT/USD conversion risk, venue-to-broker execution differences, distributions and actual taxes are not inferred from this data.
