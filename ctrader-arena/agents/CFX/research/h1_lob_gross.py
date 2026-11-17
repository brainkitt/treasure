from h1_lob import *
for sid in [1,2,4,6]:
    b = bars(sid); od = lob(sid, r1=8, e1=11, xh=16)
    c = b.close.to_numpy(); o = b.open.to_numpy()
    g = [(c[min(len(c)-1, i+mb+1)] - o[i+1]) * s / PIP[sid] for i, s, mb in zip(od.idx, od.side, od.max_bars)]
    g = np.array(g); sp = split_time(sid); isx = (b.time.to_numpy()[od.idx] < sp)
    print(NAMES[sid], "gross pips to 16:00: all %.2f (t=%.2f) IS %.2f OOS %.2f  spread %.1f" % (g.mean(), g.mean()/g.std()*np.sqrt(len(g)), g[isx].mean(), g[~isx].mean(), SPREAD[sid]/PIP[sid]))
