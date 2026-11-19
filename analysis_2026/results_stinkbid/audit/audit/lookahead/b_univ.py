"""(b) U-Q1 membership rebuilt from the raw daily klines with independent code (prereg §5, §4.1; A1.1/A2.1 inheritance),
compared with ref/universes.parquet for every coin-month 2020-01..2026-11; 10 random (coin, month) pairs from the P1
fills' months reported in detail; a truncation test (panel cut at the last day before M) for 12 months; and every
coin-month whose U-Q1 membership depends on an inheritance link, with the link's date."""
import sys

import numpy as np
import pandas as pd

S = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/lookahead"
sys.path.insert(0, "/home/user/moneyline-upgrade")
from analysis_2026 import stinkbid_data as sbd          # registry data only (SWAPS/INHERIT/REUSE dicts)

PANEL = "data/stinkbid/d1_full_all.parquet"


def mi(m):
    return int(m[:4]) * 12 + int(m[5:7]) - 1


def ms(i):
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def load_panel(cut_day=None):
    a = pd.read_parquet(PANEL, columns=["sym", "open_time", "open", "close", "quote_volume", "trades"])
    a["day"] = a.open_time.dt.tz_convert(None).dt.normalize().astype("datetime64[ns]")
    if cut_day is not None:
        a = a[a.day <= cut_day]
    a["coin"] = a.sym.str[:-4]
    m = (a.sym == "LUNAUSDT") & (a.day >= pd.Timestamp("2022-05-31"))
    a.loc[m, "coin"] = "LUNA2"
    p = pd.read_csv("data/stinkbid/ref/spot_usdt_pairs.csv", keep_default_na=False)
    exc = set(p.base[p.excluded != ""]) | {"PAX", "USDP"}
    a = a[~a.sym.str[:-4].isin(exc)]
    a = a[a.trades > 0].sort_values(["coin", "day"]).reset_index(drop=True)
    # segment ids (causal): break after a missing day or at a >25% open jump
    same = a.coin.to_numpy()[1:] == a.coin.to_numpy()[:-1]
    gap = (a.day.to_numpy()[1:] - a.day.to_numpy()[:-1]) != np.timedelta64(1, "D")
    jump = np.abs(a.open.to_numpy()[1:] / a.close.to_numpy()[:-1] - 1) > 0.25
    new = np.r_[True, ~same | gap | jump]
    a["seg"] = np.cumsum(new)
    r = np.full(len(a), np.nan)
    r[1:] = np.where(~new[1:], np.log(a.close.to_numpy()[1:] / a.close.to_numpy()[:-1]), np.nan)
    a["ret"] = r
    return a


def month_ranks(a, months):
    """rank of every eligible coin in each month M: >= 30 traded days in the 90 days before M and traded on the last
    day before M; median USDT quote volume over the traded days; stablecoin backstop sd90 < 0.5% excluded."""
    out = []
    for M in months:
        t1 = pd.Timestamp(M + "-01") - pd.Timedelta("1D")
        lo = t1 - pd.Timedelta("89D")
        w = a[(a.day >= lo) & (a.day <= t1)]
        g = w.groupby("coin")
        n = g.size()
        last = w[w.day == t1].coin.unique()
        ok = n[(n >= 30) & n.index.isin(last)].index
        w = w[w.coin.isin(ok)]
        g = w.groupby("coin")
        adv = g.quote_volume.median()
        sd = g.ret.std(ddof=1)
        nr = g.ret.count()
        back = (nr >= 2) & (sd < 0.005)
        el = adv[~back.reindex(adv.index).fillna(False)]
        el = el.reset_index().sort_values(["quote_volume", "coin"], ascending=[False, True])
        el["rank"] = np.arange(1, len(el) + 1)
        el["month"] = M
        out.append(el[["month", "coin", "rank", "quote_volume"]])
    return pd.concat(out, ignore_index=True)


def preds_map():
    links = [(p, s, "swap") for p, (s, _, _) in sbd.SWAPS.items()] + \
            [(p, s, "inherit") for p, (s, _, _) in sbd.INHERIT.items()]
    out = {}
    for p, s, kind in links:
        out.setdefault(s, []).append(p)
    def allp(c, seen=None):
        seen = seen or set()
        res = []
        for p in out.get(c, []):
            if p not in seen:
                seen.add(p); res.append(p); res += allp(p, seen)
        return res
    return {c: allp(c) for c in set(out)}


def first_listing(a_full):
    q = pd.read_csv("data/stinkbid/ref/ages_quotes.csv", keep_default_na=False)
    q = q[q.first_month != ""]
    first = q.groupby("base").first_month.min().to_dict()
    # SKY: Binance's 2018-05..2021-11 SKY pairs were Skycoin (REUSE_LISTING); the Sky token starts 2025-09
    sky = sorted(m for x in q.months[q.base == "SKY"] for m in x.split() if m >= "2025-09")
    first["SKY"] = sky[0]
    own = a_full.groupby("coin").day.min().dt.strftime("%Y-%m").to_dict()
    for c, m in own.items():
        if c not in first or m < first[c]:
            first[c] = m
    first["LUNA2"] = "2022-05"
    return first


