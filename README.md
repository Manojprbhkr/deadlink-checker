# 🔍 Bulk Website & Soft-404 Auditor

This application uses automated headless browsers to run accurate link audits. It scans spreadsheets of URLs to instantly catch dead links, server timeouts, domain failures, and tricky "soft-404" errors (pages that display a "Not Found" message but falsely return a live success code).

---

## 🚀 How to Run Locally

### 1. Install Dependencies & Web Browsers
Open your terminal and run the following commands to install the required Python libraries and automated browser drivers:
```bash
python -m pip install streamlit pandas openpyxl crawl4ai playwright
python -m playwright install chromium
```

### 2. Generate Sample Data
Run the built-in test generator script to create a sample Excel file (`input_urls.xlsx`) pre-loaded with working links, 404 errors, and dead domains:
```bash
python generate_test_data.py
```

### 3. Launch the App
Start up the interactive web interface:
```bash
streamlit run streamlit_app.py
```
Your web browser will automatically open to `http://localhost:8501`.

---

## 💻 How to Use the App

1. **Upload your Spreadsheet**: Drag and drop your `.xlsx` file into the uploader. Ensure your sheet contains a column named precisely **`URL`**.
2. **Start the Scan**: Click the bright red **"🚀 Start Security Audit"** button.
3. **Monitor Live Logs**: Watch the progress bar and real-time terminal output logs as the headless browser scans each link.
4. **Download Results**: Once complete, click **"💾 Download Audited Spreadsheet"**.

> 💡 **Zero-Disk Mode Active**: To protect server storage, all processed files and results are held securely in volatile system memory (RAM). Nothing is ever written to or saved on the host machine's hard drive.
