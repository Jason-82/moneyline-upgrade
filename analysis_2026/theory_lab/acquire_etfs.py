"""Read-only public ETF research acquisition; no accounts or trading.

Live sources are mutable. Exact reproduction uses the archived input bundle,
not another network download. Pass --raw-cache for saved Yahoo JSON.
"""
from __future__ import annotations
import argparse, concurrent.futures, datetime as dt, hashlib, io, json, pathlib, re, time, zipfile
import numpy as np, pandas as pd, requests
import exchange_calendars as xc
ROOT: pathlib.Path
RAW_CACHE: pathlib.Path | None = None
SYMBOLS=['SPY','QQQ','IWM','EFA','EEM','TLT','IEF','SHY','TIP','LQD','HYG','GLD','SLV','VNQ','XLB','XLE','XLF','XLI','XLK','XLP','XLU','XLV','XLY','SSO']
ASOF='2026-10-13'
def sha(p): return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def acquire(sym):
    u=f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}'
    params={'period1':631152000,'period2':int(pd.Timestamp(ASOF,tz='UTC').timestamp())+86400,'interval':'1d','events':'div,splits','includeAdjustedClose':'true'}
    path=ROOT/'raw'/f'{sym}.json'
    response = None
    if RAW_CACHE is not None:
        cached = RAW_CACHE / f"{sym}.json"
        payload = cached.read_bytes()
        raw = json.loads(payload)
    else:
        for attempt in range(4):
            try:
                response = requests.get(u, params=params, headers={"User-Agent": "MoneylineResearch/1.0 public-market-data"}, timeout=90)
                response.raise_for_status()
                payload = response.content
                raw = response.json()
                break
            except requests.RequestException:
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))
    if raw["chart"]["error"]:
        raise ValueError(raw["chart"]["error"])
    result = raw["chart"]["result"][0]
    path.write_bytes(payload)
    stamp=pd.to_datetime(result['timestamp'],unit='s',utc=True).tz_convert('America/New_York').normalize().tz_localize(None)
    quote=result['indicators']['quote'][0]
    d=pd.DataFrame({k:quote[k] for k in ['open','high','low','close','volume']},index=stamp)
    d['adj_close']=result['indicators']['adjclose'][0]['adjclose']; d.index.name='date'
    d=d.loc[d.index<=pd.Timestamp(ASOF)]
    if d.index.duplicated().any(): raise ValueError(f'{sym}: duplicate dates')
    d=d.sort_index()
    bad=d[['open','high','low','close','adj_close']].isna().any(axis=1)|(d[['open','high','low','close','adj_close']]<=0).any(axis=1)
    incomplete=d.loc[bad]
    if len(incomplete): incomplete.to_csv(ROOT/'session_gaps'/f'{sym}_invalid.csv')
    d=d.loc[~bad]
    tolerance=1e-5
    impossible=(d.high+ tolerance<d[['open','close']].max(axis=1))|(d.low-tolerance>d[['open','close']].min(axis=1))|(d.low>d.high)
    if impossible.any(): raise ValueError(f'{sym}: impossible OHLC on {d.index[impossible].tolist()}')
    split=d[['open','high','low','close','volume']]
    split.to_csv(ROOT/'split_only'/f'{sym}.csv',float_format='%.12g')
    factor=d.adj_close/d.close
    total=d[['open','high','low','close']].multiply(factor,axis=0)
    total['volume']=d.volume; total['adjustment_factor']=factor
    total.to_csv(ROOT/'total_return'/f'{sym}.csv',float_format='%.12g')
    ev=result.get('events',{})
    div=[]
    for k,v in ev.get('dividends',{}).items():
        date=pd.Timestamp(v['date'],unit='s',tz='UTC').tz_convert('America/New_York').date().isoformat()
        div.append({'date':date,'amount':v['amount']})
    pd.DataFrame(div,columns=['date','amount']).sort_values('date').to_csv(ROOT/'dividends'/f'{sym}.csv',index=False)
    cal=xc.get_calendar('XNYS',start=d.index[0]-pd.Timedelta(days=7),end=pd.Timestamp(ASOF)+pd.Timedelta(days=7))
    sessions=cal.sessions_in_range(d.index[0],d.index[-1]).tz_localize(None)
    missing=sessions.difference(d.index); unexpected=d.index.difference(sessions)
    if len(unexpected): raise ValueError(f'{sym}: non-NYSE dates {unexpected.tolist()}')
    pd.DataFrame({'date':missing}).to_csv(ROOT/'session_gaps'/f'{sym}_missing.csv',index=False)
    changes=d.adj_close.pct_change()
    jumps=d.loc[changes.abs()>.30,['close','adj_close']].copy(); jumps['total_return']=changes[changes.abs()>.30]
    if len(jumps): jumps.to_csv(ROOT/'session_gaps'/f'{sym}_jumps.csv')
    entry={'symbol':sym,'provider':'Yahoo Finance chart','requested_url':requests.Request('GET', u, params=params).prepare().url,'retrieved_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'http_status':response.status_code if response is not None else None,'source_mode':'saved_raw_cache' if RAW_CACHE is not None else 'live_download','raw_path':str(path.relative_to(ROOT)),'raw_sha256':sha(path),'raw_bytes':path.stat().st_size,'rows':len(d),'first':d.index[0].date().isoformat(),'last':d.index[-1].date().isoformat(),'invalid_rows':len(incomplete),'missing_sessions':len(missing),'missing_dates':[x.date().isoformat() for x in missing],'dividend_events':len(div),'split_events':len(ev.get('splits',{})),'large_return_days':len(jumps),'total_return_path':str((ROOT/'total_return'/f'{sym}.csv').relative_to(ROOT)),'total_return_sha256':sha(ROOT/'total_return'/f'{sym}.csv'),'split_only_sha256':sha(ROOT/'split_only'/f'{sym}.csv'),'currency':result['meta'].get('currency'),'exchange_timezone':result['meta'].get('exchangeTimezoneName')}
    print(json.dumps({k:entry[k] for k in ['symbol','rows','first','last','missing_sessions','dividend_events']}),flush=True)
    return entry
def acquire_stock_inputs():
    """Optional full mutable PIT release and official monthly factor download."""
    urls = {
        "prices.parquet": "https://github.com/Johnbrick123/sp500-data/releases/download/data/prices.parquet",
        "raw/membership_intervals.parquet": "https://github.com/Johnbrick123/sp500-data/releases/download/data/membership_intervals.parquet",
        "raw/F-F_Research_Data_Factors_CSV.zip": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip",
    }
    receipts = []
    for relative, url in urls.items():
        destination = ROOT / relative
        temporary = destination.with_suffix(destination.suffix + ".partial")
        response = requests.get(url, timeout=120, stream=True, headers={"User-Agent": "MoneylineResearch/1.0 public-market-data"})
        response.raise_for_status()
        with temporary.open("wb") as handle:
            for chunk in response.iter_content(4 * 1024 * 1024):
                handle.write(chunk)
        temporary.replace(destination)
        receipts.append({"requested_url": url, "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                         "http_status": response.status_code, "path": relative,
                         "bytes": destination.stat().st_size, "sha256": sha(destination),
                         "mutable_source": True})
    archive = ROOT / "raw/F-F_Research_Data_Factors_CSV.zip"
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.namelist()
        if members != ["F-F_Research_Data_Factors.csv"]:
            raise ValueError("Unexpected FF3 ZIP member names")
        payload = bundle.read(members[0])
    (ROOT / "raw/F-F_Research_Data_Factors.csv").write_bytes(payload)
    rows = []
    for line in payload.decode("utf-8-sig").splitlines():
        if re.match(r"^\d{6},", line):
            parts = line.split(",")
            rows.append([pd.Period(parts[0], freq="M").end_time.normalize(),
                         *[float(value) / 100 for value in parts[1:5]]])
    factors = pd.DataFrame(rows, columns=["date", "Mkt-RF", "SMB", "HML", "RF"])
    if factors.empty or factors.date.duplicated().any() or (factors.iloc[:, 1:] <= -1).any().any():
        raise ValueError("Invalid FF3 monthly factors")
    factors.to_csv(ROOT / "ff3_monthly.csv", index=False, float_format="%.12g")
    receipts.append({"path": "ff3_monthly.csv", "sha256": sha(ROOT / "ff3_monthly.csv"),
                     "rows": len(factors), "first": str(factors.date.iloc[0].date()),
                     "last": str(factors.date.iloc[-1].date()), "units": "decimal simple returns",
                     "caveat": "Revised factor history, not original publication vintages; apply declared lag."})
    (ROOT / "raw/stock_input_download_receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")


def main(argv=None):
    global ROOT, ASOF, RAW_CACHE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, required=True, help="New empty output directory")
    parser.add_argument("--asof", default="2026-10-13", help="Last complete NYSE session allowed (YYYY-MM-DD)")
    parser.add_argument("--raw-cache", type=pathlib.Path, help="Saved raw Yahoo JSON directory; no ETF network calls")
    parser.add_argument("--include-stock-inputs", action="store_true", help="Also download mutable PIT stocks/membership and FF3 factors")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    date = pd.Timestamp(args.asof)
    if date.tzinfo is not None or date != date.normalize():
        parser.error("--asof must be a plain YYYY-MM-DD date")
    if args.workers < 1:
        parser.error("--workers must be positive")
    ROOT = args.output.resolve()
    if ROOT.exists() and any(ROOT.iterdir()):
        parser.error("--output must be empty; archived/frozen input files must never be overwritten")
    ROOT.mkdir(parents=True, exist_ok=True)
    ASOF = date.date().isoformat()
    RAW_CACHE = args.raw_cache.resolve() if args.raw_cache is not None else None
    for sub in ["raw", "total_return", "split_only", "dividends", "session_gaps"]:
        (ROOT / sub).mkdir(exist_ok=True)
    result = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(acquire, symbol): symbol for symbol in SYMBOLS}
        for future in concurrent.futures.as_completed(futures):
            result.append(future.result())
    manifest = {
        "schema_version": 1, "asof": ASOF,
        "source": "Official public Yahoo Finance chart endpoint; mutable and not an execution data contract.",
        "adjustment": "Per-day adj_close / close factor applied to OHLC. Synthetic total-return units assume frictionless dividend reinvestment; split_only preserves provider split-adjusted OHLC. No fabricated or filled bars.",
        "scope": "24 surviving ETFs including actual SSO since inception. No dead-fund universe or synthetic leveraged backfill.",
        "rows": sorted(result, key=lambda item: item["symbol"]),
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    pd.DataFrame(result).drop(columns=["missing_dates"]).sort_values("symbol").to_csv(ROOT / "coverage.csv", index=False)
    if args.include_stock_inputs:
        acquire_stock_inputs()
    print("manifest_sha256", sha(ROOT / "manifest.json"), flush=True)


if __name__ == "__main__":
    main()