def build(a, months_all, months_out, first, pm, use_inherit=True):
    rk = month_ranks(a, months_all)
    piv = rk.pivot(index="month", columns="coin", values="rank").reindex(months_all)
    hist = piv.copy()
    if use_inherit:
        for c in hist.columns:
            ps = [p for p in pm.get(c, []) if p in piv.columns]
            if ps:
                hist[c] = hist[c].where(hist[c].notna(), piv[ps].min(axis=1))
    med = hist.fillna(999.0).rolling(12, min_periods=12).median()
    r = rk[rk.month.isin(months_out)].copy()
    r["med12"] = [med.at[m, c] for m, c in zip(r.month, r.coin)]

    def fl(c):
        f = first.get(c)
        if use_inherit:
            for p in pm.get(c, []):
                if p in first and (f is None or first[p] < f):
                    f = first[p]
        return f
    r["first"] = r.coin.map(fl)
    r["age"] = [mi(m) - mi(f) if isinstance(f, str) else -1 for m, f in zip(r.month, r["first"])]
    r["UB"] = r["rank"] <= 100
    r["Q1"] = r.UB & (r.age >= 24) & (r.med12 <= 50)
    return r


def main():
    a = load_panel()
    first = first_listing(a)
    pm = preds_map()
    months_all = [ms(i) for i in range(mi("2018-08"), mi("2026-11") + 1)]
    months_out = [ms(i) for i in range(mi("2020-01"), mi("2026-11") + 1)]
    mine = build(a, months_all, months_out, first, pm)
    u = pd.read_parquet("data/stinkbid/ref/universes.parquet")
    cmp_ = u.merge(mine, on=["month", "coin"], how="outer", suffixes=("_s", "_m"), indicator=True)
    print("rows only in stored:", (cmp_._merge == "left_only").sum(), "only mine:", (cmp_._merge == "right_only").sum())
    both = cmp_[cmp_._merge == "both"]
    print("rank equal:", (both["rank_s"] == both["rank_m"]).mean(), "| med12 equal:",
          (both.rank_med12 == both.med12).mean(), "| age equal:", (both.listing_age_months == both.age).mean())
    print("U_B equal:", (both.U_B == both.UB).mean(), "| U_Q1 equal:", (both.U_Q1 == both.Q1).mean())
    d = both[(both.U_Q1 != both.Q1) | (both.U_B != both.UB)]
    print("membership mismatches:", len(d))
    if len(d):
        print(d[["month", "coin", "rank_s", "rank_m", "rank_med12", "med12", "listing_age_months", "age", "U_B", "UB",
                 "U_Q1", "Q1"]].head(40).to_string())
    print("stored U_Q1 coin-months:", int(u.U_Q1.sum()), "mine:", int(mine.Q1.sum()))
    # 10 random (coin, month) pairs from the P1 fills' months
    f = pd.read_parquet("data/stinkbid/runs/outcomes/P1__U_Q1/fills.parquet", columns=["coin", "month", "t_F1"])
    f = f[f.t_F1 >= 0]
    f["mon"] = [str(np.datetime64(int(x), "M")) for x in f.month]
    pairs = f[["coin", "mon"]].drop_duplicates().sort_values(["mon", "coin"]).reset_index(drop=True)
    pk = pairs.iloc[np.sort(np.random.default_rng(11).choice(len(pairs), 10, replace=False))]
    det = pk.merge(both, left_on=["coin", "mon"], right_on=["coin", "month"], how="left")
    pd.set_option("display.width", 250)
    print(f"\n10 random fill (coin, month) pairs out of {len(pairs)}:")
    print(det[["coin", "month", "rank_s", "rank_m", "quote_volume", "adv90", "rank_med12", "med12",
               "listing_age_months", "age", "first", "U_Q1", "Q1"]].to_string())
    # every fill month is a U_Q1 month (stored and mine)
    fm = pairs.merge(mine[["coin", "month", "Q1"]], left_on=["coin", "mon"], right_on=["coin", "month"], how="left")
    print("fill (coin, month) pairs:", len(fm), "in my U_Q1:", int(fm.Q1.fillna(False).sum()))
    # membership that depends on inheritance
    noinh = build(a, months_all, months_out, first, pm, use_inherit=False)
    x = mine.merge(noinh[["month", "coin", "Q1", "age", "med12"]], on=["month", "coin"], suffixes=("", "_noinh"))
    dep = x[x.Q1 & ~x.Q1_noinh]
    print("\nU_Q1 coin-months that need an inheritance link:", len(dep))
    print(dep.groupby("coin").agg(first=("month", "min"), last=("month", "max"), n=("month", "size"),
                                  age=("age", "min"), age_noinh=("age_noinh", "min"),
                                  med=("med12", "max"), med_noinh=("med12_noinh", "max")).to_string())
    links = {s: [] for s in dep.coin.unique()}
    for p, (s, uu, src) in list(sbd.SWAPS.items()) + list(sbd.INHERIT.items()):
        if s in links:
            sp = sbd.segments(p) if p in a.coin.unique() else None
            last = str(sp.last_day.max().date()) if sp is not None and len(sp) else "?"
            links[s].append((p, last))
    for s, v in links.items():
        print(f"  {s}: predecessors and their last USDT day {v}")
    dep.to_csv(f"{S}/b_inherit_dependent.csv", index=False)
    mine.to_csv(f"{S}/b_mine.csv", index=False)


if __name__ == "__main__":
    main()
