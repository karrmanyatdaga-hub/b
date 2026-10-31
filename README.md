# 📈 Historical Equity & Spot OHLC Data Downloader & MA Screener

A modern web application built with **Streamlit** and **yfinance** that allows users to fetch, inspect, visualize, screen, and download historical Open, High, Low, Close (OHLC), and Volume data for equities, spot market indices, ETFs, and cryptocurrencies.

Supports both **Single Ticker Analysis** and **Bulk Upload with Moving Average Screener & ZIP Downloads**.

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

### 2. 📦 Bulk Upload & Moving Average Screener
- **Upload CSV with `Symbol` Column**: Upload any CSV containing stock scrips (e.g. `RELIANCE`, `TCS`, `INFY` without `.NS`).
- **Automatic Exchange Suffix**: Automatically appends `.NS` (National Stock Exchange of India) or custom suffix.
- **Custom Moving Average Screener**:
  - **MA Type**: Simple Moving Average (`SMA`) or Exponential Moving Average (`EMA`).
  - **MA Period**: User-configurable window (e.g. 20, 50, 100, 200 days).
  - **Condition Operators**: Greater than (`>`), Less than (`<`), or Equal to / Near (`≈ / ==` with configurable tolerance band).
  - **Comparison Modes**:
    - `Close Price vs Moving Average` (e.g. Latest Close > 50 SMA).
    - `Moving Average vs Target Value` (e.g. 50 SMA > 500.00).
- **Server-Side Data Persistence & Fast Testing**:
  - Downloaded CSVs are stored directly on the server disk (`./saved_data/`).
  - Instant testing mode: screen server-cached data in seconds without re-fetching from Yahoo Finance.
  - Sidebar cache counter and cache clearing button.
- **Interactive Visual Inspector**: Inspect Candlestick charts with the Moving Average overlay for any filtered stock.
- **Multi-Format Exports**:
  - Download filtered stocks list (CSV).
  - Download matching stocks historical OHLC data (.ZIP).
  - Download all processed stocks master archive (.ZIP).

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
