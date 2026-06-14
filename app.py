import streamlit as st
import pandas as pd
import asyncio
import io
import os
import subprocess
import sys

# --- STEP 1: DEPLOYMENT PROVISIONING HOOK ---
# We force the Playwright installation loop to run BEFORE crawl4ai is imported.
# This guarantees that the headless browser engine exists on Streamlit Cloud.
def provision_playwright_browsers():
    # Detect if we are on a remote Streamlit Cloud server container
    is_cloud = os.environ.get("STREAMLIT_SERVER_PORT") is not None or os.environ.get("HOME") in ["/home/appuser", "/home/adminuser"]
    
    if is_cloud:
        # Check if the cache folder already has downloaded browser binaries
        playwright_cache = os.path.expanduser("~/.cache/ms-playwright")
        if not os.path.exists(playwright_cache) or len(os.listdir(playwright_cache)) == 0:
            with st.spinner("📦 Provisioning cloud browser engines (First boot only)..."):
                try:
                    # Execute system terminal download loop
                    subprocess.run(
                        [sys.executable, "-m", "playwright", "install", "chromium"], 
                        check=True, 
                        capture_output=True, 
                        text=True
                    )
                except Exception as e:
                    st.error(f"Failed to auto-configure server web browsers: {e}")

# Run the provisioning sequence immediately
provision_playwright_browsers()

# --- STEP 2: CORE FRAMEWORK IMPORTS ---
# Now it is completely safe to import crawl4ai modules
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

# Set up page configurations
st.set_page_config(page_title="Website Link & Audit Scanner", page_icon="🔍", layout="wide")

# --- STEP 3: ASYNC AUDITOR CONTEXT ---
async def run_audit_core(urls, progress_bar, status_text, log_area):
    """Core logic to navigate and check web endpoints without locking the UI thread."""
    browser_config = BrowserConfig(
        headless=True,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_for="body", 
        delay_before_return_html=2.0, 
        page_timeout=30000            
    )

    statuses = []
    log_messages = []

    def update_log(msg):
        log_messages.append(msg)
        log_area.text("\n".join(log_messages[-10:]))

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for index, url in enumerate(urls, 1):
            percent_complete = index / len(urls)
            progress_bar.progress(percent_complete)
            status_text.text(f"⏳ Processing URL {index} of {len(urls)}...")
            
            update_log(f"🔍 Scanning: {url[:60]}")
            current_status = "Failed: Unspecified Error"
            
            try:
                result = await crawler.arun(url=url, config=run_config)
                
                if result and result.success:
                    status_code = getattr(result, 'status_code', None)
                    if status_code and status_code >= 400:
                        current_status = f"Broken (HTTP {status_code})"
                    else:
                        # Convert to markdown layout to eliminate false soft-404 code strings
                        page_text = (result.markdown or "").lower()
                        fail_keywords = ["page not found", "404 error", "sorry, this page does not exist", "status code 404"]
                        
                        if any(keyword in page_text for keyword in fail_keywords):
                            current_status = "Broken / Soft 404"
                        else:
                            current_status = "Active"
                else:
                    error_msg = result.error_message if result else "Unknown Crawler Error"
                    if "ERR_NAME_NOT_RESOLVED" in error_msg or "failed on navigating" in error_msg.lower():
                        current_status = "Broken (Domain Does Not Exist)"
                    else:
                        current_status = f"Failed: {error_msg[:40]}"
                    
            except RuntimeError as re:
                err_str = str(re)
                if "ERR_NAME_NOT_RESOLVED" in err_str or "dns" in err_str.lower() or "acs-goto" in err_str.lower():
                    current_status = "Broken (Domain Does Not Exist)"
                elif "timeout" in err_str.lower():
                    current_status = "Failed: Connection Timeout"
                else:
                    current_status = f"Failed: Network Error"
            except Exception as e:
                current_status = f"Exception: {type(e).__name__}"
            
            finally:
                statuses.append(current_status)
                update_log(f"➔ Status: {current_status}")
                
    return statuses

# --- STEP 4: USER INTERFACE LAYOUT ---
st.title("🔍 Bulk Website & Soft-404 Auditor")
st.markdown("Upload a spreadsheet of URLs to check their status using browser automation.")

with st.sidebar:
    st.header("Setup Instructions")
    st.markdown("""
    1. Upload an Excel file containing a **'URL'** column.
    2. Click **'Start Security Audit'**.
    3. Monitor execution logs in real time.
    4. Download the final report spreadsheet.
    """)
    st.info("💡 Zero-Disk Mode Active: Results are held in RAM and never written to the server's drive.")

uploaded_file = st.file_uploader("Choose an Excel file (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file, engine='openpyxl')
        df.columns = df.columns.str.strip()
        
        st.success("📊 File uploaded successfully!")
        st.dataframe(df.head(5), width="stretch")
        
        if 'URL' not in df.columns:
            st.error("❌ Critical Error: The uploaded sheet must contain a column precisely named **'URL'**.")
        else:
            urls_list = df['URL'].dropna().astype(str).str.strip().tolist()
            st.metric(label="Total URLs Detected", value=len(urls_list))
            
            if st.button("🚀 Start Security Audit", type="primary"):
                st.subheader("Progress & Diagnostics")
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                
                st.markdown("**Live Crawler Log Output:**")
                log_area = st.empty()
                
                with st.spinner("Executing background tasks..."):
                    audit_results = asyncio.run(run_audit_core(urls_list, progress_bar, status_text, log_area))
                
                df['Audit Status'] = audit_results
                
                status_text.text("✅ Audit Complete!")
                st.subheader("Results Preview")
                st.dataframe(df, width="stretch")
                
                # --- Zero-Disk Output Buffer ---
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button(
                    label="💾 Download Audited Spreadsheet",
                    data=buffer.getvalue(),
                    file_name="audit_results_completed.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
    except Exception as e:
        st.error(f"Failed to read the excel file format. Details: {e}")
