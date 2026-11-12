import sys; sys.path.insert(0,"agents/DELTA")
from lib import *; import fam
SPR=0.36; V=0.1; CAP=14; N=32
p=ny(load(2517,"M_15")); p=p[p.time<"2026-09-10"].reset_index(drop=True)
m1=load(2517,"M_1"); b=ny(engine.resample(m1,15))
def sigs(x):
    hm=fam.hours_mask(x,3,9.5); od=fam.donchian(x,N,2,1,16,V,hm=hm,cap=CAP,fade=True)
    pos=np.searchsorted(x.m1_idx.to_numpy(),od.idx.to_numpy()) if "m1_idx" in x else od.idx.to_numpy()
    return od,pos
# --- excursion profile on pre-sample (all signals, no exits), in ATR units, signed in trade direction
od,pos=sigs(p); a=fam.atr(p,14).to_numpy(); c=p.close.to_numpy(); h=p.high.to_numpy(); l=p.low.to_numpy()
K=24; prof=[]; mfe=[]; mae=[]
for i,s in zip(pos,od.side.to_numpy()):
    if i+K>=len(p): continue
    e=c[i]; path=(c[i+1:i+K+1]-e)*s/a[i]; prof.append(path)
    hh=(h[i+1:i+K+1]-e)*s/a[i]; ll=(l[i+1:i+K+1]-e)*s/a[i]
    fav=np.maximum.accumulate(np.maximum(hh,ll)); adv=np.minimum.accumulate(np.minimum(hh,ll)); mfe.append(fav); mae.append(adv)
prof=np.array(prof); mfe=np.array(mfe); mae=np.array(mae)
print("signals",len(prof)); print("bars  mean_close  median  %>0   meanMFE  meanMAE   (ATR units)")
for k in (1,2,3,4,6,8,12,16,24):
    print(f"{k:3d}  {prof[:,k-1].mean():+.3f}  {np.median(prof[:,k-1]):+.3f}  {(prof[:,k-1]>0).mean():.2f}  {mfe[:,k-1].mean():+.2f}  {mae[:,k-1].mean():+.2f}")
print("P(MFE16>=x):",{x:round((mfe[:,15]>=x).mean(),2) for x in (0.5,0.75,1,1.5,2,3)}, " P(MAE16<=-x):",{x:round((mae[:,15]<=-x).mean(),2) for x in (1,1.5,2,3)})
# conditional: after 2 bars, in profit vs not -> final at 16
for k in (2,4):
    g=prof[:,k-1]>0; print(f"if >0 after {k} bars: mean@16 {prof[g,15].mean():+.3f} (n={g.sum()}), else {prof[~g,15].mean():+.3f} (n={(~g).sum()})")
# --- exit variants expressible in the engine: pre-sample vs forward
def variant(x,kind,par):
    od,pos=sigs(x); a=fam.atr(x,14).to_numpy()[pos]; cl=x.close.to_numpy()[pos]
    hi=x.high.rolling(N).max().shift(1).to_numpy()[pos]; lo=x.low.rolling(N).min().shift(1).to_numpy()[pos]
    od=od.copy(); mb=16 if "m1_idx" not in x else 240; od["max_bars"]=mb
    if kind=="mid":   od["tp"]=np.maximum(np.abs(cl-(hi+lo)/2)*par,0.25*a)
    if kind=="tp":    od["tp"]=par*a
    if kind=="sl":    od["sl"]=np.minimum(par*a,CAP)
    if kind=="hold":  od["max_bars"]=par if "m1_idx" not in x else par*15
    if kind=="trail": od["tp"]=0.0; od["trail"]=par*a
    if kind=="sltp":  od["sl"]=np.minimum(par[0]*a,CAP); od["tp"]=par[1]*a
    return od
def line(kind,par):
    q=engine.simulate(p,variant(p,kind,par),spread=SPR); t=engine.simulate(m1,variant(b,kind,par),spread=SPR)
    i=t[t.entry_time<"2026-10-23"]; o=t[t.entry_time>="2026-10-23"]; a_=q[q.entry_time<"2026-06-18"]; c_=q[q.entry_time>="2026-06-18"]
    print(f"{kind:5s} {str(par):10s} | pre PF {pf(q.pnl):.2f} (h1 {pf(a_.pnl):.2f} h2 {pf(c_.pnl):.2f}) n={len(q)} win={(q.pnl>0).mean():.2f} | fwd PF {pf(t.pnl):.2f} IS {pf(i.pnl):.2f} OOS {pf(o.pnl):.2f} n={len(t)}")
line("tp",1.0)
for f in (0.25,0.33,0.5,0.75,1.0): line("mid",f)
for k in (2,4,8): line("hold",k)
for k in (1,1.5,2): line("trail",k)
for sp_ in ((1,1),(1.5,1.5),(2,2),(3,1.5),(1,0.5),(1.5,2)): line("sltp",sp_)
