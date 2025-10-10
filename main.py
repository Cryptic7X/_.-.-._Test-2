#!/usr/bin/env python3
"""
main.py — Simple, single-file Stochastic RSI alerts
"""
import sys, os, time, json, logging
from datetime import datetime, timedelta

import ccxt
import pandas as pd
import numpy as np

from config import (
    TIMEFRAMES, PRIMARY_TIMEFRAME,
    LENGTH_RSI, LENGTH_STOCH, SMOOTH_K, SMOOTH_D,
    OVERBOUGHT_LEVEL, OVERSOLD_LEVEL,
    COOLDOWN_PERIODS, EXCHANGE_PRIORITY, EXCHANGE_OPTIONS,
    COINS_FILE, LOG_LEVEL, LOG_FORMAT
)
from utils.telegram_alert import send_alert, create_chart_links

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def rma(series: pd.Series, length: int) -> pd.Series:
    alpha = 1 / length
    r = series.ewm(alpha=alpha, adjust=False).mean()
    r.iloc[length - 1] = series.iloc[:length].mean()  # seed
    return r


def tv_rsi(closes: list[float], length: int = 14) -> pd.Series:
    close = pd.Series(closes, dtype='float64')
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_up = rma(up, length)
    avg_down = rma(down, length)
    rs = avg_up / avg_down
    return 100 - 100 / (1 + rs)


def get_exchange():
    for name in EXCHANGE_PRIORITY:
        try:
            ex = getattr(ccxt, name)(EXCHANGE_OPTIONS)
            ex.load_markets()
            logger.info(f"✓ Connected to {name.upper()}")
            return ex
        except Exception:
            continue
    raise Exception("All exchanges failed")


class AlertManager:
    def __init__(self, cache_file='alert_cache.json'):
        self.file = cache_file
        self.cache = self._load()

    def _load(self):
        if os.path.exists(self.file):
            try:
                return json.load(open(self.file))
            except:
                pass
        return {}

    def _save(self):
        json.dump(self.cache, open(self.file, 'w'))

    def can_alert(self, sym, tf, sig):
        key = f"{sym}_{tf}_{sig}"
        if key not in self.cache:
            return True
        last = datetime.fromisoformat(self.cache[key])
        return datetime.now() - last >= timedelta(minutes=COOLDOWN_PERIODS[tf])

    def record(self, sym, tf, sig):
        self.cache[f"{sym}_{tf}_{sig}"] = datetime.now().isoformat()
        self._save()


def load_coins():
    txt = open(COINS_FILE).read()
    coins = [c.strip() for line in txt.splitlines() for c in line.split(',') if c.strip()]
    return [c if '/' in c else c + '/USDT' for c in coins]


def analyze(ex, sym, am):
    logger.info(f"\nAnalyzing {sym}")
    tf_data = {}
    ohlcv_limit = max(LENGTH_STOCH, SMOOTH_K, SMOOTH_D) + LENGTH_RSI + 50

    for tf in TIMEFRAMES:
        data = ex.fetch_ohlcv(sym, tf, limit=ohlcv_limit)
        if len(data) < ohlcv_limit:
            logger.warning(f"  {tf}: insufficient data")
            continue
        closes = [c[4] for c in data]
        rsi1 = tv_rsi(closes, LENGTH_RSI)
        low = rsi1.rolling(LENGTH_STOCH).min()
        high = rsi1.rolling(LENGTH_STOCH).max()
        stoch = 100 * (rsi1 - low) / (high - low)
        k = stoch.rolling(SMOOTH_K).mean().iloc[-1]
        d = pd.Series(k).rolling(SMOOTH_D).mean().iloc[-1]
        sig = ("OVERBOUGHT" if k >= OVERBOUGHT_LEVEL and d >= OVERBOUGHT_LEVEL
               else "OVERSOLD" if k <= OVERSOLD_LEVEL and d <= OVERSOLD_LEVEL
               else "NEUTRAL")
        tf_data[tf] = {'k': k, 'd': d, 'status': sig}
        logger.info(f"  {tf}: K={k:.2f} D={d:.2f} {sig}")

    psig = tf_data.get(PRIMARY_TIMEFRAME, {}).get('status')
    if psig in ("OVERBOUGHT", "OVERSOLD") and am.can_alert(sym, PRIMARY_TIMEFRAME, psig):
        tv, cg = create_chart_links(sym.replace('/USDT',''), int(PRIMARY_TIMEFRAME[:-1]))
        send_alert(sym, psig, tf_data, PRIMARY_TIMEFRAME, tv, cg)
        am.record(sym, PRIMARY_TIMEFRAME, psig)


def main():
    ex = get_exchange()
    am = AlertManager()
    coins = load_coins()
    logger.info(f"Loaded {len(coins)} coins")
    for i, sym in enumerate(coins, 1):
        logger.info(f"[{i}/{len(coins)}] {sym}")
        analyze(ex, sym, am)
        time.sleep(1.2)


if __name__ == "__main__":
    main()
