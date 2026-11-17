from d2 import *
import itertools
rows=[]
pre={}
for s in (2517,2521,2522):
    b=bars(s); D=daily_cash(b); pre[s]=(b,D)
cut={s:pre[s][0].time.iloc[int(len(pre[s][0])*0.7)] for s in pre}
for N,tpm,slm,hold in itertools.product((3,4,5,6,7,8,10),(0,0.5,0.75,1.0,1.5),(1.5,2.0,2.5,3.0,4.0),(1,2,3,4,5)):
    r={'N':N,'tp':tpm,'sl':slm,'hold':hold}; P_is=[];P_oos=[]
    for s in pre:
        b,D=pre[s]; sig,a=signal(D,'lowclose',(N,)); tr=run(b,orders(b,D,sig,a,tpm,slm,hold),s,swap_long=SW[s])
        # normalise pnl by price level (pct) so indices pool fairly
        p=(tr.pnl/tr.entry_px*100).to_numpy(); i=(pd.to_datetime(tr.entry_time)<cut[s]).to_numpy()
        P_is.append(p[i]); P_oos.append(p[~i]); r[NAME[s]+'_is']=round(pf(p[i]),2); r[NAME[s]+'_oos']=round(pf(p[~i]),2)
    pi=np.concatenate(P_is); po=np.concatenate(P_oos)
    r.update(n=len(pi)+len(po),pf_is=round(pf(pi),3),pf_oos=round(pf(po),3)); rows.append(r)
X=pd.DataFrame(rows); X.to_csv('d3.csv'); print(len(X))
for c in ['N','tp','sl','hold']:
    print(X.groupby(c)[['pf_is','pf_oos']].median().round(3).T)
print(X.sort_values('pf_is',ascending=False).head(20).to_string())
