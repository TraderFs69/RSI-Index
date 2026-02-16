import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import time
import re

# ==================================
# CONFIG
# ==================================

st.set_page_config(layout="wide")
st.title("📊 RSI Relative vs ETF (Strict Mapping + Debug)")

try:
    POLYGON_API_KEY = st.secrets["POLYGON_API_KEY"]
except:
    st.error("POLYGON_API_KEY manquante dans Streamlit Secrets.")
    st.stop()

# ==================================
# RSI WILDER (TradingView)
# ==================================

def calculate_rsi(df, period=14):

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1/period,
        adjust=False,
        min_periods=period
    ).mean()

    avg_loss = loss.ewm(
        alpha=1/period,
        adjust=False,
        min_periods=period
    ).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi.iloc[-1]

# ==================================
# FETCH DATA POLYGON
# ==================================

@st.cache_data(ttl=3600)
def get_daily_data(ticker):

    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

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

    df = df[["date", "close"]].sort_values("date")

    # Supprimer bougie partielle du jour
    today = datetime.now().date()
    df = df[df["date"].dt.date < today]

    return df

# ==================================
# STRICT INDEX → ETF MAPPING
# ==================================

def normalize_index(index_name):

    cleaned = str(index_name).upper().strip()
    cleaned = re.sub(r"[-_/]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)

    cleaned = cleaned.replace("S&P500", "S&P 500")
    cleaned = cleaned.replace("SP500", "S&P 500")

    return cleaned


def map_index_to_etf(normalized_index):

    if normalized_index.startswith("S&P 500"):
        return "SPY"

    if normalized_index.startswith("RUSSELL 1000"):
        return "IWB"

    if normalized_index.startswith("RUSSELL 2000"):
        return "IWM"

    if normalized_index.startswith("RUSSELL 3000"):
        return "IWV"

    if normalized_index.startswith("NASDAQ 100"):
        return "QQQ"

    if normalized_index.startswith("DOW"):
        return "DIA"

    if normalized_index.startswith("TSX"):
        return "XIU"

    return None


# ==================================
# MAIN
# ==================================

try:
    df_input = pd.read_csv("nyse_11.1.2025.csv")
except FileNotFoundError:
    st.error("Fichier nyse_11.1.2025.csv introuvable dans le repo.")
    st.stop()

st.success("Fichier chargé automatiquement depuis GitHub.")

results = []
etf_cache = {}

progress = st.progress(0)
total = len(df_input)

for i, (_, row) in enumerate(df_input.iterrows()):

    symbol = row["Symbol"]
    raw_index = row["Index"]

    normalized_index = normalize_index(raw_index)
    etf = map_index_to_etf(normalized_index)

    stock_data = get_daily_data(symbol)

    if etf and etf not in etf_cache:
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
            "Index_Raw": raw_index,
            "Index_Normalized": normalized_index,
            "ETF": etf,
            "Stock_RSI14": round(stock_rsi, 2),
            "ETF_RSI14": round(etf_rsi, 2),
            "RSI_Relative": round(stock_rsi - etf_rsi, 2)
        })

    progress.progress((i + 1) / total)
    time.sleep(0.05)

df_results = pd.DataFrame(results)

if not df_results.empty:

    df_results = df_results.sort_values(by="RSI_Relative", ascending=False)

    st.subheader("📈 Résultats classés par RSI Relatif")
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
