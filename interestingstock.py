from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

app = FastAPI(title="Dynamic Market Anomaly & Sentiment Screener")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional: Core tickers you ALWAYS want tracked alongside dynamic movers
CORE_WATCHLIST = ["SPY", "QQQ", "NVDA", "GLD"]

BULLISH_WORDS = {"surge", "soar", "beat", "upgrade", "growth", "rally", "breakout", "record", "buy", "bull", "ai", "profit"}
BEARISH_WORDS = {"drop", "plunge", "miss", "downgrade", "cut", "crash", "lawsuit", "slump", "sell", "bear", "loss", "warn"}

def get_dynamic_tickers(limit: int = 20) -> List[str]:
    """
    Dynamically fetches today's Most Active stocks from Yahoo Finance's public screener API
    and merges them with your CORE_WATCHLIST.
    """
    discovered = set(CORE_WATCHLIST)
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Pulls 'most_actives' and 'day_gainers' dynamically
    screener_ids = ["most_actives", "day_gainers", "day_losers"]
    
    for scr_id in screener_ids:
        try:
            url = f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?scrIds={scr_id}&count=10"
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                quotes = resp.json()["finance"]["result"][0]["quotes"]
                for q in quotes:
                    symbol = q.get("symbol", "")
                    # Filter out warrants, preferred shares, or non-US OTC tickers
                    if symbol.isalpha() and len(symbol) <= 5:
                        discovered.add(symbol)
        except Exception as e:
            print(f"Screener fetch warning ({scr_id}): {e}")
            
    return list(discovered)[:limit]

def calculate_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0

def score_news_sentiment(news_items: List[Dict[str, Any]]) -> tuple[float, str]:
    if not news_items:
        return 0.0, "No recent headlines"
    
    score = 0
    top_headline = ""
    for idx, item in enumerate(news_items[:5]):
        title = item.get("title") or item.get("content", {}).get("title", "")
        if idx == 0:
            top_headline = title
        words = set(title.lower().replace(":", "").replace(",", "").split())
        score += len(words.intersection(BULLISH_WORDS))
        score -= len(words.intersection(BEARISH_WORDS))
        
    normalized = max(-1.0, min(1.0, score / 4.0))
    return round(normalized, 2), top_headline

def analyze_ticker(symbol: str) -> Dict[str, Any] | None:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1mo")
        if len(hist) < 15:
            return None

        current_price = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2])
        pct_change = ((current_price - prev_close) / prev_close) * 100

        current_vol = float(hist["Volume"].iloc[-1])
        avg_vol_20d = float(hist["Volume"].iloc[:-1].mean())
        rvol = current_vol / avg_vol_20d if avg_vol_20d > 0 else 1.0

        rsi = calculate_rsi(hist["Close"], 14)
        sentiment_score, top_headline = score_news_sentiment(ticker.news)

        rvol_points = min(40, max(0, (rvol - 1.0) * 35))
        rsi_points = min(35, abs(rsi - 50) * 1.4)
        sentiment_points = abs(sentiment_score) * 25
        interesting_score = round(rvol_points + rsi_points + sentiment_points, 1)

        if rvol >= 1.5 and rvol_points >= rsi_points:
            driver_type = "VOLUME_SURGE"
            driver_label = f"Volume Breakout ({rvol:.1f}x Avg)"
        elif rsi >= 70:
            driver_type = "OVERBOUGHT"
            driver_label = f"Overbought Extension (RSI {rsi:.0f})"
        elif rsi <= 30:
            driver_type = "OVERSOLD"
            driver_label = f"Oversold Reversal Watch (RSI {rsi:.0f})"
        elif abs(sentiment_score) >= 0.4:
            driver_type = "NEWS_CATALYST"
            driver_label = "High News Sentiment" if sentiment_score > 0 else "Negative News Shock"
        else:
            driver_type = "BALANCED"
            driver_label = "Steady Trend"

        return {
            "symbol": symbol,
            "price": round(current_price, 2),
            "pct_change": round(pct_change, 2),
            "rvol": round(rvol, 2),
            "rsi": round(rsi, 1),
            "sentiment": sentiment_score,
            "top_headline": top_headline,
            "interesting_score": interesting_score,
            "driver_type": driver_type,
            "driver_label": driver_label,
        }
    except Exception:
        return None

@app.get("/api/interesting-stocks")
def get_interesting_stocks():
    # 1. Dynamically discover today's movers
    tickers = get_dynamic_tickers(limit=24)
    
    # 2. Fetch and compute metrics concurrently across 8 worker threads
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        for data in executor.map(analyze_ticker, tickers):
            if data:
                results.append(data)
                
    results.sort(key=lambda x: x["interesting_score"], reverse=True)
    return {"count": len(results), "stocks": results}
