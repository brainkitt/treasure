import sys, copy, numpy as np, pandas as pd
sys.path.insert(0,'.')
from arena import evaluate2 as ev
import importlib.util
def ev_variant(legs, risk_cap=None, B=300):
    mod=ev.load_strategy('agents/IDX/strategy.py')
    mod.LEGS=[l for l in mod.LEGS if l['symbol_id'] in legs]
    if risk_cap:
        f=mod.signals
        def g(bars,p,spec,f=f):
            od=f(bars,p,spec); return od[od.sl*od.volume<=risk_cap].reset_index(drop=True)
        mod.signals=g
    mod.START_BALANCE=B
    specs=ev.load_specs('agents/IDX/strategy.py')
    tr,days,orders,ok,swap_ok,margin=ev.run_legs(mod,specs)
    days=pd.DatetimeIndex(days); split=days[int(len(days)*0.7)]
    f=ev.stats(tr,days,B); i=ev.stats(tr[tr.entry_time<split],days[days<split],B); o=ev.stats(tr[tr.entry_time>=split],days[days>=split],B)
    mc=ev.monte_carlo(tr.pnl.to_numpy())
    rec=max(mc['dd95']/0.25,abs(f['worst_trade'])/0.03,2*margin)
    gate_min=max(f['max_dd_usd']/0.25,mc['dd95']/0.35,abs(f['worst_trade'])/0.05,2*margin)
    return dict(legs=legs,cap=risk_cap,n=f['trades'],pf=round(f['pf'],2),pf_is=round(i['pf'],2),pf_oos=round(o['pf'],2),t=round(f['t_stat'],2),
                net=round(f['net'],1),dd=round(f['max_dd_usd'],1),mc95=round(mc['dd95'],1),worst=round(f['worst_trade'],1),gate_min=round(gate_min),rec=round(rec),n_oos=o['trades'])
if __name__=='__main__':
    rows=[]
    for legs in ([2517,2521,2522],[2521,2522],[2521],[2517,2521],[2517]):
        for cap in (None,6,10,15):
            rows.append(ev_variant(legs,cap))
    print(pd.DataFrame(rows).to_string())
