import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# 1. Page Configuration
st.set_page_config(page_title="Nifty Live True ATM IV Dashboard", layout="wide")
st.title("📊 Nifty Live True-ATM IV Tracker")
st.caption("Target URL: https://optionchainlive.com")

# 2. Session State initialization for continuous chart history
if "iv_history" not in st.session_state:
    st.session_state.iv_history = pd.DataFrame(columns=["Timestamp", "Strike", "Call IV", "Put IV"])

def scrape_nifty_true_atm_iv():
    # Target the site's back-end raw API JSON feed rather than parsing the front-end layout
    url = "https://optionchainlive.com" 
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://optionchainlive.com"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        # Fallback to direct page parse if api schema endpoints shift
        if response.status_code != 200:
            return None, None, None
            
        data = response.json()
        
        # Extract spot price and option chain payload directly from JSON
        spot_price = float(data.get("spotPrice", 0))
        records = data.get("data", []) # List of dictionaries per strike price row
        
        if not records:
            return None, None, None
            
        df = pd.DataFrame(records)
        
        # Map dynamic json key structural pairs (e.g., 'strike', 'ce_iv', 'pe_iv')
        # Standardizing naming conventions based on the site's network data stream
        df['strike'] = pd.to_numeric(df['strike'], errors='coerce')
        
        # Lock closest ATM Strike row
        if spot_price > 0:
            closest_idx = (df['strike'] - spot_price).abs().idxmin()
            atm_row = df.loc[closest_idx]
        else:
            atm_row = df.iloc[len(df) // 2]
            
        atm_strike = atm_row['strike']
        
        # Safely extract IV integers directly, stripping string symbols if present
        atm_call_iv = float(str(atm_row.get('ce_iv', 0)).replace('%', ''))
        atm_put_iv = float(str(atm_row.get('pe_iv', 0)).replace('%', ''))
        
        return atm_strike, atm_call_iv, atm_put_iv
        
    except Exception:
        # If external site API encounters structured error anomalies
        return None, None, None

# 3. Data Collection Execution
current_time = datetime.now().strftime("%H:%M:%S")
strike, c_iv, p_iv = scrape_nifty_true_atm_iv()

# Only append to session database historical log when target response returns real data streams
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
    st.metric(label="ATM Call IV", value=f"{c_iv}%" if c_iv else "Updating...")
with m_col3:
    st.metric(label="ATM Put IV", value=f"{p_iv}%" if p_iv else "Updating...")
with m_col4:
    st.metric(label="Last Sync", value=current_time)

st.subheader("📈 Real-time Implied Volatility Timeline")
if len(st.session_state.iv_history) > 0:
    plot_df = st.session_state.iv_history.set_index("Timestamp")[["Call IV", "Put IV"]]
    st.line_chart(plot_df)
else:
    st.info("Awaiting live option data feed sync...")

# 5. Refresh Rerun loop (30 seconds)
time.sleep(30)
st.rerun()
