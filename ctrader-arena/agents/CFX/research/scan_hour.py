from lib import *
for sid in [1,2,4,5,6,9,101,102]:
    b = bars(sid); sp = split_time(sid)
    r = (b.close - b.open) / PIP[sid]
    hr = b.time.dt.hour; isx = b.time < sp
    out = []
    for h in range(24):
        a = r[(hr == h) & isx]; o = r[(hr == h) & ~isx]
        if len(a) < 50: out.append("  .  "); continue
        ti = a.mean()/a.std()*np.sqrt(len(a)); to = o.mean()/o.std()*np.sqrt(len(o))
        out.append(f"{ti:+.1f}/{to:+.1f}" if abs(ti) > 2 else "  .  ")
    print(NAMES[sid], " ".join(f"{h:02d}:{x}" for h, x in enumerate(out) if x.strip() != "."))
