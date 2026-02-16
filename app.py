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
st.title("📊 RSI Relative vs ETF (Polygon - Robust Version)")

try:
    POLYGON_API_KEY = st.secrets["POLYGON_API_KEY"]
except:
    st.error("POLYGON_API_KEY manquante dans Streamlit Secrets.")
    st.stop()

# ==================================
# RSI WILDER (MATCH TRADINGVIEW)
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

    # Supprime la bougie partielle du jour
    today = datetime.now().date()
    df = df[df["date"].dt.date < today]

    return df


# ==================================
# BULLETPROOF INDEX → ETF MAPPING
# ==================================

def map_index_to_etf(index_name):

    if pd.isna(index_name):
        return None

    cleaned = str(index_name).upper()

    # Nettoyage robuste
    cleaned = re.sub(r"[-_/]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip()

    # Normalisation S&P
    cleaned = cleaned.replace("S&P500", "S&P 500")
    cleaned = cleaned.replace("SP500", "S&P 500")

    words = cleaned.split()

    first_two = " ".join(words[:2])

    # Matching strict basé sur le début
    if first_two == "S&P 500":
        return "SPY"

    if first_two == "RUSSELL 1000":
        return "IWB"

    if first_two == "RUSSELL 2000":
        return "IWM"

    if first_two == "RUSSELL 3000":
        return "IWV"

    if first_two == "NASDAQ 100":
        return "QQQ"

    if words[0] == "NASDAQ":
        return "QQQ"

    if words[0] == "DOW":
        return "DIA"

    if words[0] == "TSX":
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
    index_name = row["Index"]

    etf = map_index_to_etf(index_name)

    stock_data = get_daily_data(symbol)

    # Charger ETF une seule fois
    if etf and etf not in etf_cache:
        etf
