import json, sys, time
from jaf.params import Params
from jaf.report import run
t0=time.time(); last=[0]
def cb(f,label):
    if f-last[0]>0.05 or f>=1: last[0]=f; print(f"{f:5.0%} {label} {time.time()-t0:.0f}s", flush=True)
d=run(Params(), sweep_draws=int(sys.argv[1]) if len(sys.argv)>1 else 12, progress=cb)
json.dump(d, open(sys.argv[2] if len(sys.argv)>2 else "results.json","w"))
print("done", time.time()-t0)
