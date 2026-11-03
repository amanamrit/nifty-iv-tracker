import streamlit as st
import pandas as pd
import requests
import re
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
    url = "https://optionchainlive.com"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        html_content = response.text
        
        # --- A. Extract Nifty Spot Price ---
        spot_match = re.search(r'(?:₹\s*)?(\d{2,3},?\d{3}\.\d{2})', html_content)
        spot_price = None
        if spot_match:
            spot_price = float(spot_match.group(1).replace(",", ""))
        
        # --- B. Parse Option Chain Tables ---
        tables = pd.read_html(html_content)
        if not tables:
            return None, None, None
            
        df = tables[0] # Target main data layout grid
        
        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            cols = ['_'.join(map(str, col)).strip().lower() for col in df.columns.values]
        else:
            cols = [str(c).strip().lower() for c in df.columns]
            
        df.columns = cols

        # --- C. Target Exact Column Text Positions ---
        strike_col_idx = None
        call_iv_idx = None
        put_iv_idx = None

        # Loop to accurately find index mapping based on text headers
        for idx, col_name in enumerate(cols):
            if "strike" in col_name:
                strike_col_idx = idx
                break
                
        if strike_col_idx is not None:
            # Calls are located before the center Strike column, Puts are after it
            for idx, col_name in enumerate(cols):
                if "iv" in col_name:
                    if idx < strike_col_idx:
                        call_iv_idx = idx
                    elif idx > strike_col_idx:
                        put_iv_idx = idx

        # Absolute fallback mapping if named columns can't be string-matched
        if strike_col_idx is None: strike_col_idx = len(cols) // 2
        if call_iv_idx is None: call_iv_idx = 4   # True IV structural position for CE
        if put_iv_idx is None: put_iv_idx = len(cols) - 5 # True IV structural position for PE

        # Clean Strike data to ensure numbers match spot price
        df.iloc[:, strike_col_idx] = pd.to_numeric(df.iloc[:, strike_col_idx].astype(str).str.replace(",", ""), errors='coerce')
        df = df.dropna(subset=[df.columns[strike_col_idx]])
        
        # --- D. Lock True ATM Row ---
        if spot_price is not None:
            closest_idx = (df.iloc[:, strike_col_idx] - spot_price).abs().idxmin()
            atm_row = df.loc[closest_idx]
            atm_strike = atm_row.iloc[strike_col_idx]
        else:
            closest_idx = len(df) // 2
            atm_row = df.iloc[closest_idx]
            atm_strike = atm_row.iloc[strike_col_idx]

        # --- E. Clean and Extract Exact Call/Put IV values ---
        call_iv_raw = str(atm_row.iloc[call_iv_idx]).replace("%", "").strip()
        put_iv_raw = str(atm_row.iloc[put_iv_idx]).replace("%", "").strip()
        
        # Parse into standard floats
        atm_call_iv = float(call_iv_raw) if call_iv_raw.replace('.','',1).isdigit() else None
        atm_put_iv = float(put_iv_raw) if put_iv_raw.replace('.','',1).isdigit() else None
        
        return atm_strike, atm_call_iv, atm_put_iv
        
    except Exception as e:
        return None, None, None

# 3. Data Collection Execution
current_time = datetime.now().strftime("%H:%M:%S")
strike, c_iv, p_iv = scrape_nifty_true_atm_iv()

# Update chart history matrix only if authentic web data maps correctly
if c_iv is not None and p_iv is not None:
    new_entry = pd.DataFrame([{"Timestamp": current_time, "Strike": strike, "Call IV": c_iv, "Put IV": p_iv}])
    st.session_state.iv_history = pd.concat([st.session_state.iv_history, new_entry], ignore_index=True)

if len(st.session_state.iv_history) > 120:
    st.session_state.iv_history = st.session_state.iv_history.iloc[1:]

# 4. Display Interface Components
m_col1, m_col2, m_col3, m_col4 = st.columns(4)
with m_col1:
    st.metric(label="ATM Strike", value=f"{int(strike)}" if strike else "Searching...")
with m_col2:
    st.metric(label="ATM Call IV", value=f"{c_iv}%" if c_iv else "N/A")
with m_col3:
    st.metric(label="ATM Put IV", value=f"{p_iv}%" if p_iv else "N/A")
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
