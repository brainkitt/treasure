"""Append spot samples to ticks.csv. usage: python agents/BRAVO/tk.py "ts b10 a10 b20 a20 b30 a30" ...
(ts = epoch ms of the DS30 quote; prices typed as price*100 integers, i.e. API value / 1000)"""
import sys, os
f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ticks.csv")
new = not os.path.exists(f)
with open(f, "a") as fh:
    if new: fh.write("ts_ms,symbol,bid,ask\n")
    for a in sys.argv[1:]:
        v = a.split(); ts = int(v[0])
        for s, k in ((2464, 1), (2469, 3), (2470, 5)):
            fh.write(f"{ts},{s},{int(v[k])/100:.2f},{int(v[k+1])/100:.2f}\n")
print(sum(1 for _ in open(f)) // 3, "samples")
