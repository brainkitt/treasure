"""Live signal engine for the demo session. OKX BTC-USDT bbo-tbt; signal when mid moved
>= THRESH within WINDOW ms (proxy for Deriv being behind by that much). Cooldown COOL s."""
import asyncio, json, ssl, time, sys, collections
import websockets
ctx=ssl.create_default_context(cafile="/root/.ccr/ca-bundle.crt")
THRESH=23.42; WINDOW=500; COOL=20; END=time.time()+float(sys.argv[1])
hist=collections.deque(); last_sig=0
sig=open("signals.jsonl","a"); tick=open("okx_ticks.jsonl","a")
async def main():
    global last_sig
    while time.time()<END:
        try:
            async with websockets.connect("wss://ws.okx.com/ws/v5/public",ssl=ctx,ping_interval=20) as ws:
                await ws.send('{"op":"subscribe","args":[{"channel":"bbo-tbt","instId":"BTC-USDT"}]}')
                print("connected",flush=True)
                while time.time()<END:
                    j=json.loads(await asyncio.wait_for(ws.recv(),30))
                    if "data" not in j: continue
                    d=j["data"][0]; ts=int(d["ts"]); mid=(float(d["bids"][0][0])+float(d["asks"][0][0]))/2
                    now=int(time.time()*1000)
                    tick.write(f"[{ts},{now},{mid}]\n")
                    hist.append((ts,mid))
                    while hist and hist[0][0]<ts-WINDOW: hist.popleft()
                    lo=min(h[1] for h in hist); hi=max(h[1] for h in hist)
                    up=mid-lo; dn=hi-mid
                    if max(up,dn)>=THRESH and now/1000-last_sig>=COOL:
                        side="BUY" if up>=dn else "SELL"
                        last_sig=now/1000
                        sig.write(json.dumps(dict(okx_ts=ts,local_ms=now,side=side,move=round(max(up,dn),2),okx_mid=mid))+"\n"); sig.flush()
                        print("SIGNAL",side,round(max(up,dn),2),flush=True)
        except Exception as e:
            print("reconnect",e,flush=True); await asyncio.sleep(1)
asyncio.run(main())
