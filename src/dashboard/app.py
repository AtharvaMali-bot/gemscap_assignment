import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import requests
import datetime

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & BLOOMBERG STYLING
# ---------------------------------------------------------
st.set_page_config(layout="wide", page_title="Gemscap Quant Terminal", page_icon="⚡")

st.markdown("""
<style>
    /* Dark Theme Core */
    .stApp { background-color: #000000; color: #ff9900; }
    
    /* Metrics Containers */
    div[data-testid="metric-container"] {
        background-color: #121212;
        border: 1px solid #333;
        padding: 10px;
        border-radius: 4px;
        color: #ff9900;
    }
    div[data-testid="metric-container"] label { color: #888; font-family: 'Courier New', monospace; }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] { color: #f0f0f0; font-family: 'Courier New', monospace; font-weight: bold; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #1a1a1a; border-right: 1px solid #333; }
    
    /* Tables */
    .stDataFrame { border: 1px solid #333; }
    
    /* Headers */
    h1, h2, h3 { font-family: 'Arial', sans-serif; color: #ff9900; text-transform: uppercase; letter-spacing: 1px; }
    
    /* Hide Streamlit Cruft */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. QUANT ANALYTICS ENGINE
# ---------------------------------------------------------
def calculate_metrics(df, window):
    """
    Computes Pairs Trading metrics: Hedge Ratio (Beta), Spread, Z-Score, Correlation.
    """
    if len(df) < window:
        return df, None
    
    # 1. Rolling Correlation
    df['corr'] = df['price_y'].rolling(window=window).corr(df['price_x'])
    
    # 2. Rolling Beta (Hedge Ratio) = Cov(x,y) / Var(x)
    cov = df['price_y'].rolling(window=window).cov(df['price_x'])
    var = df['price_x'].rolling(window=window).var()
    df['beta'] = cov / var
    
    # 3. Spread = Y - (Beta * X)
    # Using the latest beta for the spread calculation creates a dynamic spread
    df['spread'] = df['price_y'] - (df['beta'] * df['price_x'])
    
    # 4. Z-Score of the Spread
    df['spread_mean'] = df['spread'].rolling(window=window).mean()
    df['spread_std'] = df['spread'].rolling(window=window).std()
    
    # Handle division by zero
    df['z_score'] = 0.0
    mask = df['spread_std'] > 0
    df.loc[mask, 'z_score'] = (df.loc[mask, 'spread'] - df.loc[mask, 'spread_mean']) / df.loc[mask, 'spread_std']
    
    return df, df.iloc[-1]

# ---------------------------------------------------------
# 3. BINANCE CLIENT (DUAL ASSET)
# ---------------------------------------------------------
class PairClient:
    """
    Fetches prices for two assets to enable pairs trading analysis.
    """
    def __init__(self, symbol_y, symbol_x):
        self.sy = symbol_y.upper() # Target Asset (e.g., ETH)
        self.sx = symbol_x.upper() # Hedge Asset (e.g., BTC)
        self.url = "https://fapi.binance.com/fapi/v1/ticker/price"
    
    def get_data(self):
        try:
            # Fetch both prices. In a production async env, these would be concurrent.
            r1 = requests.get(self.url, params={'symbol': self.sy}, timeout=2)
            r2 = requests.get(self.url, params={'symbol': self.sx}, timeout=2)
            
            if r1.status_code == 200 and r2.status_code == 200:
                return float(r1.json()['price']), float(r2.json()['price'])
        except Exception:
            return None, None
        return None, None

# ---------------------------------------------------------
# 4. SIDEBAR CONTROLS
# ---------------------------------------------------------
st.sidebar.markdown("## ⚡ GEMSCAP TERMINAL")

# A. Feed Control
st.sidebar.subheader("📡 FEED CONTROL")
run_live = st.sidebar.toggle("🔴 LIVE CONNECTION", value=True, help="Toggle OFF to stop stream and enable Export.")

st.sidebar.markdown("---")

# B. Asset Config (Pairs Selection)
st.sidebar.subheader("🛠 PAIRS CONFIG")
col1, col2 = st.sidebar.columns(2)
symbol_y = col1.selectbox("Long (Y)", ["ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"], index=0)
symbol_x = col2.selectbox("Short (X)", ["BTCUSDT", "ETHUSDT"], index=0)

# C. Algo Parameters
st.sidebar.markdown("---")
st.sidebar.subheader("⚠️ MODEL PARAMS")
z_threshold = st.sidebar.slider("Z-Score Trigger", 1.0, 4.0, 2.0, 0.1)
window_size = st.sidebar.number_input("Rolling Window (N)", value=30, min_value=10)
resample_freq = st.sidebar.select_slider("Resample Frequency", options=['Tick', '10s', '1m', '5m'], value='Tick')

# ---------------------------------------------------------
# 5. STATE MANAGEMENT
# ---------------------------------------------------------
# Initialize buffer with columns for both assets and calc metrics
if 'buffer' not in st.session_state:
    st.session_state.buffer = pd.DataFrame(columns=['timestamp', 'price_y', 'price_x', 'spread', 'z_score', 'beta', 'corr'])

# Reset buffer if pair changes
pair_key = f"{symbol_y}-{symbol_x}"
if 'last_pair' not in st.session_state:
    st.session_state.last_pair = pair_key
elif st.session_state.last_pair != pair_key:
    st.session_state.buffer = pd.DataFrame(columns=['timestamp', 'price_y', 'price_x', 'spread', 'z_score', 'beta', 'corr'])
    st.session_state.last_pair = pair_key

client = PairClient(symbol_y, symbol_x)

# ---------------------------------------------------------
# 6. DASHBOARD LAYOUT
# ---------------------------------------------------------
# Header
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown(f"### {symbol_y} / {symbol_x} <span style='font-size:12px; color:gray'>[STAT ARB]</span>", unsafe_allow_html=True)
with c2:
    status_text = "🟢 LIVE" if run_live else "🔴 PAUSED"
    st.markdown(f"**STATUS: {status_text}**")

# Metrics Row
m1, m2, m3, m4 = st.columns(4)
metric_spread = m1.empty()
metric_z = m2.empty()
metric_beta = m3.empty()
metric_corr = m4.empty()

# Charts
tab_main, tab_raw, tab_data = st.tabs(["📊 SPREAD ANALYSIS", "📈 RAW PRICES", "📋 DATA LOG"])

with tab_main:
    chart_spread_placeholder = st.empty()

with tab_raw:
    chart_price_placeholder = st.empty()

with tab_data:
    st.caption("Recent calculated data points")
    data_table_placeholder = st.empty()

# ---------------------------------------------------------
# 7. EXPORT UTILITY
# ---------------------------------------------------------
if not run_live:
    st.warning("⚠️ Feed Paused. Analysis stopped.")
    if not st.session_state.buffer.empty:
        csv_data = st.session_state.buffer.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="💾 DOWNLOAD SESSION CSV",
            data=csv_data,
            file_name=f"{symbol_y}_{symbol_x}_arb_data.csv",
            mime="text/csv",
            key="download-btn"
        )

# ---------------------------------------------------------
# 8. MAIN ANALYTICS LOOP
# ---------------------------------------------------------
while run_live:
    # 1. Fetch Data (Dual Asset)
    py, px = client.get_data()
    
    if py and px:
        now = pd.Timestamp.now()
        
        # 2. Append Raw Data
        new_row = pd.DataFrame([{'timestamp': now, 'price_y': py, 'price_x': px}])
        st.session_state.buffer = pd.concat([st.session_state.buffer, new_row], ignore_index=True)
        
        # 3. Resampling & Analytics
        # We work on a copy to handle resampling without losing raw ticks
        df_raw = st.session_state.buffer.copy()
        df_raw.set_index('timestamp', inplace=True)
        
        # Apply Resampling if selected
        if resample_freq != 'Tick':
            # Resample rule: '10s', '1min', '5min'
            rule = resample_freq.replace('m', 'min')
            # Use 'last' for price closing values
            df_analysis = df_raw[['price_y', 'price_x']].resample(rule).last().dropna()
        else:
            df_analysis = df_raw[['price_y', 'price_x']]

        # Only run analytics if we have enough history
        last_stats = None
        if len(df_analysis) > window_size:
            df_analysis, last_stats = calculate_metrics(df_analysis, window_size)

        # 4. Render Interface
        if last_stats is not None:
            # Extract metrics
            spread = last_stats['spread']
            z = last_stats['z_score']
            beta = last_stats['beta']
            corr = last_stats['corr']
            
            # Update Top Metrics
            metric_spread.metric("SPREAD", f"{spread:.4f}")
            
            z_col = "inverse" if abs(z) > z_threshold else "normal"
            metric_z.metric("Z-SCORE", f"{z:.2f}", delta=z, delta_color=z_col)
            
            metric_beta.metric("HEDGE RATIO (β)", f"{beta:.3f}")
            metric_corr.metric("CORRELATION", f"{corr:.3f}")
            
            # --- PLOT 1: Spread & Z-Score ---
            fig_s = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
            
            # Spread Line
            fig_s.add_trace(go.Scatter(x=df_analysis.index, y=df_analysis['spread'], name='Spread', line=dict(color='#00F0FF', width=2)), row=1, col=1)
            
            # Mean Line (Zero if normalized, or rolling mean)
            fig_s.add_trace(go.Scatter(x=df_analysis.index, y=df_analysis['spread_mean'], line=dict(width=1, dash='dot', color='#888'), name='Mean'), row=1, col=1)
            
            # Bands (Mean +/- 2 Std Dev) - Optional visual aid
            if 'spread_std' in df_analysis:
                upper = df_analysis['spread_mean'] + (2 * df_analysis['spread_std'])
                lower = df_analysis['spread_mean'] - (2 * df_analysis['spread_std'])
                fig_s.add_trace(go.Scatter(x=df_analysis.index, y=upper, line=dict(width=0), showlegend=False), row=1, col=1)
                fig_s.add_trace(go.Scatter(x=df_analysis.index, y=lower, fill='tonexty', fillcolor='rgba(255,255,255,0.05)', line=dict(width=0), showlegend=False), row=1, col=1)

            # Z-Score Bars
            colors = ['#FF4B4B' if abs(x) > z_threshold else '#333' for x in df_analysis['z_score']]
            fig_s.add_trace(go.Bar(x=df_analysis.index, y=df_analysis['z_score'], marker_color=colors, name='Z-Score'), row=2, col=1)
            
            # Z-Score Threshold Lines
            fig_s.add_hline(y=z_threshold, line_dash="dot", line_color="#FF4B4B", row=2, col=1)
            fig_s.add_hline(y=-z_threshold, line_dash="dot", line_color="#FF4B4B", row=2, col=1)

            fig_s.update_layout(
                height=500, template="plotly_dark", 
                margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                showlegend=False,
                font=dict(family="Courier New")
            )
            # Auto-scale Y-Axis slightly
            if len(df_analysis) > 0:
                 s_min, s_max = df_analysis['spread'].min(), df_analysis['spread'].max()
                 fig_s.update_yaxes(range=[s_min-(abs(s_min)*0.01), s_max+(abs(s_max)*0.01)], row=1, col=1)

            chart_spread_placeholder.plotly_chart(fig_s, use_container_width=True)
            
            # --- PLOT 2: Raw Prices (Comparison) ---
            fig_p = make_subplots(specs=[[{"secondary_y": True}]])
            fig_p.add_trace(go.Scatter(x=df_analysis.index, y=df_analysis['price_y'], name=symbol_y, line=dict(color='#00ffcc')), secondary_y=False)
            fig_p.add_trace(go.Scatter(x=df_analysis.index, y=df_analysis['price_x'], name=symbol_x, line=dict(color='#ff9900')), secondary_y=True)
            
            fig_p.update_layout(height=400, template="plotly_dark", margin=dict(l=0,r=0,t=20,b=0), paper_bgcolor='rgba(0,0,0,0)')
            chart_price_placeholder.plotly_chart(fig_p, use_container_width=True)

            # Update Log
            data_table_placeholder.dataframe(df_analysis.tail(5).sort_index(ascending=False)[['price_y', 'price_x', 'spread', 'z_score', 'beta']], use_container_width=True)
        
        else:
            # Waiting for enough data
            metric_spread.info(f"Collecting Data... ({len(df_analysis)}/{window_size})")

    # Rate limit (avoid Binance ban)
    time.sleep(1.0)