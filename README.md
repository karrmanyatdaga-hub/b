# 📈 Historical Equity & Spot OHLC Data Downloader

A modern web application built with **Streamlit** and **yfinance** that allows users to fetch, inspect, visualize, and download historical Open, High, Low, Close (OHLC), and Volume data for equities, spot market indices, ETFs, and cryptocurrencies.

Supports both **Single Ticker Analysis** and **Batch CSV Upload (with one-click ZIP download)**.

---

## 🚀 Features

### 1. 🎯 Single Ticker Mode
- **Flexible Ticker Inputs**:
  - **US Equities**: `AAPL`, `MSFT`, `TSLA`, `NVDA`
  - **Indian Equities (NSE/BSE)**: `RELIANCE.NS`, `TCS.NS`, `INFY.NS`
  - **Spot Market Indices**: `^NSEI` (Nifty 50), `^BSESN` (Sensex), `^GSPC` (S&P 500)
  - **Commodities & Crypto**: `GC=F` (Gold), `BTC-USD`
- **Dynamic Asset Verification Banner**: Automatically identifies asset full name, exchange, and traded currency.
- **Dark Translucent Metric Cards**: High-contrast glassmorphic metrics (Latest Close / Spot Level, Price Change %, Period High & Low, Trading Days, Total Volume).
- **Interactive Plotly Visualizations**: Candlestick chart with volume bars and line chart toggle.
- **Single-Click CSV Download**: Formatted single-level CSV `{TICKER}_OHLC_{start}_{end}.csv`.

### 2. 📦 Batch CSV Upload Mode (Zipped Output)
- **Upload CSV with `Symbol` Column**: Upload any CSV containing stock scrips (e.g. `RELIANCE`, `TCS`, `INFY`).
- **Automatic Exchange Suffix**: Automatically appends `.NS` (National Stock Exchange of India) or custom suffix.
- **Skip Duplicate Suffix**: Skips appending if the symbol already has an exchange suffix (`.NS`, `.BO`) or starts with `^`.
- **Live Progress Tracking**: Real-time progress bar showing the active stock being fetched.
- **One-Click ZIP Download**: Generates an in-memory `.zip` archive containing:
  - Individual CSV files for each stock (`{SYMBOL}_OHLC_{start}_{end}.csv`).
  - `_BATCH_DOWNLOAD_SUMMARY.csv`: A complete manifest of all symbols, status, trading days, and latest close.

---

## 🛠️ Quick Start

### 1. Activate Virtual Environment
```bash
source venv/bin/activate
```

### 2. Run the Streamlit Application
```bash
streamlit run app.py
```
*(Or directly: `./venv/bin/streamlit run app.py`)*

The web application will open in your browser at:
`http://localhost:8501`

---

## 📄 Batch CSV Format Example

Your uploaded CSV file should have a column named `Symbol` (a sample is included in [`sample_symbols.csv`](file:///Users/shakundaga/Desktop/ltc/sample_symbols.csv)):

```csv
Symbol
RELIANCE
TCS
INFY
HDFCBANK
ICICIBANK
TATAMOTORS
SBIN
```

The application will automatically query `RELIANCE.NS`, `TCS.NS`, etc., and output all historical OHLC CSVs zipped together.
