import pandas as pd, numpy as np
import os; S=os.path.dirname(os.path.abspath(__file__))+'/'
m=pd.read_csv(S+'monthly_prices.csv',index_col=0); m.index=pd.PeriodIndex(m.index,freq='M')
m=m.loc[:'2026-09']
def r(col,a,b):
    a=pd.Period(a,'M'); b=pd.Period(b,'M')
    s=m[col].dropna()
    if a not in s.index or b not in s.index: return np.nan
    return s[b]/s[a]-1
def fmt(x): return 'n/a' if pd.isna(x) else f'{x*100:+.0f}%'
def ep(name,c,bms,t0,pre=None):
    t0p=pd.Period(t0,'M'); last=pd.Period('2026-09','M')
    rows=[]
    hs=[('pre',pre)] if pre else []
    hs+= [(f'{h}y',str(t0p+12*h)) for h in (1,3,5,10)]+[('to2026-09','2026-09')]
    out=[name, c, 't0='+t0]
    for lab,x in hs:
        if lab=='pre': a,b=x,t0
        else:
            if pd.Period(x,'M')>last: out.append(f'{lab}: n/a'); continue
            a,b=t0,x
        cr=r(c,a,b); bs=[r(bm,a,b) for bm in bms]
        rel=' / '.join(f'{bm.split("_")[1]} {fmt(v)} (rel {fmt((1+cr)/(1+v)-1)})' for bm,v in zip(bms,bs))
        out.append(f'{lab} [{a}->{b}]: {fmt(cr)} vs {rel}')
    print('\n  '.join(out)); print()
RH=['RH_EEM','RH_ACWI']; TR=['TR_EEM','TR_EFA','TR_SPY']
ep('ARG Macri win','RH_ARGT',RH,'2015-11',pre='2015-07')
ep('ARG Macri peak->2019','RH_ARGT',RH,'2018-01',pre='2015-11')
ep('ARG Milei win','RH_ARGT',RH,'2023-11',pre='2023-07')
ep('ARG Milei longer pre','RH_ARGT',RH,'2023-11',pre='2022-11')
ep('ARG midterm','RH_ARGT',RH,'2025-10',pre='2025-09')
ep('IND Modi','RH_INDA',RH,'2014-05',pre='2013-08')
ep('CHN crackdown MCHI','RH_MCHI',RH,'2020-10',pre='2019-10')
ep('CHN crackdown KWEB','RH_KWEB',RH,'2020-10',pre='2019-10')
ep('CHN crackdown FXI','RH_FXI',RH,'2020-10',pre='2019-10')
ep('TUR 2018','RH_TUR',RH,'2017-12',pre='2016-12')
ep('TUR orthodox pivot','RH_TUR',RH,'2023-05',pre='2022-05')
ep('GRC 3rd bailout','RH_GREK',RH,'2015-07',pre='2014-12')
ep('GRC Mitsotakis','RH_GREK',RH,'2019-07',pre='2019-04')
ep('VNM Res68','RH_VNM',RH,'2025-04',pre='2024-04')
ep('KSA Vision2030','RH_KSA',RH,'2016-04',pre='2015-10')
ep('IDN Jokowi','RH_EIDO',RH,'2014-07',pre='2013-08')
ep('BRA Temer','TR_EWZ',TR,'2016-05',pre='2016-01')
ep('BRA Temer RH-compare','TR_EWZ',['RH_EEM','RH_ACWI'],'2016-05',pre='2016-01')
ep('BRA Bolsonaro','TR_EWZ',TR,'2018-10',pre='2018-05')
ep('JPN Abenomics','TR_EWJ',TR,'2012-11',pre='2012-05')
ep('JPN StewardshipCode','TR_EWJ',TR,'2014-02',pre='2013-02')
ep('JPN CGcode','TR_EWJ',TR,'2015-06',pre='2014-06')
ep('JPN TSE PB request','TR_EWJ',TR,'2023-03',pre='2022-03')
ep('US TCJA signed','TR_SPY',['TR_EFA','TR_EEM'],'2017-12',pre='2016-10')
ep('ZAF Zuma','RH_EZA',RH,'2009-05',pre='2008-05')
ep('ZAF Zuma era (EEM only)','RH_EZA',['RH_EEM'],'2009-04',pre='2007-12')
ep('ZAF Ramaphosa','RH_EZA',RH,'2017-12',pre='2017-11')
ep('ZAF GNU','RH_EZA',RH,'2024-05',pre='2024-04')
ep('MEX AMLO','RH_EWW',RH,'2018-07',pre='2018-06')
ep('CHL protests','RH_ECH',RH,'2019-10',pre='2019-09')
ep('CHL Kast','RH_ECH',RH,'2025-12',pre='2025-06')
print('Zuma full tenure EZA vs EEM 2009-05->2018-02:', fmt(r('RH_EZA','2009-05','2018-02')), fmt(r('RH_EEM','2009-05','2018-02')))
print('Turkey 2017-12->2023-05:', fmt(r('RH_TUR','2017-12','2023-05')), 'EEM', fmt(r('RH_EEM','2017-12','2023-05')), 'ACWI', fmt(r('RH_ACWI','2017-12','2023-05')))
print('Turkey 2013-05->2023-05:', fmt(r('RH_TUR','2013-05','2023-05')), 'EEM', fmt(r('RH_EEM','2013-05','2023-05')))
print('China MCHI 2021-01->2022-10:', fmt(r('RH_MCHI','2021-01','2022-10')), 'KWEB',fmt(r('RH_KWEB','2021-01','2022-10')),'EEM', fmt(r('RH_EEM','2021-01','2022-10')),'ACWI', fmt(r('RH_ACWI','2021-01','2022-10')))
print('China KWEB 2021-01->2026-09:', fmt(r('RH_KWEB','2021-01','2026-09')), 'MCHI', fmt(r('RH_MCHI','2021-01','2026-09')), 'EEM', fmt(r('RH_EEM','2021-01','2026-09')))
print('ARGT 2015-11->2019-08', fmt(r('RH_ARGT','2015-11','2019-08')), 'EEM', fmt(r('RH_EEM','2015-11','2019-08')))
print('ARGT 2015-11->2018-01', fmt(r('RH_ARGT','2015-11','2018-01')))
print('ARGT 2018-01->2019-08', fmt(r('RH_ARGT','2018-01','2019-08')))
print('ARGT 2019-07->2019-08', fmt(r('RH_ARGT','2019-07','2019-08')))
print('ARGT 2023-07->2025-01', fmt(r('RH_ARGT','2023-07','2025-01')))
print('ARGT 2025-01->2026-09', fmt(r('RH_ARGT','2025-01','2026-09')), 'EEM', fmt(r('RH_EEM','2025-01','2026-09')))
print('ARGT 2025-12->2026-09', fmt(r('RH_ARGT','2025-12','2026-09')), 'EEM', fmt(r('RH_EEM','2025-12','2026-09')))
print('VNM 2025-04->2025-10', fmt(r('RH_VNM','2025-04','2025-10')),'EEM',fmt(r('RH_EEM','2025-04','2025-10')))
print('VNM 2025-12->2026-09', fmt(r('RH_VNM','2025-12','2026-09')),'EEM',fmt(r('RH_EEM','2025-12','2026-09')))
print('EWJ 2012-11->2026-09', fmt(r('TR_EWJ','2012-11','2026-09')),'EFA',fmt(r('TR_EFA','2012-11','2026-09')),'SPY',fmt(r('TR_SPY','2012-11','2026-09')))
print('EWJ 2014-02->2026-09', fmt(r('TR_EWJ','2014-02','2026-09')),'EFA',fmt(r('TR_EFA','2014-02','2026-09')),'SPY',fmt(r('TR_SPY','2014-02','2026-09')),'EEM',fmt(r('TR_EEM','2014-02','2026-09')))
print('EWJ 2025-12->2026-09', fmt(r('TR_EWJ','2025-12','2026-09')),'EFA',fmt(r('TR_EFA','2025-12','2026-09')),'SPY',fmt(r('TR_SPY','2025-12','2026-09')))
print('KSA 2016-04->2026-09', fmt(r('RH_KSA','2016-04','2026-09')))
print('GREK 2015-07->2026-09', fmt(r('RH_GREK','2015-07','2026-09')),'EEM',fmt(r('RH_EEM','2015-07','2026-09')),'ACWI',fmt(r('RH_ACWI','2015-07','2026-09')))
print('GREK 2011-12->2015-07', fmt(r('RH_GREK','2011-12','2015-07')))
print('TUR 2023-05->2026-09',fmt(r('RH_TUR','2023-05','2026-09')))
print('INDA 2014-05->2024-05',fmt(r('RH_INDA','2014-05','2024-05')), 'EEM', fmt(r('RH_EEM','2014-05','2024-05')))

