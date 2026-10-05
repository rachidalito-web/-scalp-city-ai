from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
import math, random
import numpy as np
import pandas as pd

try:
    import ccxt
except Exception:
    ccxt = None

@dataclass
class Vote:
    agent: str
    signal: str
    score: float
    confidence: float
    reason: str

def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def rsi(s, n=14):
    d=s.diff()
    up=d.clip(lower=0).rolling(n).mean()
    dn=(-d.clip(upper=0)).rolling(n).mean()
    rs=up/(dn.replace(0,np.nan))
    return (100-(100/(1+rs))).fillna(50)

def atr(df, n=14):
    pc=df.close.shift(1)
    tr=pd.concat([(df.high-df.low).abs(),(df.high-pc).abs(),(df.low-pc).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean().bfill()

class MarketAgent:
    name="MARKET"
    def fetch(self, symbol="BTC/USDT", timeframe="5m", limit=300):
        if ccxt:
            try:
                ex=ccxt.binance({"enableRateLimit":True})
                rows=ex.fetch_ohlcv(symbol,timeframe=timeframe,limit=limit)
                df=pd.DataFrame(rows,columns=["timestamp","open","high","low","close","volume"])
                df["timestamp"]=pd.to_datetime(df.timestamp,unit="ms")
                return df, "BINANCE PUBLIC"
            except Exception:
                pass
        # fallback so the dashboard always works
        rng=np.random.default_rng(42)
        ret=rng.normal(0,0.002,limit)
        close=65000*np.exp(np.cumsum(ret))
        op=np.r_[close[0],close[:-1]]
        high=np.maximum(op,close)*(1+rng.uniform(0,0.002,limit))
        low=np.minimum(op,close)*(1-rng.uniform(0,0.002,limit))
        vol=rng.lognormal(7,0.4,limit)
        df=pd.DataFrame({"timestamp":pd.date_range(end=pd.Timestamp.now(),periods=limit,freq="5min"),
                         "open":op,"high":high,"low":low,"close":close,"volume":vol})
        return df, "SIMULATOR"

class TrendAgent:
    name="TREND AI"
    def run(self,df):
        f,s=ema(df.close,20).iloc[-1],ema(df.close,50).iloc[-1]
        gap=(f/s-1)*100
        sig="BUY" if gap>.05 else "SELL" if gap<-.05 else "WAIT"
        return Vote(self.name,sig,float(np.clip(gap*4,-1,1)),min(abs(gap)*4,1),f"EMA20/50 verschil {gap:+.2f}%")

class MomentumAgent:
    name="MOMENTUM AI"
    def run(self,df):
        x=float(rsi(df.close).iloc[-1])
        if x<35: sig,score="BUY",(50-x)/25
        elif x>65: sig,score="SELL",-(x-50)/25
        else: sig,score="WAIT",(50-x)/100
        return Vote(self.name,sig,float(np.clip(score,-1,1)),min(abs(x-50)/25,1),f"RSI {x:.1f}")

class VolatilityAgent:
    name="VOLATILITY AI"
    def run(self,df):
        a=float(atr(df).iloc[-1]/df.close.iloc[-1]*100)
        # volatility is a filter, not directional alpha
        conf=min(a/2,1)
        return Vote(self.name,"WAIT",0.0,conf,f"ATR {a:.2f}% — {'hoog risico' if a>1.2 else 'normaal'}")

class VolumeAgent:
    name="VOLUME AI"
    def run(self,df):
        v=float(df.volume.iloc[-1]/df.volume.rolling(30).mean().iloc[-1])
        direction=np.sign(df.close.iloc[-1]-df.open.iloc[-1])
        score=float(np.clip((v-1)*direction,-1,1))
        sig="BUY" if score>.15 else "SELL" if score<-.15 else "WAIT"
        return Vote(self.name,sig,score,min(abs(v-1),1),f"Volume {v:.2f}× gemiddelde")

class CriticAgent:
    name="CRITIC AI"
    def run(self,df,votes):
        directions=[v.score for v in votes if v.agent!="VOLATILITY AI"]
        disagreement=float(np.std(directions)) if directions else 0
        move=abs(float(df.close.pct_change().iloc[-1]))*100
        danger=min(1, disagreement*.7 + move/2)
        return Vote(self.name,"BLOCK" if danger>.65 else "PASS",-danger,danger,
                    f"Tegenspraak {disagreement:.2f}; laatste candle {move:.2f}%")

class RiskAgent:
    name="RISK AI"
    def run(self,df,equity=10000,risk_pct=.5):
        price=float(df.close.iloc[-1]); a=float(atr(df).iloc[-1])
        stopdist=max(a*1.5,price*.003)
        riskcash=equity*(risk_pct/100)
        qty=riskcash/stopdist
        return {"agent":self.name,"price":price,"atr":a,"risk_cash":riskcash,
                "qty":qty,"stop_distance":stopdist,"take_distance":stopdist*2}

class DecisionAgent:
    name="MASTER AI"
    weights={"TREND AI":.38,"MOMENTUM AI":.30,"VOLUME AI":.22,"VOLATILITY AI":.10}
    def run(self,votes,critic):
        raw=sum(v.score*self.weights.get(v.agent,0) for v in votes)
        penalty=.55 if critic.signal=="BLOCK" else 1.0
        score=float(np.clip(raw*penalty,-1,1))
        conf=min(abs(score)*1.35,1)
        sig="BUY" if score>.22 else "SELL" if score<-.22 else "WAIT"
        return Vote(self.name,sig,score,conf,f"Gewogen consensus {score:+.2f}; critic {critic.signal}")

class PaperBroker:
    def __init__(self,cash=10000):
        self.cash=float(cash); self.position=0.0; self.entry=None; self.trades=[]
    def equity(self,price): return self.cash+self.position*price
    def act(self,decision,risk):
        p=risk["price"]; now=datetime.now().strftime("%H:%M:%S")
        if decision.signal=="BUY" and self.position==0:
            qty=min(risk["qty"], self.cash/p)
            if qty>0:
                self.position=qty; self.cash-=qty*p; self.entry=p
                self.trades.append({"time":now,"action":"BUY","price":p,"qty":qty,"pnl":0.0})
        elif decision.signal=="SELL" and self.position>0:
            pnl=(p-self.entry)*self.position
            self.cash+=self.position*p
            self.trades.append({"time":now,"action":"SELL","price":p,"qty":self.position,"pnl":pnl})
            self.position=0; self.entry=None

class TradingCity:
    def __init__(self):
        self.market=MarketAgent(); self.agents=[TrendAgent(),MomentumAgent(),VolatilityAgent(),VolumeAgent()]
        self.critic=CriticAgent(); self.risk=RiskAgent(); self.master=DecisionAgent()
    def cycle(self,symbol,timeframe,equity,risk_pct):
        df,source=self.market.fetch(symbol,timeframe)
        votes=[a.run(df) for a in self.agents]
        critic=self.critic.run(df,votes)
        risk=self.risk.run(df,equity,risk_pct)
        master=self.master.run(votes,critic)
        return df,source,votes,critic,risk,master
