import sys; sys.path.insert(0,"agents/DELTA")
from lib import *
b=ny(load(2517,"M_1")); IS=b[b.time<"2026-10-23"].copy()
lc=np.log(IS.close)
def sess(h): return np.where((h>=9.5)&(h<16),"RTH",np.where((h>=3)&(h<9.5),"EUR","ASIA"))
IS["s"]=sess(IS.nyh)
r1=lc.diff()
print("M1 ret std bp by sess:", (r1.groupby(IS.s).std()*1e4).round(2).to_dict(), "spread bp", 0.36/7500*1e4)
# variance ratios within session
for k in (2,5,15,30,60):
    out={}
    for s in ("RTH","EUR","ASIA"):
        m=IS.s==s
        rk=lc.diff(k)[m]; out[s]=round(rk.var()/(k*r1[m].var()),3)
    print("VR",k,out)
# conditional continuation: past k-min return z vs next k-min ret
for k in (5,15,30,60):
    past=lc.diff(k); fut=lc.shift(-k)-lc
    for s in ("RTH","EUR","ASIA"):
        m=(IS.s==s)&past.notna()&fut.notna()
        c=np.corrcoef(past[m],fut[m])[0,1]
        z=past[m]/past[m].std(); big=z.abs()>2
        cont=(np.sign(past[m][big])*fut[m][big]).mean()*1e4
        print(f"k={k:3d} {s:5s} corr={c:+.3f}  after |z|>2: mean cont {cont:+.2f}bp n={big.sum()}")
# daily structure
rows=[]
for d,g in IS.groupby("nyd"):
    g=g.set_index("nymin")
    try:
        o=g.open[570]; c10=g.close[599]; c1530=g.close[929]; c16=g.close[959]; c12=g.close[719]
        pc=g.open.iloc[0]
        rows.append(dict(d=d, on=np.log(o/pc), f30=np.log(c10/o), mid=np.log(c1530/c10), l30=np.log(c16/c1530), rest=np.log(c16/c10), am=np.log(c12/c10), pm=np.log(c16/c12)))
    except KeyError: pass
D=pd.DataFrame(rows); print(len(D),"days")
print(D.drop(columns="d").corr().round(2).to_string())
print("mean bp:", (D.drop(columns="d").mean()*1e4).round(1).to_dict())
print("sign agree f30->l30:", (np.sign(D.f30)==np.sign(D.l30)).mean(), " f30->rest:", (np.sign(D.f30)==np.sign(D.rest)).mean(), "on->f30", (np.sign(D.on)==np.sign(D.f30)).mean())
