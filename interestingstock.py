from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional

app = FastAPI(title="Dynamic Market Anomaly & Sentiment Screener")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CORE_WATCHLIST = ["SPY", "QQQ", "NVDA", "GLD"]
BULLISH_WORDS = {"surge", "soar", "beat", "upgrade", "growth", "rally", "breakout", "record", "buy", "bull", "ai", "profit"}
BEARISH_WORDS = {"drop", "plunge", "miss", "downgrade", "cut", "crash", "lawsuit", "slump", "sell", "bear", "loss", "warn"}

# Simple in-memory TTL cache: {cache_key: (timestamp, payload)}
CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 60

def get_dynamic_tickers(custom_tickers: List[str], limit: int = 24) -> List[str]:
    discovered = set(CORE_WATCHLIST + [t.upper().strip() for t in custom_tickers if t.strip()])
    headers = {"User-Agent": "Mozilla/5.0"}
    screener_ids = ["most_actives", "day_gainers", "day_losers"]
    
    for scr_id in screener_ids:
        try:
            url = f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?scrIds={scr_id}&count=10"
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                quotes = resp.json()["finance"]["result"][0]["quotes"]
                for q in quotes:
                    symbol = q.get("symbol", "")
                    if symbol.isalpha() and len(symbol) <= 5:
                        discovered.add(symbol)
        except Exception as e:
            print(f"Screener fetch warning ({scr_id}): {e}")
            
    # Ensure custom tickers are never sliced off by the limit
    priority = list(dict.fromkeys([t.upper().strip() for t in custom_tickers if t.strip()] + CORE_WATCHLIST))
    others = [t for t in discovered if t not in priority]
    return (priority + others)[:limit]

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
    
    # Clamped to [-1.0, +1.0]: -1.0 is strongly bearish, 0 is neutral, and +1.0 is strongly bullish.
    normalized = max(-1.0, min(1.0, score / 4.0))
    return round(normalized, 2), top_headline

def analyze_ticker(symbol: str, is_custom: bool = False) -> Dict[str, Any] | None:
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
            "is_custom": is_custom,
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
def get_interesting_stocks(
    custom: Optional[str] = Query(default="", description="Comma-separated custom tickers"),
    force_refresh: bool = Query(default=False)
):
    custom_list = [t.upper().strip() for t in custom.split(",") if t.strip()]
    cache_key = ",".join(sorted(custom_list))
    now = time.time()

    # Serve from cache if valid and not force-refreshed
    if not force_refresh and cache_key in CACHE:
        cached_time, cached_payload = CACHE[cache_key]
        if now - cached_time < CACHE_TTL_SECONDS:
            return {**cached_payload, "cached": True, "cache_age_sec": int(now - cached_time)}

    tickers = get_dynamic_tickers(custom_list, limit=24)
    custom_set = set(custom_list)
    
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(analyze_ticker, sym, sym in custom_set) for sym in tickers]
        for f in futures:
            data = f.result()
            if data:
                results.append(data)
                
    results.sort(key=lambda x: x["interesting_score"], reverse=True)
    payload = {"count": len(results), "stocks": results, "cached": False, "cache_age_sec": 0}
    CACHE[cache_key] = (now, payload)
    return payload
