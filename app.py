import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import warnings
import inspect
import zipfile
import io
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Server data storage directory for testing and screener cache
SAVED_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_data")
os.makedirs(SAVED_DATA_DIR, exist_ok=True)

# Suppress minor deprecation warnings from internal dependencies
warnings.filterwarnings("ignore")

def _get_stretch_kw():
    """Returns width='stretch' if supported by current Streamlit, else use_container_width=True."""
    if "width" in inspect.signature(st.dataframe).parameters:
        return {"width": "stretch"}
    return {"use_container_width": True}

STRETCH = _get_stretch_kw()

# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="Historical OHLC & Spot Downloader | yfinance",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for polished styling, dark translucent metric cards, and readability
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
        color: #F8FAFC;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #94A3B8;
        margin-bottom: 1.5rem;
    }
    
    /* Dark translucent metric cards with high contrast bright text */
    [data-testid="stMetric"] {
        background: rgba(15, 23, 42, 0.78) !important; /* dark slate translucent */
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.14) !important;
        border-radius: 12px !important;
        padding: 0.85rem 1rem !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3) !important;
        min-width: 0 !important;
    }
    [data-testid="stMetricValue"], [data-testid="stMetricValue"] * {
        font-size: 1.35rem !important;
        color: #FFFFFF !important; /* solid white */
        font-weight: 700 !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        word-break: break-word !important;
        line-height: 1.25 !important;
    }
    [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {
        font-size: 0.8rem !important;
        color: #94A3B8 !important; /* light slate gray for clear contrast */
        font-weight: 600 !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
    }
    [data-testid="stMetricDelta"], [data-testid="stMetricDelta"] * {
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
    }
    
    /* Asset identification banner */
    .asset-banner {
        background: rgba(15, 23, 42, 0.75);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.14);
        border-radius: 10px;
        padding: 0.85rem 1.25rem;
        margin-bottom: 1.25rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 0.75rem;
    }
    .asset-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #FFFFFF;
        margin-right: 0.5rem;
    }
    .asset-tag {
        font-size: 0.85rem;
        font-weight: 600;
        color: #38BDF8;
        background: rgba(56, 189, 248, 0.16);
        padding: 0.2rem 0.55rem;
        border-radius: 6px;
        border: 1px solid rgba(56, 189, 248, 0.35);
    }
    .asset-badge {
        font-size: 0.8rem;
        font-weight: 500;
        color: #CBD5E1;
        background: rgba(255, 255, 255, 0.08);
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Screener rule banner */
    .rule-banner {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(56, 189, 248, 0.35);
        border-radius: 8px;
        padding: 0.75rem 1.1rem;
        margin: 0.85rem 0 0.5rem 0;
        color: #38BDF8;
        font-weight: 600;
        font-size: 0.95rem;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# Data Fetching Logic (Cached)
# ---------------------------------------------------------
# Pre-mapped common ticker descriptions for instant lookup without network latency
POPULAR_TICKER_NAMES = {
    # Spot Indices
    "^NSEI": "NIFTY 50 (National Stock Exchange of India)",
    "^BSESN": "BSE SENSEX (Bombay Stock Exchange)",
    "^GSPC": "S&P 500 (US Broad Market)",
    "^IXIC": "NASDAQ Composite",
    "^DJI": "Dow Jones Industrial Average",
    "^FTSE": "FTSE 100 (UK)",
    "^N225": "Nikkei 225 (Japan)",
    # US Equities
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "GOOGL": "Alphabet Inc. (Google)",
    "AMZN": "Amazon.com Inc.",
    "TSLA": "Tesla, Inc.",
    "META": "Meta Platforms Inc.",
    "SPY": "SPDR S&P 500 ETF Trust",
    "QQQ": "Invesco QQQ Trust",
    # Indian Equities
    "RELIANCE.NS": "Reliance Industries Ltd",
    "TCS.NS": "Tata Consultancy Services Ltd",
    "INFY.NS": "Infosys Ltd",
    "HDFCBANK.NS": "HDFC Bank Ltd",
    "ICICIBANK.NS": "ICICI Bank Ltd",
    "SBIN.NS": "State Bank of India",
    # Crypto & Commodities
    "BTC-USD": "Bitcoin (USD)",
    "ETH-USD": "Ethereum (USD)",
    "GC=F": "Gold Futures",
    "CL=F": "Crude Oil Futures"
}

@st.cache_data(ttl=3600, show_spinner=False)
def get_ticker_meta(symbol: str):
    """
    Detects whether the asset is a spot index or equity,
    and returns its human-readable name, currency code, display prefix, and appropriate labels.
    """
    sym = symbol.strip().upper()
    is_index = sym.startswith("^")
    currency = ""
    exchange = ""
    quote_type = "INDEX" if is_index else "EQUITY"
    name = POPULAR_TICKER_NAMES.get(sym, "")
    
    try:
        t = yf.Ticker(sym)
        fi = t.fast_info
        currency = getattr(fi, "currency", "") or ""
        exchange = getattr(fi, "exchange", "") or ""
        qt = getattr(fi, "quote_type", None)
        if qt:
            quote_type = str(qt).upper()
        if quote_type == "INDEX":
            is_index = True
            
        if not name:
            info = t.info
            name = info.get("shortName") or info.get("longName") or sym
            if not exchange:
                exchange = info.get("exchange", "")
    except Exception:
        if not name:
            name = sym
        
    CURRENCY_SYMBOLS = {
        "USD": "$",
        "INR": "₹",
        "EUR": "€",
        "GBP": "£",
        "GBp": "£",
        "JPY": "¥",
        "CAD": "C$",
        "AUD": "A$",
        "CHF": "CHF "
    }
    
    if is_index:
        symbol_prefix = ""
        unit_suffix = " pts"
        asset_label = "Spot Level"
        axis_title = f"{sym} Spot Value (Points)"
    else:
        symbol_prefix = CURRENCY_SYMBOLS.get(currency.upper(), f"{currency} " if currency else "")
        unit_suffix = f" {currency}" if (currency and symbol_prefix == "") else ""
        asset_label = "Closing Price"
        axis_title = f"Price ({currency})" if currency else "Price"
        
    return {
        "name": name or sym,
        "exchange": exchange,
        "is_index": is_index,
        "currency": currency,
        "symbol_prefix": symbol_prefix,
        "unit_suffix": unit_suffix,
        "asset_label": asset_label,
        "axis_title": axis_title,
        "quote_type": quote_type
    }


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_ohlc(ticker: str, start_date: datetime.date, end_date: datetime.date, auto_adjust: bool = False):
    """
    Fetches OHLC equity data from yfinance and cleans up column structures.
    """
    ticker_clean = ticker.strip().upper()
    
    # We add 1 day to end_date because yfinance end date is non-inclusive
    query_end = end_date + datetime.timedelta(days=1)
    
    # Fetch historical data safely
    try:
        df = yf.download(
            tickers=ticker_clean,
            start=start_date.strftime("%Y-%m-%d"),
            end=query_end.strftime("%Y-%m-%d"),
            auto_adjust=auto_adjust,
            multi_level_index=False,
            progress=False
        )
    except Exception:
        return None
    
    if df is None or df.empty:
        return None
    
    # Reset index so 'Date' is a column
    df = df.reset_index()
    
    # Ensure Date column is cleanly formatted string (YYYY-MM-DD)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.strftime("%Y-%m-%d")
    
    # Flatten MultiIndex columns if present in any older yfinance versions
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

    # Reorder standard OHLC columns
    preferred_order = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]
    available_cols = [col for col in preferred_order if col in df.columns]
    extra_cols = [col for col in df.columns if col not in preferred_order]
    
    final_df = df[available_cols + extra_cols].copy()
    return final_df


def compute_moving_average(df: pd.DataFrame, period: int, ma_type: str = "SMA") -> pd.Series:
    """
    Computes Simple Moving Average (SMA) or Exponential Moving Average (EMA)
    on the 'Close' column of the given dataframe.
    """
    if df is None or "Close" not in df.columns or len(df) == 0:
        return pd.Series(dtype=float)
    
    if str(ma_type).upper() == "EMA":
        return df["Close"].ewm(span=period, adjust=False).mean()
    else:
        return df["Close"].rolling(window=period).mean()


def evaluate_screener_condition(
    latest_close: float,
    latest_ma: float,
    comparison_mode: str,
    operator: str,
    target_value: float = 0.0,
    tolerance_pct: float = 1.0
):
    """
    Evaluates whether the stock satisfies the Moving Average condition.
    Returns: (is_match: bool, diff_pct: float, diff_pts: float, status_msg: str)
    """
    if pd.isna(latest_ma) or pd.isna(latest_close):
        return False, 0.0, 0.0, "Insufficient Data"
    
    if "Target Value" in comparison_mode or "Value" in comparison_mode:
        # Compare latest_ma against user input target_value
        diff_pts = latest_ma - target_value
        diff_pct = (diff_pts / target_value * 100.0) if target_value != 0 else 0.0
        
        if ">" in operator:
            match = latest_ma > target_value
        elif "<" in operator:
            match = latest_ma < target_value
        else:  # "==" or "≈"
            tol_val = abs(target_value * (tolerance_pct / 100.0))
            match = abs(diff_pts) <= tol_val
    else:
        # Compare latest_close against latest_ma
        diff_pts = latest_close - latest_ma
        diff_pct = (diff_pts / latest_ma * 100.0) if latest_ma != 0 else 0.0
        
        if ">" in operator:
            match = latest_close > latest_ma
        elif "<" in operator:
            match = latest_close < latest_ma
        else:  # "==" or "≈"
            tol_val = abs(latest_ma * (tolerance_pct / 100.0))
            match = abs(diff_pts) <= tol_val
            
    status_msg = "Passed" if match else "Failed"
    return match, diff_pct, diff_pts, status_msg


# ---------------------------------------------------------
# Sidebar Inputs
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("### 🔀 Workflow Mode")
    app_mode = st.radio(
        "Choose Mode:",
        ["🎯 Single Ticker", "📦 Batch Upload & MA Screener"],
        index=0,
        help="Single Ticker: Interactive chart & individual CSV.\nBatch Upload & MA Screener: Upload CSV with 'Symbol' column, screen by Moving Average, and download ZIP/CSVs."
    )
    st.markdown("---")

    if app_mode == "🎯 Single Ticker":
        st.header("⚙️ Query Parameters")
        
        # Initialize session state for ticker if not already present
        if "ticker_input_val" not in st.session_state:
            st.session_state["ticker_input_val"] = "AAPL"
            
        def set_ticker(symbol):
            st.session_state["ticker_input_val"] = symbol

        ticker_input = st.text_input(
            "Enter Ticker Symbol",
            key="ticker_input_val",
            placeholder="e.g. AAPL, ^NSEI, RELIANCE.NS",
            help="Type any symbol tracked on Yahoo Finance. For spot indices, prefix with '^'. For Indian stocks, suffix with '.NS'."
        ).strip().upper()

        st.markdown("""
        <div style="font-size: 0.78rem; color: #94A3B8; margin-top: -0.4rem; margin-bottom: 0.8rem;">
        💡 <b>Tip:</b> Spot Indices start with <code>^</code> (e.g. <code>^NSEI</code>, <code>^GSPC</code>). Indian NSE stocks use <code>.NS</code> (e.g. <code>RELIANCE.NS</code>).
        </div>
        """, unsafe_allow_html=True)

        # Quick pick popular tickers in 2 clean columns
        st.caption("⚡ Popular Tickers (Quick Picks):")
        col_q1, col_q2 = st.columns(2)
        with col_q1:
            st.button("🍎 AAPL (Apple)", on_click=set_ticker, args=("AAPL",), **STRETCH)
            st.button("🇮🇳 ^NSEI (Nifty 50)", on_click=set_ticker, args=("^NSEI",), **STRETCH)
            st.button("🚗 TSLA (Tesla)", on_click=set_ticker, args=("TSLA",), **STRETCH)
        with col_q2:
            st.button("🇺🇸 ^GSPC (S&P 500)", on_click=set_ticker, args=("^GSPC",), **STRETCH)
            st.button("💻 MSFT (Microsoft)", on_click=set_ticker, args=("MSFT",), **STRETCH)
            st.button("🇮🇳 RELIANCE.NS", on_click=set_ticker, args=("RELIANCE.NS",), **STRETCH)

        # Clear and helpful Ticker Guide Expander
        with st.expander("🔍 Symbol Directory & Search Guide", expanded=False):
            st.markdown("""
            **Spot Indices (start with `^`):**
            - `^NSEI` : NIFTY 50 (India)
            - `^BSESN` : BSE Sensex (India)
            - `^GSPC` : S&P 500 (US)
            - `^IXIC` : NASDAQ Composite
            - `^DJI` : Dow Jones
            
            **Indian Equities (add `.NS` or `.BO`):**
            - `RELIANCE.NS` : Reliance Industries
            - `TCS.NS` : Tata Consultancy
            - `INFY.NS` : Infosys
            - `HDFCBANK.NS` : HDFC Bank
            
            **US Equities & ETFs:**
            - `AAPL`, `MSFT`, `NVDA`, `GOOGL`, `AMZN`, `META`, `TSLA`
            - `SPY` (S&P 500 ETF), `QQQ` (Nasdaq ETF)
            
            **Crypto & Commodities:**
            - `BTC-USD` (Bitcoin), `ETH-USD` (Ethereum)
            - `GC=F` (Gold Futures), `CL=F` (Crude Oil)
            """)
        st.markdown("---")
    else:
        # Batch Mode Configuration
        st.subheader("⚙️ Batch Suffix Settings")
        suffix_option = st.selectbox(
            "Default Exchange Suffix",
            [".NS (NSE India)", ".BO (BSE India)", "None (Keep as-is)", "Custom Suffix"],
            index=0,
            help="Symbols without an exchange suffix will automatically have this appended."
        )
        if suffix_option == ".NS (NSE India)":
            batch_suffix = ".NS"
        elif suffix_option == ".BO (BSE India)":
            batch_suffix = ".BO"
        elif suffix_option == "None (Keep as-is)":
            batch_suffix = ""
        else:
            batch_suffix = st.text_input("Enter custom suffix", value=".NS").strip()

        auto_skip_existing = st.checkbox(
            "Skip if symbol already has suffix or is an index (^)",
            value=True,
            help="Prevents duplicate suffixes like RELIANCE.NS.NS"
        )
        st.markdown("---")
        
        # Server Storage Cache Info
        saved_files_count = len([f for f in os.listdir(SAVED_DATA_DIR) if f.endswith(".csv")]) if os.path.exists(SAVED_DATA_DIR) else 0
        st.subheader("💾 Server Storage")
        st.caption(f"📁 **{saved_files_count}** stock CSVs stored on server.")
        if saved_files_count > 0:
            if st.button("🗑️ Clear Server Cache", help="Deletes saved CSV files on the server"):
                for f in os.listdir(SAVED_DATA_DIR):
                    if f.endswith(".csv"):
                        try:
                            os.remove(os.path.join(SAVED_DATA_DIR, f))
                        except Exception:
                            pass
                st.session_state.pop("batch_zip_data", None)
                st.session_state.pop("batch_manifest", None)
                st.session_state.pop("screener_matched", None)
                st.session_state.pop("screener_all", None)
                st.session_state.pop("screener_meta", None)
                st.rerun()
        st.markdown("---")
        
    # Date Range Pre-sets (Common to both modes)
    st.subheader("📅 Date Range")
    
    today = datetime.date.today()
    default_start = today - datetime.timedelta(days=365)
    
    date_preset = st.selectbox(
        "Presets",
        ["Custom", "1 Month", "3 Months", "6 Months", "Year to Date (YTD)", "1 Year", "5 Years"],
        index=5
    )
    
    if date_preset == "1 Month":
        calc_start = today - datetime.timedelta(days=30)
    elif date_preset == "3 Months":
        calc_start = today - datetime.timedelta(days=90)
    elif date_preset == "6 Months":
        calc_start = today - datetime.timedelta(days=180)
    elif date_preset == "Year to Date (YTD)":
        calc_start = datetime.date(today.year, 1, 1)
    elif date_preset == "1 Year":
        calc_start = today - datetime.timedelta(days=365)
    elif date_preset == "5 Years":
        calc_start = today - datetime.timedelta(days=365 * 5)
    else:
        calc_start = default_start

    start_date = st.date_input("Start Date", value=calc_start)
    end_date = st.date_input("End Date", value=today)

    st.markdown("---")
    
    # Data & Export Preferences
    with st.expander("🛠️ Advanced Options", expanded=False):
        auto_adjust = st.checkbox(
            "Auto-adjust prices for splits/dividends",
            value=False,
            help="If checked, Open, High, Low, Close are split- and dividend-adjusted automatically."
        )
        decimal_places = st.selectbox(
            "Price Decimal Places in CSV",
            options=["Raw (Unrounded)", "2 Decimals", "4 Decimals"],
            index=1
        )

    if app_mode == "🎯 Single Ticker":
        fetch_button = st.button("🚀 Fetch OHLC Data", type="primary", **STRETCH)


# ---------------------------------------------------------
# Main Application Content
# ---------------------------------------------------------
if app_mode == "🎯 Single Ticker":
    st.markdown('<div class="main-title">📈 Historical OHLC & Spot Data Downloader</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Download historical Open, High, Low, Close, and Volume data for equities and spot indices powered by Yahoo Finance.</div>', unsafe_allow_html=True)

    # Validation checks
    if not ticker_input:
        st.info("👈 Please enter a valid ticker symbol in the sidebar to get started.")
        st.stop()

    if start_date > end_date:
        st.error(f"❌ **Invalid Date Range**: Start date ({start_date}) cannot be after End date ({end_date}).")
        st.stop()

    # Fetch Data
    with st.spinner(f"Fetching historical OHLC data for **{ticker_input}** from {start_date} to {end_date}..."):
        raw_df = fetch_stock_ohlc(ticker_input, start_date, end_date, auto_adjust=auto_adjust)

    if raw_df is None or raw_df.empty:
        st.warning(f"⚠️ No historical data found for **{ticker_input}** between **{start_date}** and **{end_date}**.")
        st.markdown("""
        **Possible causes:**
        - The ticker symbol may be incorrect, delisted, or not tracked on Yahoo Finance.
        - Non-US exchanges require a suffix (e.g., `.NS` for NSE India, `.L` for London, `.TO` for Toronto).
        - Markets may have been closed during the requested window (e.g., a single weekend or holiday).
        """)
        st.stop()
    else:
        # Work on a copy for formatting & calculations
        df = raw_df.copy()

        # Apply Decimal Formatting for CSV export if chosen
        price_cols = [c for c in ["Open", "High", "Low", "Close", "Adj Close"] if c in df.columns]
        export_df = df.copy()

        if decimal_places == "2 Decimals":
            for col in price_cols:
                export_df[col] = export_df[col].round(2)
        elif decimal_places == "4 Decimals":
            for col in price_cols:
                export_df[col] = export_df[col].round(4)

        # Generate CSV data
        csv_bytes = export_df.to_csv(index=False).encode("utf-8")
        file_name = f"{ticker_input}_OHLC_{start_date}_to_{end_date}.csv"

        # ---------------------------------------------------------
        # Asset Verification Banner & Summary Metrics Header
        # ---------------------------------------------------------
        meta = get_ticker_meta(ticker_input)

        # Display Verified Asset Banner
        currency_badge = f'<span class="asset-badge">Currency: {meta["currency"]}</span>' if meta.get("currency") else ''
        exchange_badge = f'<span class="asset-badge">Exchange: {meta["exchange"]}</span>' if meta.get("exchange") else ''
        st.markdown(f"""
        <div class="asset-banner">
            <div>
                <span class="asset-title">{meta['name']}</span>
                <span class="asset-tag">{ticker_input}</span>
            </div>
            <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                <span class="asset-badge">{meta['quote_type']}</span>
                {currency_badge}
                {exchange_badge}
            </div>
        </div>
        """, unsafe_allow_html=True)

        prefix = meta["symbol_prefix"]
        unit_suffix = meta["unit_suffix"]
        is_index = meta["is_index"]

        label_close = "Latest Spot (pts)" if is_index else (f"Latest Close ({meta['currency']})" if meta["currency"] else "Latest Close")
        label_high = "Period High (pts)" if is_index else "Period High"
        label_low = "Period Low (pts)" if is_index else "Period Low"
        chart_title_part = "Spot Level" if is_index else "Price"

        num_records = len(df)
        latest_row = df.iloc[-1]
        first_row = df.iloc[0]

        latest_close = latest_row.get("Close", 0.0)
        first_open = first_row.get("Open", 0.0)
        price_change = latest_close - first_open
        pct_change = (price_change / first_open * 100) if first_open else 0.0

        period_high = df["High"].max() if "High" in df.columns else 0.0
        period_low = df["Low"].min() if "Low" in df.columns else 0.0
        total_volume = df["Volume"].sum() if "Volume" in df.columns else 0

        delta_text = f"{price_change:+,.2f} ({pct_change:+.2f}%)"

        # Use responsive column widths giving more room to the delta column
        m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns([1.3, 1.0, 1.0, 0.85, 0.85])
        with m_col1:
            st.metric(label_close, f"{prefix}{latest_close:,.2f}", delta_text)
        with m_col2:
            st.metric(label_high, f"{prefix}{period_high:,.2f}")
        with m_col3:
            st.metric(label_low, f"{prefix}{period_low:,.2f}")
        with m_col4:
            st.metric("Trading Days", f"{num_records:,}")
        with m_col5:
            st.metric("Total Volume", f"{total_volume:,.0f}")

        st.markdown("---")

        # ---------------------------------------------------------
        # Download Action Bar
        # ---------------------------------------------------------
        d_col1, d_col2 = st.columns([2, 1])
        with d_col1:
            st.download_button(
                label=f"📥 Download {ticker_input} OHLC CSV ({num_records} rows)",
                data=csv_bytes,
                file_name=file_name,
                mime="text/csv",
                type="primary",
                **STRETCH
            )
        with d_col2:
            st.caption(f"**Target file:** `{file_name}`  \n**Size:** ~{len(csv_bytes) / 1024:.1f} KB | **Columns:** {', '.join(export_df.columns)}")

        st.markdown("<br>", unsafe_allow_html=True)

        # ---------------------------------------------------------
        # Interactive Visualizations
        # ---------------------------------------------------------
        tab_chart, tab_data, tab_summary = st.tabs(["📊 Interactive Chart", "📋 Data Table", "📐 Statistics"])

        with tab_chart:
            chart_type = st.radio("Chart Type:", [f"Candlestick (OHLC {chart_title_part} + Volume)", f"Line Chart ({chart_title_part})"], horizontal=True)
            
            if "Candlestick" in chart_type:
                fig = make_subplots(
                    rows=2, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.04,
                    row_heights=[0.7, 0.3],
                    subplot_titles=(f"{ticker_input} OHLC {chart_title_part}", "Volume")
                )
                
                # Candlestick
                fig.add_trace(
                    go.Candlestick(
                        x=df["Date"],
                        open=df["Open"],
                        high=df["High"],
                        low=df["Low"],
                        close=df["Close"],
                        name="OHLC",
                        increasing_line_color="#10B981",
                        decreasing_line_color="#EF4444"
                    ),
                    row=1, col=1
                )
                
                # Volume
                if "Volume" in df.columns:
                    colors = ["#10B981" if c >= o else "#EF4444" for c, o in zip(df["Close"], df["Open"])]
                    fig.add_trace(
                        go.Bar(
                            x=df["Date"],
                            y=df["Volume"],
                            name="Volume",
                            marker_color=colors,
                            opacity=0.6
                        ),
                        row=2, col=1
                    )
                    
                fig.update_layout(
                    xaxis_rangeslider_visible=False,
                    height=580,
                    margin=dict(l=20, r=20, t=40, b=20),
                    template="plotly_white",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, **STRETCH)
                
            else:
                fig_line = go.Figure()
                fig_line.add_trace(
                    go.Scatter(
                        x=df["Date"],
                        y=df["Close"],
                        mode="lines",
                        name=chart_title_part,
                        line=dict(color="#2563EB", width=2)
                    )
                )
                if "Adj Close" in df.columns and not auto_adjust:
                    fig_line.add_trace(
                        go.Scatter(
                            x=df["Date"],
                            y=df["Adj Close"],
                            mode="lines",
                            name=f"Adj {chart_title_part}",
                            line=dict(color="#F59E0B", width=1.5, dash="dash")
                        )
                    )
                fig_line.update_layout(
                    title=f"{ticker_input} Historical {chart_title_part}",
                    xaxis_title="Date",
                    yaxis_title=meta["axis_title"],
                    height=500,
                    template="plotly_white"
                )
                st.plotly_chart(fig_line, **STRETCH)

        with tab_data:
            st.subheader("Data Preview")
            st.dataframe(
                export_df,
                hide_index=True,
                **STRETCH
            )

        with tab_summary:
            st.subheader("Summary Statistics")
            st.dataframe(
                export_df.describe().T.style.format("{:,.2f}"),
                **STRETCH
            )

else:
    # ---------------------------------------------------------
    # Batch CSV Upload & Moving Average Screener Mode
    # ---------------------------------------------------------
    st.markdown('<div class="main-title">📦 Bulk Upload & Moving Average Screener</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sub-title">Upload a CSV of stock symbols (without <code>.NS</code>), configure your custom Moving Average rules '
        f'(SMA/EMA, &gt;, &lt;, or &#8776; user input value), filter stocks automatically, download all CSVs in a ZIP, '
        f'and save data directly on the server for rapid screener testing.</div>',
        unsafe_allow_html=True
    )

    if start_date > end_date:
        st.error(f"❌ **Invalid Date Range**: Start date ({start_date}) cannot be after End date ({end_date}).")
        st.stop()

    # Step 1: Moving Average Screener Configuration Form
    with st.container(border=True):
        st.markdown("### 🎯 Moving Average Screener Setup")
        st.caption("Define the Moving Average condition below. Stocks meeting your condition will be filtered and listed.")
        
        cfg_col1, cfg_col2, cfg_col3 = st.columns(3)
        with cfg_col1:
            ma_type = st.selectbox(
                "Moving Average Type",
                ["SMA (Simple Moving Average)", "EMA (Exponential Moving Average)"],
                index=0,
                help="SMA treats all days equally. EMA assigns higher weight to recent prices."
            )
            ma_type_short = "SMA" if "SMA" in ma_type else "EMA"

        with cfg_col2:
            ma_period = st.number_input(
                "MA Period (Days / Candles)",
                min_value=2,
                max_value=500,
                value=50,
                step=5,
                help="Period length for the moving average (e.g. 20, 50, 100, 200)."
            )

        with cfg_col3:
            comparison_mode = st.selectbox(
                "Comparison Mode",
                [
                    "Close Price vs Moving Average",
                    "Moving Average vs Target Value"
                ],
                index=0,
                help="Choose whether to compare the Stock's Latest Close against its MA, or compare the MA value against a specific numerical benchmark."
            )

        cond_col1, cond_col2 = st.columns(2)
        with cond_col1:
            operator_choice = st.selectbox(
                "Condition Operator",
                [
                    "Greater than (>)",
                    "Less than (<)",
                    "Equal to / Near (≈ / ==)"
                ],
                index=0,
                help="Condition to test against the target."
            )

        with cond_col2:
            if comparison_mode == "Moving Average vs Target Value":
                target_ma_val = st.number_input(
                    f"Target Value for {ma_type_short}({ma_period})",
                    min_value=0.0,
                    value=500.0,
                    step=25.0,
                    format="%.2f",
                    help=f"The benchmark value to compare {ma_type_short}({ma_period}) with."
                )
            else:
                target_ma_val = 0.0
                st.markdown(
                    f"<div style='margin-top: 1.8rem; font-size: 0.9rem; color: #94A3B8;'>"
                    f"Testing: <b>Latest Close Price</b> against <b>{ma_type_short}({ma_period})</b>"
                    f"</div>",
                    unsafe_allow_html=True
                )

        if "Equal to" in operator_choice or "≈" in operator_choice:
            tol_col1, tol_col2 = st.columns([2, 1])
            with tol_col1:
                tolerance_pct = st.slider(
                    "Equality Tolerance Band (± %)",
                    min_value=0.0,
                    max_value=10.0,
                    value=1.5,
                    step=0.1,
                    format="±%.1f%%",
                    help="Matches if value is within ±X% of target (0% = exact equality)."
                )
            with tol_col2:
                st.caption(f"Matches if within **±{tolerance_pct}%** of target value.")
        else:
            tolerance_pct = 1.0

        # Formulate active rule text
        op_sym = ">" if ">" in operator_choice else ("<" if "<" in operator_choice else "≈")
        tol_str = f" (±{tolerance_pct}%)" if op_sym == "≈" else ""
        if comparison_mode == "Moving Average vs Target Value":
            rule_text = f"Filter stocks where {ma_type_short}({ma_period}) {op_sym} {target_ma_val:,.2f}{tol_str}"
        else:
            rule_text = f"Filter stocks where Latest Close {op_sym} {ma_type_short}({ma_period}){tol_str}"

        st.markdown(f'<div class="rule-banner">⚡ <b>Active Screener Rule:</b> {rule_text}</div>', unsafe_allow_html=True)

    # Step 2: Server-Side Testing Cache Panel
    server_saved_csvs = [f for f in os.listdir(SAVED_DATA_DIR) if f.endswith(".csv")] if os.path.exists(SAVED_DATA_DIR) else []
    server_cached_count = len(server_saved_csvs)

    test_server_btn = False
    if server_cached_count > 0:
        with st.container(border=True):
            st.markdown(f"#### 🧪 Server Storage Cache & Fast Screener Testing ({server_cached_count} Stocks)")
            st.markdown(
                f"Historical data for **{server_cached_count} stocks** is already saved on the server disk in `saved_data/`. "
                f"You can test your Moving Average rules on these cached files instantly without re-downloading from Yahoo Finance!"
            )
            test_server_btn = st.button(
                f"⚡ Run Screener on Server Cached Stocks ({server_cached_count} Scrips)",
                type="secondary",
                **STRETCH
            )

    # Step 3: Instructions & CSV Upload
    with st.expander("ℹ️ Instructions & Download Sample Template", expanded=False):
        st.markdown(f"""
        **How Bulk Screener Works:**
        1. Upload a CSV file containing a column named **`Symbol`** (or `Ticker` / `Scrip`).
        2. Stock symbols do **not** need `.NS` at the end (e.g. `RELIANCE`, `TCS`, `INFY`, `HDFCBANK`).
        3. The app automatically appends **`{batch_suffix}`** to each symbol before querying Yahoo Finance.
        4. When processed:
           - All downloaded CSVs are **saved directly on the server disk (`./saved_data/`)** for screener testing.
           - Stocks satisfying the **Moving Average Rule** are filtered and displayed in an interactive table.
           - Download the filtered stocks list as a CSV, matching stocks as a ZIP, or all stock CSVs in a single master ZIP.
        """)
        sample_csv = "Symbol\nRELIANCE\nTCS\nINFY\nHDFCBANK\nICICIBANK\nTATAMOTORS\nSBIN\n"
        st.download_button(
            label="📄 Download Sample CSV Template",
            data=sample_csv,
            file_name="sample_symbols.csv",
            mime="text/csv"
        )

    uploaded_file = st.file_uploader(
        "Upload CSV file containing stock symbols:",
        type=["csv"],
        help="Upload a CSV with a column named 'Symbol' containing scrip names."
    )

    run_batch = False
    unique_symbols = []

    if uploaded_file is not None:
        try:
            input_df = pd.read_csv(uploaded_file)
        except Exception as e:
            st.error(f"❌ Error reading CSV file: {e}")
            st.stop()

        if input_df.empty:
            st.warning("⚠️ The uploaded CSV file is empty.")
            st.stop()

        symbol_col = next((c for c in input_df.columns if str(c).strip().lower() in ["symbol", "ticker", "scrip", "symbol_name"]), None)
        if not symbol_col:
            st.info("💡 Could not automatically find a column named 'Symbol'. Please select the column from your file:")
            symbol_col = st.selectbox("Select Symbol Column:", input_df.columns)

        raw_symbols = [str(s).strip() for s in input_df[symbol_col].dropna() if str(s).strip()]
        unique_symbols = list(dict.fromkeys(raw_symbols))

        if not unique_symbols:
            st.warning("⚠️ No valid symbols found in the selected column.")
            st.stop()

        # Preview transformed symbols
        preview_data = []
        for s in unique_symbols[:5]:
            if auto_skip_existing and (s.endswith(".NS") or s.endswith(".BO") or s.startswith("^")):
                q = s.upper()
            else:
                q = f"{s.upper()}{batch_suffix}"
            preview_data.append({"Scrip in CSV": s, "Yahoo Finance Query Ticker": q})

        st.markdown(f"**Found {len(unique_symbols)} unique symbols** in `{uploaded_file.name}` (Total rows: {len(input_df)}):")
        st.dataframe(pd.DataFrame(preview_data), hide_index=True, **STRETCH)

        st.markdown("<br>", unsafe_allow_html=True)
        run_batch = st.button(
            f"🚀 Fetch Fresh Data from Yahoo, Save to Server & Run Screener ({len(unique_symbols)} Symbols)",
            type="primary",
            **STRETCH
        )

    # Step 4: Execution Engine (Triggered by either Fresh Batch or Server Cache Test)
    should_run = run_batch or test_server_btn
    run_source = "fresh_fetch" if run_batch else ("server_cache" if test_server_btn else "")

    if should_run:
        progress_bar = st.progress(0.0)
        status_box = st.empty()

        all_zip_buffer = io.BytesIO()
        filtered_zip_buffer = io.BytesIO()
        manifest_records = []
        filtered_records = []
        cached_stock_dfs = {}

        successful_count = 0
        failed_count = 0
        matched_count = 0
        total_records = 0

        # Determine symbols to process
        if run_source == "fresh_fetch":
            symbols_to_process = unique_symbols
        else:
            symbols_to_process = [
                f.replace("_OHLC.csv", "").replace(".csv", "")
                for f in server_saved_csvs
            ]

        total_syms = len(symbols_to_process)

        with zipfile.ZipFile(all_zip_buffer, "w", zipfile.ZIP_DEFLATED) as all_zf, \
             zipfile.ZipFile(filtered_zip_buffer, "w", zipfile.ZIP_DEFLATED) as filtered_zf:

            for idx, sym in enumerate(symbols_to_process):
                # Formulate query ticker
                if auto_skip_existing and (sym.endswith(".NS") or sym.endswith(".BO") or sym.startswith("^")):
                    query_ticker = sym.upper()
                else:
                    query_ticker = f"{sym.upper()}{batch_suffix}"

                status_label = "Fetching" if run_source == "fresh_fetch" else "Reading cache"
                status_box.markdown(f"⏳ **{status_label} ({idx + 1}/{total_syms}):** `{sym.upper()}`...")

                df_sym = None
                export_sym_df = None

                if run_source == "fresh_fetch":
                    df_sym = fetch_stock_ohlc(query_ticker, start_date, end_date, auto_adjust=auto_adjust)
                    if df_sym is not None and not df_sym.empty:
                        export_sym_df = df_sym.copy()
                        sym_price_cols = [c for c in ["Open", "High", "Low", "Close", "Adj Close"] if c in export_sym_df.columns]
                        if decimal_places == "2 Decimals":
                            for c in sym_price_cols:
                                export_sym_df[c] = export_sym_df[c].round(2)
                        elif decimal_places == "4 Decimals":
                            for c in sym_price_cols:
                                export_sym_df[c] = export_sym_df[c].round(4)
                        
                        # Save to server disk in SAVED_DATA_DIR for testing
                        server_csv_path = os.path.join(SAVED_DATA_DIR, f"{sym.upper()}_OHLC.csv")
                        try:
                            export_sym_df.to_csv(server_csv_path, index=False)
                        except Exception:
                            pass
                else:
                    # Load directly from server disk
                    server_csv_path = os.path.join(SAVED_DATA_DIR, f"{sym.upper()}_OHLC.csv")
                    if not os.path.exists(server_csv_path):
                        server_csv_path = os.path.join(SAVED_DATA_DIR, f"{sym.upper()}.csv")
                    if os.path.exists(server_csv_path):
                        try:
                            export_sym_df = pd.read_csv(server_csv_path)
                            df_sym = export_sym_df
                        except Exception:
                            df_sym = None

                if df_sym is not None and not df_sym.empty and "Close" in export_sym_df.columns:
                    csv_str = export_sym_df.to_csv(index=False)
                    filename = f"{sym.upper()}_OHLC.csv"
                    all_zf.writestr(filename, csv_str)
                    
                    # Cache in memory for instant chart inspection
                    cached_stock_dfs[sym.upper()] = export_sym_df

                    # Calculate Moving Average
                    ma_series = compute_moving_average(export_sym_df, ma_period, ma_type_short)
                    trading_days = len(export_sym_df)
                    latest_close = float(export_sym_df["Close"].iloc[-1])
                    latest_ma = float(ma_series.iloc[-1]) if not ma_series.empty and not pd.isna(ma_series.iloc[-1]) else float('nan')
                    latest_date = str(export_sym_df["Date"].iloc[-1]) if "Date" in export_sym_df.columns else "N/A"

                    # Evaluate Screener Condition
                    if trading_days < ma_period or pd.isna(latest_ma):
                        is_match = False
                        diff_pct, diff_pts = 0.0, 0.0
                        eval_status = f"⚠️ Insufficient data ({trading_days} < {ma_period} candles)"
                    else:
                        is_match, diff_pct, diff_pts, eval_status = evaluate_screener_condition(
                            latest_close, latest_ma, comparison_mode, operator_choice, target_ma_val, tolerance_pct
                        )

                    if is_match:
                        matched_count += 1
                        filtered_zf.writestr(filename, csv_str)
                        filtered_records.append({
                            "Symbol": sym.upper(),
                            "Query Ticker": query_ticker,
                            "Latest Date": latest_date,
                            "Close Price": round(latest_close, 2),
                            f"{ma_type_short}({ma_period})": round(latest_ma, 2),
                            "Distance (%)": f"{diff_pct:+.2f}%",
                            "Distance (Pts)": f"{diff_pts:+.2f}",
                            "Status": "✅ Pass"
                        })

                    manifest_records.append({
                        "Symbol": sym.upper(),
                        "Query Ticker": query_ticker,
                        "Status": "✅ Pass" if is_match else ("❌ Fail" if eval_status == "Failed" else eval_status),
                        "Latest Close": f"{latest_close:,.2f}",
                        f"{ma_type_short}({ma_period})": f"{latest_ma:,.2f}" if not pd.isna(latest_ma) else "N/A",
                        "Distance (%)": f"{diff_pct:+.2f}%" if not pd.isna(latest_ma) else "-",
                        "Trading Days": trading_days,
                        "Condition Met": "YES" if is_match else "NO"
                    })
                    successful_count += 1
                    total_records += len(export_sym_df)
                else:
                    manifest_records.append({
                        "Symbol": sym.upper(),
                        "Query Ticker": query_ticker,
                        "Status": "❌ Error / No Data",
                        "Latest Close": "-",
                        f"{ma_type_short}({ma_period})": "-",
                        "Distance (%)": "-",
                        "Trading Days": 0,
                        "Condition Met": "NO"
                    })
                    failed_count += 1

                progress_bar.progress((idx + 1) / total_syms)

            # Write manifest CSVs into ZIP archives
            manifest_df = pd.DataFrame(manifest_records)
            all_zf.writestr("_ALL_STOCKS_MANIFEST.csv", manifest_df.to_csv(index=False))

            if filtered_records:
                filtered_df = pd.DataFrame(filtered_records)
                filtered_zf.writestr("_FILTERED_STOCKS_SUMMARY.csv", filtered_df.to_csv(index=False))

        status_box.success(
            f"🎉 Screener complete! Processed {total_syms} stocks. "
            f"**{matched_count} stocks matched** the Moving Average condition."
        )

        # Store in session_state for persistence across reruns
        st.session_state["screener_matched"] = filtered_records
        st.session_state["screener_all"] = manifest_records
        st.session_state["cached_stock_dfs"] = cached_stock_dfs
        st.session_state["batch_zip_data"] = all_zip_buffer.getvalue()
        st.session_state["filtered_zip_data"] = filtered_zip_buffer.getvalue() if filtered_records else None
        st.session_state["screener_meta"] = {
            "total": total_syms,
            "success": successful_count,
            "failed": failed_count,
            "matched": matched_count,
            "total_records": total_records,
            "rule_text": rule_text,
            "ma_type": ma_type_short,
            "ma_period": ma_period,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "all_zip_filename": f"equity_batch_all_{start_date}_to_{end_date}.zip",
            "filtered_zip_filename": f"filtered_stocks_{ma_type_short}{ma_period}_{start_date}_to_{end_date}.zip"
        }

    # Step 5: Results Display (Metrics, Filtered Stocks, Inspector & Downloads)
    if "screener_meta" in st.session_state and st.session_state["screener_meta"]:
        sm = st.session_state["screener_meta"]
        matched_records = st.session_state.get("screener_matched", [])
        all_records = st.session_state.get("screener_all", [])
        cached_dfs = st.session_state.get("cached_stock_dfs", {})

        st.markdown("---")
        st.subheader("📊 Screener Results & Analysis")
        st.markdown(f'<div class="rule-banner">📌 <b>Evaluated Rule:</b> {sm["rule_text"]}</div>', unsafe_allow_html=True)

        # Metrics cards
        pass_rate = (sm["matched"] / sm["total"] * 100.0) if sm["total"] > 0 else 0.0
        sm1, sm2, sm3, sm4, sm5 = st.columns(5)
        with sm1:
            st.metric("Total Analyzed", f"{sm['total']}")
        with sm2:
            st.metric("Matched Condition", f"{sm['matched']}")
        with sm3:
            st.metric("Failed Condition", f"{sm['total'] - sm['matched']}")
        with sm4:
            st.metric("Pass Rate", f"{pass_rate:.1f}%")
        with sm5:
            zip_kb = len(st.session_state["batch_zip_data"]) / 1024 if st.session_state.get("batch_zip_data") else 0
            st.metric("All CSVs ZIP", f"{zip_kb:.1f} KB")

        st.markdown("<br>", unsafe_allow_html=True)

        tab_filtered, tab_all = st.tabs([
            f"🎯 Filtered Stocks ({len(matched_records)})",
            f"📋 All Processed Scrips ({len(all_records)})"
        ])

        with tab_filtered:
            if matched_records:
                filtered_display_df = pd.DataFrame(matched_records)
                st.dataframe(filtered_display_df, hide_index=True, **STRETCH)

                st.markdown("<br>", unsafe_allow_html=True)
                dl_col1, dl_col2 = st.columns(2)
                with dl_col1:
                    # CSV Download of filtered stocks list
                    filtered_csv_bytes = filtered_display_df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label=f"📄 Download Filtered Stocks List ({len(matched_records)} stocks CSV)",
                        data=filtered_csv_bytes,
                        file_name=f"filtered_stocks_{sm['ma_type']}_{sm['ma_period']}.csv",
                        mime="text/csv",
                        type="primary",
                        **STRETCH
                    )
                with dl_col2:
                    if st.session_state.get("filtered_zip_data"):
                        st.download_button(
                            label="📦 Download Filtered Stocks OHLC Data (.ZIP)",
                            data=st.session_state["filtered_zip_data"],
                            file_name=sm["filtered_zip_filename"],
                            mime="application/zip",
                            **STRETCH
                        )

                # Interactive Candlestick + MA Inspector for any filtered stock
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander("🔎 Interactive Chart Inspector for Filtered Stocks", expanded=True):
                    matched_syms = [r["Symbol"] for r in matched_records]
                    selected_stock = st.selectbox("Select a filtered stock to inspect chart:", matched_syms)

                    if selected_stock and selected_stock in cached_dfs:
                        sdf = cached_dfs[selected_stock].copy()
                        sma_line = compute_moving_average(sdf, sm["ma_period"], sm["ma_type"])
                        
                        fig = make_subplots(
                            rows=2, cols=1,
                            shared_xaxes=True,
                            vertical_spacing=0.04,
                            subplot_titles=(f"{selected_stock} with {sm['ma_type']}({sm['ma_period']}) Overlay", "Trading Volume"),
                            row_heights=[0.75, 0.25]
                        )

                        # Candlestick
                        fig.add_trace(
                            go.Candlestick(
                                x=sdf["Date"],
                                open=sdf["Open"],
                                high=sdf["High"],
                                low=sdf["Low"],
                                close=sdf["Close"],
                                name="OHLC",
                                increasing_line_color="#10B981",
                                decreasing_line_color="#EF4444"
                            ),
                            row=1, col=1
                        )

                        # Moving Average Overlay Line
                        fig.add_trace(
                            go.Scatter(
                                x=sdf["Date"],
                                y=sma_line,
                                mode="lines",
                                name=f"{sm['ma_type']}({sm['ma_period']})",
                                line=dict(color="#F59E0B", width=2.5)
                            ),
                            row=1, col=1
                        )

                        # Volume
                        if "Volume" in sdf.columns:
                            colors = ["#10B981" if c >= o else "#EF4444" for c, o in zip(sdf["Close"], sdf["Open"])]
                            fig.add_trace(
                                go.Bar(
                                    x=sdf["Date"],
                                    y=sdf["Volume"],
                                    name="Volume",
                                    marker_color=colors,
                                    opacity=0.6
                                ),
                                row=2, col=1
                            )

                        fig.update_layout(
                            xaxis_rangeslider_visible=False,
                            height=520,
                            margin=dict(l=20, r=20, t=40, b=20),
                            template="plotly_white",
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        )
                        st.plotly_chart(fig, **STRETCH)
            else:
                st.warning(f"⚠️ No stocks met the condition: **{sm['rule_text']}**.")
                st.info("💡 Try adjusting the MA period, changing the operator (> / < / ≈), or increasing the tolerance band.")

        with tab_all:
            all_display_df = pd.DataFrame(all_records)
            st.dataframe(all_display_df, hide_index=True, **STRETCH)

            if st.session_state.get("batch_zip_data"):
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    label=f"📥 Download All {sm['success']} Stock CSVs in ZIP Archive",
                    data=st.session_state["batch_zip_data"],
                    file_name=sm["all_zip_filename"],
                    mime="application/zip",
                    type="primary",
                    **STRETCH
                )
