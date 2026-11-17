from h4_burst import *
k, H, slm, tpm = 2.5, 2, 2.0, 0.0
for sid in [101, 102]:
    tr = sim(sid, burst(sid, k, H, slm, tpm)); sp = split_time(sid)
    p = tr.pnl.to_numpy()
    print(NAMES[sid], "long PF %.2f n%d | short PF %.2f n%d" % (pf(p[tr.side>0]), (tr.side>0).sum(), pf(p[tr.side<0]), (tr.side<0).sum()))
    ps = np.sort(p); print("  PF without top5 winners: %.2f ; reasons" % pf(ps[:-5]), tr.reason.value_counts().to_dict())
    hrs = pd.to_datetime(tr.entry_time).dt.hour
    print("  by entry-hour bucket:", tr.groupby(hrs // 6).pnl.apply(lambda x: round(pf(x.to_numpy()), 2)).to_dict())
    wd = pd.to_datetime(tr.entry_time).dt.dayofweek >= 5
    print("  weekend PF %.2f n%d weekday PF %.2f n%d" % (pf(p[wd]), wd.sum(), pf(p[~wd]), (~wd).sum()))
