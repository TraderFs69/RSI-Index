import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

# ==================================
# CONFIG
# ==================================
POLYGON_API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("📊 RSI Relative vs ETF (Polygon)")

# ==================================
# RSI FUNCTION
# ==================================
def calculate_rsi(df, period=14):
    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi.iloc[-1]

# ==================================
# FETCH DATA
# ==================================
@st.cache_data(ttl=3600)
def get_daily_data(ticker):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=60)

    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start_date.date()}/{end_date.date()}?adjusted=true&sort=asc&apiKey={POLYGON_API_KEY}"

    r = requests.get(url)

    if r.status_code != 200:
        return None

    data = r.json()

    if "results" not in data:
        return None

    df = pd.DataFrame(data["results"])
    df["date"] = pd.to_datetime(df["t"], unit="ms")
    df.rename(columns={"c": "close"}, inplace=True)

    return df[["date", "close"]]

# ==================================
# INDEX → ETF
# ==================================
def map_index_to_etf(index_name):
    index_name = str(index_name).upper()

    if "S&P" in index_name or "SP500" in index_name:
        return "SPY"
    elif "NASDAQ" in index_name:
        return "QQQ"
    elif "DOW" in index_name:
        return "DIA"
    elif "RUSSELL" in index_name:
        return "IWM"
    elif "TSX" in index_name:
        return "XIU"
    else:
        return None

# ==================================
# MAIN
# ==================================

uploaded_file = st.file_uploader("Upload ton fichier CSV (Symbol, Index)", type=["csv"])

if uploaded_file:

    df_input = pd.read_csv(uploaded_file)

    if "Symbol" not in df_input.columns or "Index" not in df_input.columns:
        st.error("Le fichier doit contenir les colonnes : Symbol et Index")
        st.stop()

    results = []
    etf_cache = {}

    progress = st.progress(0)
    total = len(df_input)

    for i, (_, row) in enumerate(df_input.iterrows()):

        symbol = row["Symbol"]
        index_name = row["Index"]

        etf = map_index_to_etf(index_name)

        stock_data = get_daily_data(symbol)

        if etf not in etf_cache and etf:
            etf_data = get_daily_data(etf)
            if etf_data is not None:
                etf_cache[etf] = calculate_rsi(etf_data)
            else:
                etf_cache[etf] = None

        stock_rsi = None
        etf_rsi = etf_cache.get(etf)

        if stock_data is not None:
            stock_rsi = calculate_rsi(stock_data)

        if stock_rsi is not None and etf_rsi is not None:

            results.append({
                "Symbol": symbol,
                "Index": index_name,
                "ETF": etf,
                "Stock_RSI14": round(stock_rsi, 2),
                "ETF_RSI14": round(etf_rsi, 2),
                "RSI_Relative": round(stock_rsi - etf_rsi, 2)
            })

        progress.progress((i + 1) / total)
        time.sleep(0.1)  # évite rate limit Polygon

    df_results = pd.DataFrame(results)

    if not df_results.empty:

        df_results = df_results.sort_values(by="RSI_Relative", ascending=False)

        st.subheader("Résultats classés par RSI Relatif")
        st.dataframe(df_results, use_container_width=True)

        csv = df_results.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Télécharger le CSV",
            csv,
            "rsi_relative_sorted.csv",
            "text/csv"
        )

    else:
        st.warning("Aucun résultat valide.")
