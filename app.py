import streamlit as st
import pandas as pd
import asyncio
import io
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
import os
import subprocess
import sys

# Automatically download Chromium binaries inside the cloud container on initialization
try:
    import playwright
except ImportError:
    pass
else:
    # Trigger the system installation loop if running in production cloud context
    if os.environ.get("STREAMLIT_SERVER_PORT") or os.environ.get("HOME") == "/home/adminuser":
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)

st.set_page_config(page_title="Website Link & Audit Scanner", page_icon="🔍", layout="wide")

async def run_audit_core(urls, progress_bar, status_text, log_area):
    """Core auditing logic optimized to handle internal crawl4ai exceptions cleanly."""
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
                # Execute web automation layer
                result = await crawler.arun(url=url, config=run_config)
                
                if result and result.success:
                    status_code = getattr(result, 'status_code', None)
                    if status_code and status_code >= 400:
                        current_status = f"Broken (HTTP {status_code})"
                    else:
                        # Strip HTML tags via Markdown view to evaluate page state accurately
                        page_text = (result.markdown or "").lower()
                        fail_keywords = ["page not found", "404 error", "sorry, this page does not exist", "status code 404"]
                        
                        if any(keyword in page_text for keyword in fail_keywords):
                            current_status = "Broken / Soft 404"
                        else:
                            current_status = "Active"
                else:
                    error_msg = result.error_message if result else "Unknown Crawler Error"
                    
                    # Intercept inside-the-object failures returned as string text fields
                    if "ERR_NAME_NOT_RESOLVED" in error_msg or "failed on navigating acs-goto" in error_msg.lower():
                        current_status = "Broken (Domain Does Not Exist)"
                    else:
                        current_status = f"Failed: {error_msg[:40]}"
                    
            except RuntimeError as re:
                # Intercept strict Python/Playwright level RuntimeExceptions thrown outside the object context
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

# --- Streamlit UI Layout ---
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
        st.dataframe(df.head(5), use_container_width=True)
        
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
                st.dataframe(df, use_container_width=True)
                
                # Memory stream generator loop
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
