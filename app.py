import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import warnings
import inspect
import zipfile
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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


# ---------------------------------------------------------
# Sidebar Inputs
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("### 🔀 Workflow Mode")
    app_mode = st.radio(
        "Choose Mode:",
        ["🎯 Single Ticker", "📦 Batch CSV Upload (ZIP)"],
        index=0,
        help="Single Ticker: Interactive chart & individual CSV.\nBatch Upload: Upload CSV with 'Symbol' column & download a ZIP of all CSVs."
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
    # Batch CSV Upload Mode
    # ---------------------------------------------------------
    st.markdown('<div class="main-title">📦 Batch Equity OHLC Downloader</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sub-title">Upload a CSV file containing a <b>Symbol</b> column. The app will automatically append <b>{batch_suffix if batch_suffix else "(none)"}</b>, fetch historical OHLC data for all scrips, and package individual CSVs into a single <b>.zip</b> file.</div>',
        unsafe_allow_html=True
    )

    if start_date > end_date:
        st.error(f"❌ **Invalid Date Range**: Start date ({start_date}) cannot be after End date ({end_date}).")
        st.stop()

    # Step 1: Instructions & Sample Template Card
    with st.expander("ℹ️ Instructions & Download Sample Template", expanded=False):
        st.markdown(f"""
        **How it works:**
        1. Upload a CSV file containing a column named **`Symbol`** (or `Ticker` / `Scrip`).
        2. Scrip symbols in your CSV do **not** need `.NS` at the end (e.g. `RELIANCE`, `TCS`, `INFY`, `HDFCBANK`).
        3. The app automatically appends **`{batch_suffix}`** to each symbol before querying Yahoo Finance.
        4. When the download finishes, download a single **`.zip`** archive containing all individual CSVs plus a summary manifest!
        """)
        sample_csv = "Symbol\nRELIANCE\nTCS\nINFY\nHDFCBANK\nICICIBANK\nTATAMOTORS\nSBIN\n"
        st.download_button(
            label="📄 Download Sample CSV Template",
            data=sample_csv,
            file_name="sample_symbols.csv",
            mime="text/csv"
        )

    # Step 2: File Uploader
    uploaded_file = st.file_uploader(
        "Upload CSV file containing stock symbols:",
        type=["csv"],
        help="Upload a CSV with a column named 'Symbol' containing scrip names."
    )

    if uploaded_file is not None:
        try:
            input_df = pd.read_csv(uploaded_file)
        except Exception as e:
            st.error(f"❌ Error reading CSV file: {e}")
            st.stop()

        if input_df.empty:
            st.warning("⚠️ The uploaded CSV file is empty.")
            st.stop()

        # Find symbol column case-insensitively
        symbol_col = next((c for c in input_df.columns if str(c).strip().lower() in ["symbol", "ticker", "scrip", "symbol_name"]), None)
        if not symbol_col:
            st.info("💡 Could not automatically find a column named 'Symbol'. Please select the column from your file:")
            symbol_col = st.selectbox("Select Symbol Column:", input_df.columns)

        # Extract symbols
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

        # Start Batch Button
        st.markdown("<br>", unsafe_allow_html=True)
        run_batch = st.button(f"🚀 Start Batch Download for {len(unique_symbols)} Symbols & Create ZIP", type="primary", **STRETCH)

        if run_batch:
            progress_bar = st.progress(0.0)
            status_box = st.empty()
            
            zip_buffer = io.BytesIO()
            results_manifest = []
            successful_count = 0
            failed_count = 0
            total_records = 0

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                total_syms = len(unique_symbols)
                for idx, sym in enumerate(unique_symbols):
                    # Formulate query ticker
                    if auto_skip_existing and (sym.endswith(".NS") or sym.endswith(".BO") or sym.startswith("^")):
                        query_ticker = sym.upper()
                    else:
                        query_ticker = f"{sym.upper()}{batch_suffix}"

                    status_box.markdown(f"⏳ **Fetching ({idx + 1}/{total_syms}):** `{query_ticker}`...")
                    
                    df_sym = fetch_stock_ohlc(query_ticker, start_date, end_date, auto_adjust=auto_adjust)

                    if df_sym is not None and not df_sym.empty:
                        # Format decimals if requested
                        export_sym_df = df_sym.copy()
                        sym_price_cols = [c for c in ["Open", "High", "Low", "Close", "Adj Close"] if c in export_sym_df.columns]
                        if decimal_places == "2 Decimals":
                            for c in sym_price_cols:
                                export_sym_df[c] = export_sym_df[c].round(2)
                        elif decimal_places == "4 Decimals":
                            for c in sym_price_cols:
                                export_sym_df[c] = export_sym_df[c].round(4)

                        csv_data = export_sym_df.to_csv(index=False)
                        filename = f"{sym.upper()}_OHLC_{start_date}_to_{end_date}.csv"
                        zf.writestr(filename, csv_data)

                        latest_close = export_sym_df["Close"].iloc[-1] if "Close" in export_sym_df.columns else 0.0
                        results_manifest.append({
                            "Scrip Symbol": sym,
                            "Query Ticker": query_ticker,
                            "Status": "✅ Success",
                            "Trading Days": len(export_sym_df),
                            "Latest Close": f"{latest_close:,.2f}",
                            "File Name": filename
                        })
                        successful_count += 1
                        total_records += len(export_sym_df)
                    else:
                        results_manifest.append({
                            "Scrip Symbol": sym,
                            "Query Ticker": query_ticker,
                            "Status": "❌ No Data / Error",
                            "Trading Days": 0,
                            "Latest Close": "-",
                            "File Name": "-"
                        })
                        failed_count += 1

                    progress_bar.progress((idx + 1) / total_syms)

                # Write batch summary manifest into the zip
                manifest_df = pd.DataFrame(results_manifest)
                zf.writestr("_BATCH_DOWNLOAD_SUMMARY.csv", manifest_df.to_csv(index=False))

            status_box.success(f"🎉 Batch processing complete! {successful_count} of {total_syms} symbols fetched successfully.")
            
            # Store in session state so download button persists without re-fetching
            st.session_state["batch_zip_data"] = zip_buffer.getvalue()
            st.session_state["batch_manifest"] = results_manifest
            st.session_state["batch_meta"] = {
                "total": total_syms,
                "success": successful_count,
                "failed": failed_count,
                "total_records": total_records,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "zip_filename": f"equity_ohlc_batch_{start_date}_to_{end_date}.zip"
            }

        # If batch results exist in session_state, display summary & download button
        if "batch_zip_data" in st.session_state and st.session_state["batch_zip_data"]:
            batch_meta = st.session_state["batch_meta"]
            zip_size_kb = len(st.session_state["batch_zip_data"]) / 1024

            st.markdown("---")
            st.subheader("📊 Batch Summary & Download")

            # Metrics
            bm1, bm2, bm3, bm4, bm5 = st.columns(5)
            with bm1:
                st.metric("Total Symbols", f"{batch_meta['total']}")
            with bm2:
                st.metric("Successful", f"{batch_meta['success']}")
            with bm3:
                st.metric("Failed / Empty", f"{batch_meta['failed']}")
            with bm4:
                st.metric("Total Rows", f"{batch_meta['total_records']:,}")
            with bm5:
                st.metric("ZIP Size", f"{zip_size_kb:.1f} KB")

            st.markdown("<br>", unsafe_allow_html=True)
            
            # Prominent Download Button
            st.download_button(
                label=f"📥 Download All {batch_meta['success']} CSVs in ZIP Archive ({zip_size_kb:.1f} KB)",
                data=st.session_state["batch_zip_data"],
                file_name=batch_meta["zip_filename"],
                mime="application/zip",
                type="primary",
                **STRETCH
            )

            # Results Manifest Table
            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("📋 Processing Manifest")
            manifest_display_df = pd.DataFrame(st.session_state["batch_manifest"])
            st.dataframe(manifest_display_df, hide_index=True, **STRETCH)
