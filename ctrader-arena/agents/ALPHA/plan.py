"""Weekend-aware paging plan: prints toTimestamps walking back `days` calendar days, stepping `bars` trading minutes*tf."""
import sys, pandas as pd
def is_open(t):  # conservative (wider than reality) -> overlap rather than gaps
    wd, h = t.weekday(), t.hour
    if wd == 5: return False
    if wd == 4 and h >= 22: return False
    if wd == 6 and h < 21: return False
    return True
def plan(days, tf, end="2026-11-11T21:45:00Z", bars=960):
    end = pd.Timestamp(end).tz_localize(None); start = end - pd.Timedelta(days=days)
    out = []; t = end
    while t > start:
        out.append(t.strftime("%Y-%m-%dT%H:%M:%SZ"))
        left = bars * tf
        while left > 0:
            t -= pd.Timedelta(minutes=15)
            if is_open(t): left -= 15
        # if we landed in closed period keep going back handled by loop
    return out
if __name__ == "__main__":
    p = plan(float(sys.argv[1]), int(sys.argv[2]))
    print(len(p)); print(" ".join(p))
