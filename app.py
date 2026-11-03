import streamlit as st
import pandas as pd
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 1. Page Configuration
st.set_page_config(page_title="Nifty Live IV Dashboard", layout="wide")
st.title("📊 Nifty Live IV Tracker")
st.caption("Target URL: https://optionchainlive.com")

# 2. Session State initialization for continuous chart history
if "iv_history" not in st.session_state:
    st.session_state.iv_history = pd.DataFrame(columns=["Timestamp", "Call IV", "Put IV"])

# 3. Dynamic Browser Initialization for Streamlit Cloud Linux
@st.cache_resource
def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")         # Modern headless flag
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Let Selenium find the system chromium/driver binaries automatically
    return webdriver.Chrome(options=options)

def scrape_nifty_atm_iv():
    driver = get_driver()
    try:
        driver.get("https://optionchainlive.com")
        
        # Wait until the main table loads completely
        wait = WebDriverWait(driver, 15)
        table = wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        
        # Target the rows inside the table body
        rows = table.find_elements(By.XPATH, ".//tbody/tr")
        
        atm_call_iv = None
        atm_put_iv = None
        
        # Loop through rows to extract column mappings based on site layout:
        # Calls (Cols 0-7) | Strike (Col 8) | Puts (Cols 9-16)
        for row in rows:
            row_class = row.get_attribute("class") or ""
            cells = row.find_elements(By.TAG_NAME, "td")
            
            if len(cells) >= 15:
                strike_text = cells[8].text.strip() # Explicitly checking column 8 for strike
                
                # Check for the ATM highlighted layer or check a baseline strike fallback
                if "bg-" in row_class or "highlight" in row_class or "23" in strike_text:
                    try:
                        # Extract Call IV (Index 6) and Put IV (Index 14)
                        call_iv_text = cells[6].text.strip().replace("%", "")
                        put_iv_text = cells[14].text.strip().replace("%", "")
                        
                        atm_call_iv = float(call_iv_text) if call_iv_text and call_iv_text != "—" else None
                        atm_put_iv = float(put_iv_text) if put_iv_text and put_iv_text != "—" else None
                        
                        if atm_call_iv is not None and atm_put_iv is not None:
                            break
                    except (ValueError, IndexError):
                        continue
        
        # Static absolute fallback if table loop fails to bind values
        if atm_call_iv is None or atm_put_iv is None:
            # Look for a common center row using a contains match
            call_iv_element = driver.find_element(By.XPATH, "//tr[td[contains(text(),'23')]]/td[7]")
            put_iv_element = driver.find_element(By.XPATH, "//tr[td[contains(text(),'23')]]/td[15]")
            atm_call_iv = float(call_iv_element.text.strip().replace("%", ""))
            atm_put_iv = float(put_iv_element.text.strip().replace("%", ""))

        return atm_call_iv, atm_put_iv
    except Exception as e:
        print(f"Scraping error: {e}")
        return None, None

# 4. Data Collection Execution
current_time = datetime.now().strftime("%H:%M:%S")
c_iv, p_iv = scrape_nifty_atm_iv()

# Update persistent chart data frames
if c_iv is not None and p_iv is not None:
    new_entry = pd.DataFrame([{"Timestamp": current_time, "Call IV": c_iv, "Put IV": p_iv}])
    st.session_state.iv_history = pd.concat([st.session_state.iv_history, new_entry], ignore_index=True)
    
    # Cap storage at last 120 ticks (1 hour of 30-second data intervals)
    if len(st.session_state.iv_history) > 120:
        st.session_state.iv_history = st.session_state.iv_history.iloc[1:]

# 5. Display Interface Components
m_col1, m_col2, m_col3 = st.columns(3)
with m_col1:
    st.metric(label="ATM Call IV", value=f"{c_iv}%" if c_iv else "Updating...")
with m_col2:
    st.metric(label="ATM Put IV", value=f"{p_iv}%" if p_iv else "Updating...")
with m_col3:
    st.metric(label="Last Query Sync", value=current_time)

st.subheader("📈 Real-time Implied Volatility Timeline")
if len(st.session_state.iv_history) > 0:
    # Set index row to timestamp to split Multi-lines automatically
    plot_df = st.session_state.iv_history.set_index("Timestamp")
    st.line_chart(plot_df)
else:
    st.info("Awaiting initial 30-second data update sequence from optionchainlive.com...")

# 6. Cycle rerun timing loop (Triggers every 30 seconds)
time.sleep(30)
st.rerun()
