import streamlit as st
import pandas as pd
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 1. Page Configuration
st.set_page_config(page_title="Nifty Live IV Dashboard", layout="wide")
st.title("📊 Nifty Live IV Tracker")
st.caption("Target URL: https://optionchainlive.com/nifty-option-chain/")

# 2. Session State initialization for continuous chart history
if "iv_history" not in st.session_state:
    st.session_state.iv_history = pd.DataFrame(columns=["Timestamp", "Call IV", "Put IV"])

# 3. Headless Browser Initialization
@st.cache_resource
def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def scrape_nifty_atm_iv():
    driver = get_driver()
    try:
        driver.get("https://optionchainlive.com/nifty-option-chain/")
        
        # Wait until the main table loads completely
        wait = WebDriverWait(driver, 10)
        table = wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        
        # Target the rows inside the table body
        rows = table.find_elements(By.XPATH, ".//tbody/tr")
        
        atm_call_iv = None
        atm_put_iv = None
        
        # Loop through rows to find the highlighted At-The-Money (ATM) row.
        # Alternatively, we grab the middle strike row. Let's inspect class attributes or match the mid-point.
        for row in rows:
            # Check if this row is visually highlighted as ATM on optionchainlive (often uses custom class or styling)
            row_class = row.get_attribute("class") or ""
            
            # Fallback if no specific class: We dynamically extract columns
            # Column mapping based on standard site layout:
            # Calls (Cols 0-7) | Strike (Col 8) | Puts (Cols 9-16)
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 15:
                # Let's target Nifty spot near ~23686 (e.g., Strike 23700)
                strike_text = cells[8].text.strip()
                
                # Check for the ATM row (Optionchainlive highlights the ATM layer)
                if "bg-" in row_class or "highlight" in row_class or strike_text == "23700.00":
                    try:
                        # Extract Call IV (Col Index 6) and Put IV (Col Index 14)
                        call_iv_text = cells[6].text.strip().replace("%", "")
                        put_iv_text = cells[14].text.strip().replace("%", "")
                        
                        atm_call_iv = float(call_iv_text) if call_iv_text and call_iv_text != "—" else None
                        atm_put_iv = float(put_iv_text) if put_iv_text and put_iv_text != "—" else None
                        break
                    except ValueError:
                        continue
        
        # If specific highlight checking loop misses, take default fallback strike (23700) directly
        if atm_call_iv is None:
            # Static fallback selector for Strike 23700 row Call IV / Put IV if row loop passes
            call_iv_element = driver.find_element(By.XPATH, "//tr[td[contains(text(),'23700')]]/td[7]")
            put_iv_element = driver.find_element(By.XPATH, "//tr[td[contains(text(),'23700')]]/td[15]")
            atm_call_iv = float(call_iv_element.text.strip())
            atm_put_iv = float(put_iv_element.text.strip())

        return atm_call_iv, atm_put_iv
    except Exception as e:
        # Debug error tracker printing to console window
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

# 6. Cycle rerun timing loop 
time.sleep(30)
st.rerun()
