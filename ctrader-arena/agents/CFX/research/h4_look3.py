from h4_burst import *
import sys
for k, H, slm, tpm in [(2.0, 2, 2.0, 0.0), (2.5, 2, 2.0, 0.0), (3.0, 2, 2.0, 0.0), (2.5, 3, 2.0, 0.0), (2.5, 1, 2.0, 0.0)]:
    for sid in [101, 102, 2408, 2387]:
        tr = sim(sid, burst(sid, k, H, slm, tpm))
        print(summ(tr, split_time(sid), f"{NAMES[sid]} k{k} H{H} sl{slm} tp{tpm}"))
