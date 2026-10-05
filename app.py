import time
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from engine import TradingCity, PaperBroker, ema

st.set_page_config(page_title="Scalp City AI",page_icon="🏙️",layout="wide",initial_sidebar_state="collapsed")
st.markdown("""
<style>
header{visibility:hidden}.block-container{padding:10px 10px 80px;max-width:1250px}
.stApp{background:radial-gradient(circle at 50% -10%,#163166,#060b1c 43%,#02050d 100%);color:#f3f8ff}
.hero{padding:14px 4px 8px}.logo{font-size:29px;font-weight:900;letter-spacing:1px}.sub{opacity:.66;font-size:12px}
.city{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:10px 0 14px}
.tower{border-radius:16px;padding:13px;min-height:128px;background:linear-gradient(180deg,rgba(18,42,91,.92),rgba(4,9,24,.96));border:1px solid #2877a8}
.buy{border-color:#20d99b;box-shadow:0 0 18px #20d99b22}.sell{border-color:#ff4774;box-shadow:0 0 18px #ff477422}
.wait{border-color:#3da8ff}.block{border-color:#ffad32}.sig{font-size:25px;font-weight:900}.muted{opacity:.68;font-size:12px}
div[data-testid="stMetric"]{background:#09142cb8;border:1px solid #184a73;border-radius:14px;padding:8px}
.stButton button{width:100%;border-radius:13px;min-height:45px;font-weight:800}
@media(max-width:700px){
 .block-container{padding:5px 7px 72px}.city{grid-template-columns:repeat(2,1fr);gap:7px}
 .tower{min-height:118px;padding:10px}.logo{font-size:25px}
 div[data-testid="stMetric"]{padding:5px}
}
</style>""",unsafe_allow_html=True)

if "city" not in st.session_state: st.session_state.city=TradingCity()
if "broker" not in st.session_state: st.session_state.broker=PaperBroker(10000)

st.markdown('<div class="hero"><div class="logo">🏙️ SCALP CITY AI</div><div class="sub">MULTI-AGENT CRYPTO CONTROL ROOM • PAPER MODE</div></div>',unsafe_allow_html=True)

with st.expander("⚙️ Instellingen"):
    a,b=st.columns(2)
    symbol=a.selectbox("Market",["BTC/USDT","ETH/USDT","SOL/USDT","XRP/USDT"])
    timeframe=b.selectbox("Timeframe",["1m","5m","15m","1h"],index=1)
    risk_pct=st.slider("Risico per trade (%)",.1,2.,.5,.1)
    auto=st.toggle("Automatisch verversen",True)
    st.caption("🔒 Live orders zijn vergrendeld. Alleen paper trading.")

broker=st.session_state.broker; city=st.session_state.city
df,source,votes,critic,risk,master=city.cycle(symbol,timeframe,broker.cash, risk_pct)
price=float(df.close.iloc[-1]); equity=broker.equity(price); risk=city.risk.run(df,equity,risk_pct)

m1,m2=st.columns(2)
m1.metric(symbol.replace("/"," / "),f"${price:,.2f}")
m2.metric("MASTER",master.signal,f"{master.confidence*100:.0f}% confidence")
m3,m4=st.columns(2)
m3.metric("PAPER EQUITY",f"${equity:,.2f}")
m4.metric("DATA",source)

cards=[]
for v in votes+[critic,master]:
    cls=v.signal.lower()
    if cls not in ("buy","sell","wait","block"): cls="wait"
    cards.append(f'<div class="tower {cls}"><div class="muted">{v.agent}</div><div class="sig">{v.signal}</div><b>{v.score:+.2f}</b> · {v.confidence*100:.0f}%<div class="muted">{v.reason}</div></div>')
st.markdown('<div class="city">'+''.join(cards)+'</div>',unsafe_allow_html=True)

d=df.tail(100).copy(); d["ema20"]=ema(d.close,20); d["ema50"]=ema(d.close,50)
fig=go.Figure()
fig.add_trace(go.Candlestick(x=d.timestamp,open=d.open,high=d.high,low=d.low,close=d.close,name="Price"))
fig.add_trace(go.Scatter(x=d.timestamp,y=d.ema20,name="EMA20",line={"width":1}))
fig.add_trace(go.Scatter(x=d.timestamp,y=d.ema50,name="EMA50",line={"width":1}))
fig.update_layout(template="plotly_dark",height=390,margin=dict(l=2,r=2,t=28,b=2),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,.12)",xaxis_rangeslider_visible=False,legend=dict(orientation="h"))
st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})

st.subheader("🛡️ Risk AI")
r1,r2=st.columns(2)
r1.metric("Risk budget",f"${risk['risk_cash']:.2f}")
r2.metric("Position",f"{risk['qty']:.6f}")
if master.signal=="BUY":
    st.write(f"Stop **${price-risk['stop_distance']:,.2f}** · Target **${price+risk['take_distance']:,.2f}**")
if st.button("▶ PAPER: voer MASTER-signaal uit",type="primary"):
    broker.act(master,risk); st.rerun()

with st.expander("📡 Agent message bus"):
    st.dataframe(pd.DataFrame([{"Agent":v.agent,"Signal":v.signal,"Score":round(v.score,2),"Confidence":f"{v.confidence*100:.0f}%"} for v in votes+[critic,master]]),hide_index=True,use_container_width=True)
with st.expander("📒 Paper trade log"):
    if broker.trades: st.dataframe(pd.DataFrame(broker.trades),hide_index=True,use_container_width=True)
    else: st.caption("Nog geen trades.")
st.caption("Geen financieel advies. Test uitgebreid voordat echt kapitaal wordt gebruikt.")
if auto:
    time.sleep(10); st.rerun()
