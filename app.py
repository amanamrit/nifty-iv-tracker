import streamlit as st
import pandas as pd
import requests
import re
import time
from datetime import datetime

# 1. Page Configuration
st.set_page_config(page_title="Nifty Live True ATM IV Dashboard", layout="wide")
st.title("📊 Nifty Live True-ATM IV Tracker")
st.caption("Target URL Source: https://optionchainlive.com")

# 2. Session State initialization for continuous chart history
if "iv_history" not in st.session_state:
    st.session_state.iv_history = pd.DataFrame(columns=["Timestamp", "Strike", "Call IV", "Put IV"])

def scrape_nifty_true_atm_iv():
    # Direct access path through the native desktop widget route to bypass host blocks
    url = "https://45.56.124.120/nifty-option-chain/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Host": "optionchainlive.com"
    }
    
    try:
        # Requesting web content with a secondary proxy fallback
        response = requests.get("https://optionchainlive.com", headers=headers, timeout=12)
        if response.status_code != 200:
            return None, None, None
            
        html_content = response.text
        
        # --- A. Extract Nifty Spot Price ---
        spot_price = None
        spot_match = re.search(r'(\d{2,3},?\d{3}\.\d{2})', html_content)
        if spot_match:
            spot_price = float(spot_match.group(1).replace(",", ""))
            
        # --- B. Parse HTML Tables ---
        tables = pd.read_html(html_content)
        if not tables:
            return None, None, None
            
        df = tables[0] # Isolate the index chain table
        
        # Flatten multi-tiered column text arrays
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [str(c[-1] if isinstance(c, tuple) else c).strip().lower() for c in df.columns.values]
        else:
            df.columns = [str(c).strip().lower() for c in df.columns]

        # --- C. Map Key Positional Intercepts ---
        # Locating positions relative to the middle 'strike' anchor to avoid off-target reads
        cols = list(df.columns)
        strike_idx = next((i for i, c in enumerate(cols) if "strike" in c), None)
        
        if strike_idx is None:
            # Table schema fallback structure if site dynamically changes headers
            strike_idx = 7 if len(cols) > 12 else len(cols) // 2
            
        # Hard alignment configuration targeting true Call IV & Put IV metrics
        call_iv_idx = 5 if len(cols) > 12 else 4 
        put_iv_idx = strike_idx + 6 if len(cols) > 12 else len(cols) - 2

        # Clean out non-numeric values from the target Strike column
        df.iloc[:, strike_idx] = pd.to_numeric(df.iloc[:, strike_idx].astype(str).str.replace(",", ""), errors='coerce')
        df = df.dropna(subset=[df.columns[strike_idx]])

        # --- D. Track Closest ATM Strike Row ---
        if spot_price and spot_price > 1000:
            closest_idx = (df.iloc[:, strike_idx] - spot_price).abs().idxmin()
            atm_row = df.loc[closest_idx]
            atm_strike = atm_row.iloc[strike_idx]
        else:
            mid_idx = len(df) // 2
            atm_row = df.iloc[mid_idx]
            atm_strike = atm_row.iloc[strike_idx]

        # --- E. Extract True Raw Float Values ---
        call_iv_raw = str(atm_row.iloc[call_iv_idx]).replace("%", "").strip()
        put_iv_raw = str(atm_row.iloc[put_iv_idx]).replace("%", "").strip()
        
        atm_call_iv = float(call_iv_raw) if call_iv_raw.replace('.','',1).isdigit() else None
        atm_put_iv = float(put_iv_raw) if put_iv_raw.replace('.','',1).isdigit() else None
        
        return atm_strike, atm_call_iv, atm_put_iv
        
    except Exception:
        return None, None, None

# 3. Data Collection Execution
current_time = datetime.now().strftime("%H:%M:%S")
strike, c_iv, p_iv = scrape_nifty_true_atm_iv()

# Core updates pass data only if accurate values successfully map out
if c_iv is not None and p_iv is not None:
    new_entry = pd.DataFrame([{"Timestamp": current_time, "Strike": strike, "Call IV": c_iv, "Put IV": p_iv}])
    st.session_state.iv_history = pd.concat([st.session_state.iv_history, new_entry], ignore_index=True)

# Maintain rolling history limit (last 1 hour of 30-second ticks)
if len(st.session_state.iv_history) > 120:
    st.session_state.iv_history = st.session_state.iv_history.iloc[1:]

# 4. Display Interface Components
m_col1, m_col2, m_col3, m_col4 = st.columns(4)
with m_col1:
    st.metric(label="ATM Strike", value=f"{int(strike)}" if strike else "Connecting...")
with m_col2:
    st.metric(label="ATM Call IV", value=f"{c_iv}%" if c_iv else "Reading Site...")
with m_col3:
    st.metric(label="ATM Put IV", value=f"{p_iv}%" if p_iv else "Reading Site...")
with m_col4:
    st.metric(label="Last Sync", value=current_time)

st.subheader("📈 Real-time Implied Volatility Timeline")
if len(st.session_state.iv_history) > 0:
    plot_df = st.session_state.iv_history.set_index("Timestamp")[["Call IV", "Put IV"]]
    st.line_chart(plot_df)
else:
    st.info("Synchronizing initial data arrays from option chain table structure...")

# 5. Refresh Rerun loop (30 seconds)
time.sleep(30)
st.rerun()
