#!/usr/bin/env python3
"""
main.py — Fast, accurate Stochastic RSI alerts
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
    if len(series) >= length:
        r.iloc[length - 1] = series.iloc[:length].mean()
    return r


def tv_rsi(closes: list, length: int = 14) -> pd.Series:
    close = pd.Series(closes, dtype='float64')
    d = close.diff()
    up = d.clip(lower=0)
    down = -d.clip(upper=0)
    return 100 - 100 / (1 + rma(up, length) / rma(down, length))


def tv_stochastic_rsi(closes, rsi_len, stoch_len, k_smooth, d_smooth):
    rsi1 = tv_rsi(closes, rsi_len)
    lo = rsi1.rolling(stoch_len).min()
    hi = rsi1.rolling(stoch_len).max()
    st = 100 * (rsi1 - lo) / (hi - lo)
    k = st.rolling(k_smooth).mean()
    d = k.rolling(d_smooth).mean()
    if pd.isna(k.iloc[-1]) or pd.isna(d.iloc[-1]):
        return None
    return {'k': round(float(k.iloc[-1]), 2), 'd': round(float(d.iloc[-1]), 2)}


def get_exchange():
    for name in EXCHANGE_PRIORITY:
        try:
            ex = getattr(ccxt, name)(EXCHANGE_OPTIONS)
            ex.load_markets()
            logger.info(f"✓ {name.upper()}")
            return ex
        except Exception as e:
            logger.warning(f"✗ {name}: {e}")
    raise Exception("All exchanges failed")


class AlertManager:
    def __init__(self, file='alert_cache.json'):
        self.file = file
        self.cache = self._load()

    def _load(self):
        if os.path.exists(self.file):
            try:
                return json.load(open(self.file))
            except:
                pass
        return {}

    def _save(self):
        try:
            json.dump(self.cache, open(self.file, 'w'))
        except:
            pass

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
    if sym not in ex.markets:
        logger.warning(f"⚠ {sym} unavailable")
        return
    logger.info(f"\n{sym}")
    tf_data = {}
    limit = LENGTH_RSI + LENGTH_STOCH + SMOOTH_K + SMOOTH_D + 50
    for tf in TIMEFRAMES:
        try:
            ohlcv = ex.fetch_ohlcv(sym, tf, limit=limit)
            if len(ohlcv) < limit:
                logger.warning(f"  {tf}: Insufficient data")
                continue
            closes = [c[4] for c in ohlcv]
            res = tv_stochastic_rsi(closes, LENGTH_RSI, LENGTH_STOCH, SMOOTH_K, SMOOTH_D)
            if not res:
                logger.warning(f"  {tf}: Calc failed")
                continue
            k, d = res['k'], res['d']
            sig = ("OVERBOUGHT" if k >= OVERBOUGHT_LEVEL and d >= OVERBOUGHT_LEVEL
                   else "OVERSOLD" if k <= OVERSOLD_LEVEL and d <= OVERSOLD_LEVEL
                   else "NEUTRAL")
            tf_data[tf] = {'k': k, 'd': d, 'status': sig}
            logger.info(f"  {tf}: K={k:6.2f} D={d:6.2f} [{sig}]")
        except Exception as e:
            logger.warning(f"  {tf}: {e}")
    if PRIMARY_TIMEFRAME in tf_data:
        s = tf_data[PRIMARY_TIMEFRAME]['status']
        if s in ("OVERBOUGHT", "OVERSOLD") and am.can_alert(sym, PRIMARY_TIMEFRAME, s):
            logger.info(f"🚨 {s}")
            tv, cg = create_chart_links(sym.replace('/USDT',''), 15)
            send_alert(sym, s, tf_data, PRIMARY_TIMEFRAME, tv, cg)
            am.record(sym, PRIMARY_TIMEFRAME, s)


def main():
    st = time.time()
    logger.info("="*40 + "\nSTOCH RSI START\n" + "="*40)
    ex = get_exchange()
    am = AlertManager()
    coins = load_coins()
    logger.info(f"Loaded {len(coins)} coins")
    for i, c in enumerate(coins,1):
        logger.info(f"[{i}/{len(coins)}]")
        analyze(ex, c, am)
        time.sleep(0.1)
    et = time.time() - st
    logger.info(f"\nDone {et:.1f}s")


if __name__=="__main__":
    main()
