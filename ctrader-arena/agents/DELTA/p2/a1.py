from core import *
b = load(2517, "M_15")
cutoff = pd.Timestamp("2026-03-26")
tr = run(b)
old = tr[tr.entry_time < cutoff]; new = tr[tr.entry_time >= cutoff]
print(line(old, "FROZEN unseen <2026-03-26")); print(line(new, "seen >=2026-03-26"))
print(half(tr).to_string())
for s in (0.0, 0.54, 0.72):
    t = run(b, spread=s); print(line(t[t.entry_time < cutoff], f"unseen spread {s}"))
print("atr median by half-year:")
