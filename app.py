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
    
    # Advanced browser emulation headers to prevent empty drops and blocks
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code != 200:
            return None, None, None
            
        html_content = response.text
        
        # --- A. Extract Nifty Spot Price via Text Parsing ---
        spot_price = None
        # Target common Nifty Index patterns on the site structure
        spot_match = re.search(r'(?:spot|nifty|price)[:\s₹]*([23]\d{3,4}\.\d{2})', html_content, re.IGNORECASE)
        if not spot_match:
            spot_match = re.search(r'([23]\d{3,4}\.\d{2})', html_content) # Absolute fall-back number matching
            
        if spot_match:
            spot_price = float(spot_match.group(1).replace(",", ""))
        
        # --- B. Parse HTML Table via explicit positional indexes ---
        # Using lxml parser to strictly capture table tags directly
        tables = pd.read_html(html_content, flavor='lxml')
        if not tables:
            return None, None, None
            
        df = tables[0] # Grab the target Option Chain matrix
        
        # Resolve MultiIndex issues if the page structure alters header tags
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [str(col[1] if len(col) > 1 else col[0]).strip() for col in df.columns.values]
            
        # --- C. True Coordinate Extraction ---
        # Optionchainlive structural standard positions:
        # Col 4 = CE (Call) IV | Center Column = Strike Price | Col -5 = PE (Put) IV
        num_cols = len(df.columns)
        
        # Let's find the true index position of the center strike column
        strike_col_idx = None
        for i, col_name in enumerate(df.columns):
            if "strike" in str(col_name).lower():
                strike_col_idx = i
                break
                
        if strike_col_idx is None:
            strike_col_idx = num_cols // 2 # Fallback center anchor point
            
        # Hard lock true column index targets relative to center
        call_iv_idx = 4  # Standard structural index position for Call IV
        put_iv_idx = num_cols - 5 if num_cols > 10 else strike_col_idx + 4 # Standard position for Put IV
        
        # Clean Strike rows to calculate exact ATM mathematical distances
        df.iloc[:, strike_col_idx] = pd.to_numeric(df.iloc[:, strike_col_idx].astype(str).str.replace(",", ""), errors='coerce')
        df = df.dropna(subset=[df.columns[strike_col_idx]])
        
        # --- D. Track Closest ATM Strike Row ---
        if spot_price and spot_price > 0:
            closest_idx = (df.iloc[:, strike_col_idx] - spot_price).abs().idxmin()
            atm_row = df.loc[closest_idx]
            atm_strike = atm_row.iloc[strike_col_idx]
        else:
            # Absolute fallback if spot price regex is blocked
            mid_idx = len(df) // 2
            atm_row = df.iloc[mid_idx]
            atm_strike = atm_row.iloc[strike_col_idx]

        # --- E. Extract True Raw Float Values (The 5% and 6% data columns) ---
        call_iv_raw = str(atm_row.iloc[call_iv_idx]).replace("%", "").strip()
        put_iv_raw = str(atm_row.iloc[put_iv_idx]).replace("%", "").strip()
        
        atm_call_iv = float(call_iv_raw) if call_iv_raw.replace('.','',1).isdigit() else 0.0
        atm_put_iv = float(put_iv_raw) if put_iv_raw.replace('.','',1).isdigit() else 0.0
        
        # If extraction hit a blank cell character value like '—'
        if atm_call_iv == 0.0 or atm_put_iv == 0.0:
            return atm_strike, None, None
            
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

# Limit database size to rolling 120 ticks
if len(st.session_state.iv_history) > 120:
    st.session_state.iv_history = st.session_state.iv_history.iloc[1:]

# 4. Display Interface Components
m_col1, m_col2, m_col3, m_col4 = st.columns(4)
with m_col1:
    st.metric(label="ATM Strike", value=f"{int(strike)}" if strike else "Scanning...")
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
    st.info("Synchronizing initial structural data point arrays from the option chain table...")

# 5. Refresh Rerun loop (30 seconds)
time.sleep(30)
st.rerun()
