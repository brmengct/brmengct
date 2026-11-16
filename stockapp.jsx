import React, { useState, useEffect } from 'react';

const DRIVER_STYLES = {
  VOLUME_SURGE: {
    border: 'border-amber-500 bg-amber-950/20',
    badge: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
    accent: 'text-amber-400',
  },
  OVERBOUGHT: {
    border: 'border-rose-500 bg-rose-950/20',
    badge: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
    accent: 'text-rose-400',
  },
  OVERSOLD: {
    border: 'border-emerald-500 bg-emerald-950/20',
    badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
    accent: 'text-emerald-400',
  },
  NEWS_CATALYST: {
    border: 'border-sky-500 bg-sky-950/20',
    badge: 'bg-sky-500/20 text-sky-300 border-sky-500/40',
    accent: 'text-sky-400',
  },
  BALANCED: {
    border: 'border-slate-700 bg-slate-900/60',
    badge: 'bg-slate-800 text-slate-300 border-slate-700',
    accent: 'text-slate-300',
  },
};

export default function App() {
  const [stocks, setStocks] = useState([]);
  const [filter, setFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);

  const fetchMarketData = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/interesting-stocks');
      const data = await res.json();
      setStocks(data.stocks || []);
    } catch (err) {
      console.error('Failed to fetch scanner data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMarketData();
  }, []);

  const filteredStocks =
    filter === 'ALL' ? stocks : stocks.filter((s) => s.driver_type === filter);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 font-sans">
      <div className="max-w-6xl mx-auto">
        {/* Header & Controls */}
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6 mb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Market Anomaly & Sentiment Radar
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Ranked by Relative Volume (RVOL), RSI-14 Extremes, and Headline Polarity
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {['ALL', 'VOLUME_SURGE', 'OVERSOLD', 'OVERBOUGHT', 'NEWS_CATALYST'].map((type) => (
              <button
                key={type}
                onClick={() => setFilter(type)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${
                  filter === type
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-900 text-slate-400 hover:bg-slate-800'
                }`}
              >
                {type.replace('_', ' ')}
              </button>
            ))}
            <button
              onClick={fetchMarketData}
              className="ml-2 px-3 py-1.5 rounded-md text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200"
            >
              ↻ Refresh
            </button>
          </div>
        </header>

        {/* Loading State */}
        {loading ? (
          <div className="text-center py-20 text-slate-400 animate-pulse">
            Scanning technical indicators and news feeds...
          </div>
        ) : (
          /* Dynamic Grid */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredStocks.map((stock) => {
              const style = DRIVER_STYLES[stock.driver_type] || DRIVER_STYLES.BALANCED;
              const isPositive = stock.pct_change >= 0;

              return (
                <div
                  key={stock.symbol}
                  className={`rounded-xl border p-5 transition-all shadow-lg ${style.border}`}
                >
                  {/* Top Row: Ticker & Score */}
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xl font-bold">{stock.symbol}</span>
                        <span
                          className={`text-xs font-semibold px-2 py-0.5 rounded ${
                            isPositive
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : 'bg-rose-500/20 text-rose-400'
                          }`}
                        >
                          {isPositive ? '+' : ''}
                          {stock.pct_change}%
                        </span>
                      </div>
                      <div className="text-lg font-mono text-slate-200 mt-0.5">
                        ${stock.price.toFixed(2)}
                      </div>
                    </div>

                    <div className="text-right">
                      <span className="text-[10px] uppercase tracking-wider text-slate-400 block">
                        Anomaly Score
                      </span>
                      <span className={`text-xl font-black ${style.accent}`}>
                        {stock.interesting_score}
                      </span>
                    </div>
                  </div>

                  {/* Dynamic Catalyst Badge */}
                  <div className={`inline-block text-xs px-2.5 py-1 rounded-md border mb-4 ${style.badge}`}>
                    {stock.driver_label}
                  </div>

                  {/* Conditional Display 1: Volume Surge Bar */}
                  {stock.driver_type === 'VOLUME_SURGE' && (
                    <div className="mb-4 bg-slate-900/80 p-3 rounded-lg border border-amber-500/20">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-amber-300">Relative Volume Surge</span>
                        <span className="font-mono font-bold">{stock.rvol}x avg</span>
                      </div>
                      <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div
                          className="bg-amber-400 h-full"
                          style={{ width: `${Math.min(100, (stock.rvol / 3) * 100)}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Conditional Display 2: RSI Meter */}
                  {(stock.driver_type === 'OVERSOLD' || stock.driver_type === 'OVERBOUGHT') && (
                    <div className="mb-4 bg-slate-900/80 p-3 rounded-lg border border-slate-700">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-slate-300">14-Day RSI Extreme</span>
                        <span className="font-mono font-bold">{stock.rsi} / 100</span>
                      </div>
                      <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${
                            stock.rsi >= 70 ? 'bg-rose-500' : 'bg-emerald-500'
                          }`}
                          style={{ width: `${stock.rsi}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Conditional Display 3: Highlighted News Box */}
                  {stock.top_headline && (
                    <div
                      className={`p-3 rounded-lg text-xs leading-relaxed ${
                        stock.driver_type === 'NEWS_CATALYST'
                          ? 'bg-sky-950/60 border border-sky-500/30 text-sky-100'
                          : 'bg-slate-900/50 text-slate-400'
                      }`}
                    >
                      <span className="font-semibold uppercase text-[10px] tracking-wider block mb-1 opacity-75">
                        Latest Catalyst ({stock.sentiment > 0 ? 'Bullish' : stock.sentiment < 0 ? 'Bearish' : 'Neutral'})
                      </span>
                      "{stock.top_headline}"
                    </div>
                  )}

                  {/* Footer Metrics */}
                  <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-slate-800/80 text-center text-xs">
                    <div>
                      <span className="text-slate-500 block">RVOL</span>
                      <span className="font-mono">{stock.rvol}x</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">RSI-14</span>
                      <span className="font-mono">{stock.rsi}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Sentiment</span>
                      <span className="font-mono">{stock.sentiment}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