# ---- Additional calculations cited in reform_case_studies.md ----
print('\n--- extra ---')
X=pd.read_csv(S+'monthly_prices.csv',index_col=0)
RR=lambda c,a,b: X.loc[b,c]/X.loc[a,c]-1
for lab,c,a,b in [('ARGT late-Kirchner','RH_ARGT','2012-06','2015-10'),('EEM same','RH_EEM','2012-06','2015-10'),
                  ('ARGT Fernandez era','RH_ARGT','2019-08','2023-07'),('TUR 2023','RH_TUR','2022-12','2023-12'),
                  ('TUR rate cuts','RH_TUR','2021-08','2021-12'),('EWZ Lula fear','TR_EWZ','2002-04','2002-09'),
                  ('EWZ post-fear','TR_EWZ','2002-09','2003-12'),('EWW Sheinbaum','RH_EWW','2024-05','2024-06'),
                  ('EPU Castillo','RH_EPU','2021-03','2021-07'),('EIDO 2025-26','RH_EIDO','2025-08','2026-09'),
                  ('EWJ unhedged 2020-12..2024-06','TR_EWJ','2020-12','2024-06'),('DXJ hedged same','RH_DXJ','2020-12','2024-06'),
                  ('EZA Nene','RH_EZA','2015-11','2015-12'),('MCHI peak-trough','RH_MCHI','2021-02','2022-10'),('KWEB peak-trough','RH_KWEB','2021-02','2022-10')]:
    print(lab, a, b, f'{RR(c,a,b)*100:+.0f}%')
# UK mini-budget (daily, dividend-adjusted local files)
for t in ['EWU','EFA','SPY']:
    d=pd.read_csv(f'/home/user/moneyline-upgrade/data/universe_pit_all/{t}.csv',parse_dates=['date']).set_index('date')['close']
    base=d.loc['2022-09-22']
    print('mini-budget',t,{k:f'{(d.loc[k]/base-1)*100:+.1f}%' for k in ['2022-09-27','2022-10-31','2023-09-22']})
# Notes: RH_* = Robinhood monthly closes (split-adjusted, price-only; RH_EWJ has an unadjusted 2016 reverse split - do not use);
# TR_* = local dividend-adjusted daily closes resampled to month-end. Data pulled 2026-10-16; last full month 2026-09.
