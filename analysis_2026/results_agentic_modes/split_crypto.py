"""immediate vs split vs confirm5 on the broad crypto evidence: 21 coins per asset and the top-20 basket incl. dead coins."""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
import numpy as np, pandas as pd
from analysis_2026.flip_delay import LARGE20, load_crypto_daily, moneyline_delay, stats
from analysis_2026.larsson import basket, rf_daily, sharpe, boot_sharpe_gain, summarise
from analysis_2026.altcoins import load_crypto, tiers_for_year
from agentic.backtest import weights_returns

MODES = {'immediate': lambda g1, g5: g1.astype(float), 'split': lambda g1, g5: 0.5 * g1 + 0.5 * g5,
         'confirm5': lambda g1, g5: g5.astype(float)}

def mode_returns(d, cost):
    g1, g5 = moneyline_delay(d, 1), moneyline_delay(d, 5)
    return {m: weights_returns(d, f(g1, g5), cost)[0] for m, f in MODES.items()}

pd.set_option('display.width', 220)
out = []
# ---- per asset, 21 coins
for cost in (0.0015, 0.0095):
    rows = []
    for s in LARGE20 + ['ZEC']:
        d = load_crypto_daily(s)
        rr = mode_returns(d, cost)
        for wu in (120, 200):
            st = max(pd.Timestamp('2018-01-01'), d.index[min(len(d) - 1, wu)])
            rf = rf_daily(d.index)
            bh = d.close.pct_change().fillna(0).loc[st:'2026-09-30']
            rows.append({'asset': s, 'warmup': wu, 'mode': 'BUY & HOLD', **summarise(bh, 365, rf, hold=True)})
            for m, r in rr.items():
                rows.append({'asset': s, 'warmup': wu, 'mode': m, **summarise(r.loc[st:'2026-09-30'], 365, rf)})
    P = pd.DataFrame(rows); P['cost'] = cost; out.append(P)
    for wu in (120, 200):
        Q = P[P.warmup == wu]
        print(f'\n===== 21 coins, cost {cost:.2%}/side, warm-up {wu}: medians')
        print(Q.groupby('mode')[['CAGR_%', 'CAGR_tax_%', 'Sharpe_xs', 'maxDD_%']].median().round(2).to_string())
        pv = {k: Q.pivot_table(index='asset', columns='mode', values=k) for k in ('CAGR_tax_%', 'Sharpe_xs', 'maxDD_%')}
        for a, b in [('split', 'immediate'), ('split', 'confirm5'), ('confirm5', 'immediate')]:
            print(f'  {a} vs {b}: after-tax better on {int((pv["CAGR_tax_%"][a] > pv["CAGR_tax_%"][b]).sum())}/21, '
                  f'median diff {(pv["CAGR_tax_%"][a] - pv["CAGR_tax_%"][b]).median():+.2f}; Sharpe better on '
                  f'{int((pv["Sharpe_xs"][a] > pv["Sharpe_xs"][b]).sum())}/21; shallower maxDD on '
                  f'{int((pv["maxDD_%"][a] > pv["maxDD_%"][b]).sum())}/21 (median {(pv["maxDD_%"][a] - pv["maxDD_%"][b]).median():+.1f} pts)')
pd.concat(out).to_csv(str(__import__('pathlib').Path(__file__).resolve().parent / 'split_crypto_per_asset.csv'), index=False)

# ---- top-20 basket incl. dead coins, 2019-2026 (as the Larsson / flip-delay studies)
cd = load_crypto()
yrs = list(range(2019, 2027)); cby = {}
for y in yrs:
    t = tiers_for_year(cd, y); cby[y] = t['1-10'] + t['11-30'][:10]
for cost_name, cost_fn in [('study', lambda s: 0.0010 if s.split('#')[0] in ('BTC', 'ETH') else 0.0015), ('0.95%', lambda s: 0.0095)]:
    mats = {m: {} for m in MODES}; mats['BH'] = {}
    cache = {}
    for y in yrs:
        cols = {m: {} for m in mats}
        for s in cby[y]:
            if s not in cd:
                continue
            d = cd[s][['open', 'high', 'low', 'close']]
            if s not in cache:
                cache[s] = mode_returns(d, cost_fn(s))
                cache[s]['BH'] = d.close.pct_change().fillna(0.0)
            for m in mats:
                x = cache[s][m].loc[f'{y}-01-01':f'{y}-12-31']
                if len(x) > 20:
                    cols[m][s] = x
        for m in mats:
            if cols[m]:
                mats[m][y] = pd.concat(cols[m], axis=1, sort=True)
    for how in ('daily', 'held'):
        B = {m: basket(mats[m], how).loc[:'2026-09-30'] for m in mats}
        rf = rf_daily(B['BH'].index)
        print(f'\n===== crypto top-20 basket incl. dead coins 2019-2026, {how}, costs {cost_name}')
        tab = pd.DataFrame({m: summarise(r, 365, rf, hold=(m == 'BH')) for m, r in B.items()}).T
        print(tab[['CAGR_%', 'CAGR_tax_%', 'Sharpe_xs', 'maxDD_%']].round(2).to_string())
        for a, b, seed in [('split', 'immediate', 11), ('split', 'confirm5', 12), ('confirm5', 'immediate', 13)]:
            t = boot_sharpe_gain(B[a], B[b], rf, 365, 180, seed=seed)
            print(f'  {a} vs {b}: dSharpe {t["dSharpe"]:+.3f}, one-sided p {t["p_one_sided"]:.3f}, halves {t["half1"]:+.3f}/{t["half2"]:+.3f}')
