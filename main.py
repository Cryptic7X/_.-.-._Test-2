#!/usr/bin/env python3
"""
main.py — Fast Stochastic RSI alerts with exact K/D values
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
    """Wilder's RMA exactly as TradingView"""
    alpha = 1 / length
    r = series.ewm(alpha=alpha, adjust=False).mean()
    if len(series) >= length:
        r.iloc[length - 1] = series.iloc[:length].mean()
    return r


def tv_rsi(closes: list, length: int = 14) -> pd.Series:
    """TradingView RSI calculation"""
    close = pd.Series(closes, dtype='float64')
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_up = rma(up, length)
    avg_down = rma(down, length)
    rs = avg_up / avg_down
    return 100 - 100 / (1 + rs)


def tv_stochastic_rsi(closes: list, rsi_len=14, stoch_len=14, k_smooth=3, d_smooth=3):
    """TradingView Stochastic RSI - exact Pine Script logic"""
    try:
        # Step 1: Calculate RSI
        rsi1 = tv_rsi(closes, rsi_len)
        
        # Step 2: Stochastic of RSI
        lowest = rsi1.rolling(stoch_len).min()
        highest = rsi1.rolling(stoch_len).max()
        stoch = 100 * (rsi1 - lowest) / (highest - lowest)
        
        # Step 3: Smooth K
        k = stoch.rolling(k_smooth).mean()
        
        # Step 4: Smooth D from K series
        d = k.rolling(d_smooth).mean()
        
        # Get last valid values
        k_val = k.iloc[-1]
        d_val = d.iloc[-1]
        
        if pd.isna(k_val) or pd.isna(d_val):
            return None
        
        return {'k': round(float(k_val), 2), 'd': round(float(d_val), 2)}
    except Exception as e:
        logger.debug(f"Calc error: {e}")
        return None


def get_exchange():
    """Connect to first available exchange"""
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
    """Simple cooldown manager"""
    def __init__(self, cache_file='alert_cache.json'):
        self.file = cache_file
        self.cache = self._load()

    def _load(self):
        if os.path.exists(self.file):
            try:
                with open(self.file) as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save(self):
        try:
            with open(self.file, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            logger.debug(f"Cache save error: {e}")

    def can_alert(self, sym, tf, sig):
        key = f"{sym}_{tf}_{sig}"
        if key not in self.cache:
            return True
        last = datetime.fromisoformat(self.cache[key])
        cooldown = timedelta(minutes=COOLDOWN_PERIODS.get(tf, 15))
        return datetime.now() - last >= cooldown

    def record(self, sym, tf, sig):
        key = f"{sym}_{tf}_{sig}"
        self.cache[key] = datetime.now().isoformat()
        self._save()


def load_coins():
    """Load coin list"""
    with open(COINS_FILE) as f:
        txt = f.read()
    coins = [c.strip() for line in txt.splitlines() for c in line.split(',') if c.strip()]
    return [c if '/' in c else c + '/USDT' for c in coins]


def analyze(ex, sym, am):
    """Analyze one symbol"""
    try:
        # Quick check if symbol exists
        if sym not in ex.markets:
            logger.warning(f"⚠️ {sym} unavailable")
            return False
        
        logger.info(f"\n{sym}")
        tf_data = {}
        
        # Fetch enough candles
        limit = LENGTH_RSI + LENGTH_STOCH + SMOOTH_K + SMOOTH_D + 50
        
        for tf in TIMEFRAMES:
            try:
                ohlcv = ex.fetch_ohlcv(sym, tf, limit=limit)
                if len(ohlcv) < 60:
                    logger.warning(f"  {tf}: Insufficient data")
                    continue
                
                closes = [c[4] for c in ohlcv]
                result = tv_stochastic_rsi(closes, LENGTH_RSI, LENGTH_STOCH, SMOOTH_K, SMOOTH_D)
                
                if not result:
                    logger.warning(f"  {tf}: Calc failed")
                    continue
                
                k, d = result['k'], result['d']
                
                # Determine signal
                if k >= OVERBOUGHT_LEVEL and d >= OVERBOUGHT_LEVEL:
                    sig = "OVERBOUGHT"
                elif k <= OVERSOLD_LEVEL and d <= OVERSOLD_LEVEL:
                    sig = "OVERSOLD"
                else:
                    sig = "NEUTRAL"
                
                tf_data[tf] = {'k': k, 'd': d, 'status': sig}
                
                # ALWAYS show K and D values
                logger.info(f"  {tf}: K={k:6.2f} D={d:6.2f} [{sig}]")
                
            except Exception as e:
                logger.warning(f"  {tf}: {str(e)[:50]}")
                continue
        
        # Check for alerts on primary timeframe
        if PRIMARY_TIMEFRAME in tf_data:
            data = tf_data[PRIMARY_TIMEFRAME]
            sig = data['status']
            
            if sig in ("OVERBOUGHT", "OVERSOLD") and am.can_alert(sym, PRIMARY_TIMEFRAME, sig):
                logger.info(f"🚨 {sig} ALERT")
                tv, cg = create_chart_links(sym.replace('/USDT', ''), 15)
                send_alert(sym, sig, tf_data, PRIMARY_TIMEFRAME, tv, cg)
                am.record(sym, PRIMARY_TIMEFRAME, sig)
        
        return True
    
    except Exception as e:
        logger.error(f"❌ {sym}: {str(e)[:100]}")
        return False


def main():
    """Main execution"""
    start = time.time()
    logger.info("="*50)
    logger.info("STOCHASTIC RSI ALERTS")
    logger.info("="*50)
    
    try:
        ex = get_exchange()
        am = AlertManager()
        coins = load_coins()
        
        logger.info(f"\nAnalyzing {len(coins)} coins...\n")
        
        success = 0
        for i, sym in enumerate(coins, 1):
            logger.info(f"[{i}/{len(coins)}]")
            if analyze(ex, sym, am):
                success += 1
            # Minimal delay for rate limiting
            time.sleep(0.3)
        
        elapsed = time.time() - start
        logger.info("\n" + "="*50)
        logger.info(f"✓ {success}/{len(coins)} analyzed in {elapsed:.1f}s")
        logger.info("="*50)
    
    except Exception as e:
        logger.error(f"Main error: {e}")
        raise


if __name__ == "__main__":
    main()
