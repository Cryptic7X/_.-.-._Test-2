#!/usr/bin/env python3
"""
Main script for Stochastic RSI Alerts System
Multi-exchange support: Bybit, KuCoin, OKX, BingX
"""
import sys
import os
import time
import json
import logging
from datetime import datetime, timedelta

# Import configuration first
import config

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Import other modules
import ccxt
import pandas as pd
import numpy as np
from utils.telegram_alert import send_telegram_alert


# ============================================================================
# ALERT MANAGER
# ============================================================================

class AlertManager:
    """Manages alert cooldown periods"""

    def __init__(self, cache_file='alert_cache.json'):
        self.cache_file = cache_file
        self.cache = self.load_cache()

    def load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_cache(self):
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def can_send_alert(self, symbol, timeframe, signal_type):
        cache_key = f"{symbol}_{timeframe}_{signal_type}"
        if cache_key not in self.cache:
            return True

        last_alert = datetime.fromisoformat(self.cache[cache_key])
        cooldown = timedelta(minutes=config.COOLDOWN_PERIODS.get(timeframe, 15))
        return datetime.now() - last_alert >= cooldown

    def record_alert(self, symbol, timeframe, signal_type):
        cache_key = f"{symbol}_{timeframe}_{signal_type}"
        self.cache[cache_key] = datetime.now().isoformat()
        self.save_cache()

    def clear_opposite_signal(self, symbol, timeframe, signal_type):
        opposite = 'OVERSOLD' if signal_type == 'OVERBOUGHT' else 'OVERBOUGHT'
        opposite_key = f"{symbol}_{timeframe}_{opposite}"
        if opposite_key in self.cache:
            del self.cache[opposite_key]
            self.save_cache()


# ============================================================================
# STOCHASTIC RSI
# ============================================================================

def calculate_rsi(src, length):
    delta = src.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_stoch(src, high, low, length):
    lowest = low.rolling(window=length, min_periods=length).min()
    highest = high.rolling(window=length, min_periods=length).max()
    stoch = 100 * (src - lowest) / (highest - lowest)
    return stoch.replace([np.inf, -np.inf], np.nan)


def calculate_stochastic_rsi(closes, length_rsi=14, length_stoch=14, smooth_k=3, smooth_d=3):
    try:
        src = pd.Series(closes)
        rsi1 = calculate_rsi(src, length_rsi)
        stoch_rsi = calculate_stoch(rsi1, rsi1, rsi1, length_stoch)
        k = stoch_rsi.rolling(window=smooth_k, min_periods=smooth_k).mean()
        d = k.rolling(window=smooth_d, min_periods=smooth_d).mean()

        k_val = k.iloc[-1] if not pd.isna(k.iloc[-1]) else None
        d_val = d.iloc[-1] if not pd.isna(d.iloc[-1]) else None

        if k_val is None or d_val is None:
            return None
        return {'k': round(k_val, 2), 'd': round(d_val, 2)}
    except:
        return None


def determine_signal(k, d, overbought=80, oversold=20):
    if k >= overbought and d >= overbought:
        return 'OVERBOUGHT'
    elif k <= oversold and d <= oversold:
        return 'OVERSOLD'
    return 'NEUTRAL'


# ============================================================================
# EXCHANGE
# ============================================================================

def get_exchange():
    for exchange_name in config.EXCHANGE_PRIORITY:
        try:
            exchange_class = getattr(ccxt, exchange_name)
            exchange = exchange_class(config.EXCHANGE_OPTIONS)
            exchange.load_markets()
            logger.info(f"✓ Initialized {exchange_name.upper()} - {len(exchange.markets)} markets")
            return exchange
        except Exception as e:
            logger.warning(f"✗ Failed {exchange_name}: {e}")
    raise Exception("All exchanges failed")


def normalize_symbol(symbol, exchange):
    """Find the correct symbol format for this exchange"""
    # Direct match
    if symbol in exchange.markets:
        return symbol

    # Try without slash
    no_slash = symbol.replace('/', '')
    if no_slash in exchange.markets:
        return no_slash

    # Try with slash
    if '/' not in symbol and 'USDT' in symbol:
        with_slash = symbol.replace('USDT', '/USDT')
        if with_slash in exchange.markets:
            return with_slash

    return None


def fetch_ohlcv_data(exchange, symbol, timeframe, limit=100):
    try:
        normalized = normalize_symbol(symbol, exchange)
        if not normalized:
            return None

        ohlcv = exchange.fetch_ohlcv(normalized, timeframe, limit=limit)
        return ohlcv if ohlcv and len(ohlcv) > 0 else None
    except:
        return None


# ============================================================================
# COINS
# ============================================================================

def load_coins():
    try:
        with open(config.COINS_FILE, 'r') as f:
            content = f.read()

        coins = []
        for line in content.split('\n'):
            for coin in line.split(','):
                coin = coin.strip()
                if coin and not coin.startswith('#'):
                    coins.append(coin)

        formatted = []
        for coin in coins:
            if not coin:
                continue
            if '/' not in coin and 'USDT' in coin:
                formatted.append(coin[:-4] + '/USDT')
            else:
                formatted.append(coin)

        logger.info(f"Loaded {len(formatted)} coins")
        return formatted
    except Exception as e:
        logger.error(f"Error loading coins: {e}")
        return []


def validate_coins(exchange, coins):
    """Check which coins are available on the exchange"""
    available = []
    unavailable = []

    logger.info(f"\nValidating coins on {exchange.id.upper()}...")

    for coin in coins:
        if normalize_symbol(coin, exchange):
            available.append(coin)
            logger.debug(f"  ✓ {coin}")
        else:
            unavailable.append(coin)
            logger.warning(f"  ✗ {coin} - not available")

    logger.info(f"Available: {len(available)}, Unavailable: {len(unavailable)}")
    if unavailable:
        logger.info(f"Skipping: {', '.join(unavailable)}")

    return available, unavailable


# ============================================================================
# ANALYSIS
# ============================================================================

def analyze_symbol(exchange, symbol, alert_manager):
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"Analyzing {symbol}")

        timeframe_data = {}

        for tf in config.TIMEFRAMES:
            ohlcv = fetch_ohlcv_data(exchange, symbol, tf, config.CANDLES_LIMIT)

            if not ohlcv or len(ohlcv) < config.MIN_CANDLES_REQUIRED:
                logger.warning(f"  {tf}: Insufficient data")
                continue

            closes = [c[4] for c in ohlcv]
            stoch = calculate_stochastic_rsi(
                closes, config.LENGTH_RSI, config.LENGTH_STOCH,
                config.SMOOTH_K, config.SMOOTH_D
            )

            if not stoch:
                logger.warning(f"  {tf}: Calculation failed")
                continue

            k, d = stoch['k'], stoch['d']
            signal = determine_signal(k, d, config.OVERBOUGHT_LEVEL, config.OVERSOLD_LEVEL)

            timeframe_data[tf] = {'k': k, 'd': d, 'status': signal}
            logger.info(f"  {tf}: K={k:.2f}, D={d:.2f}, {signal}")

        # Alert check
        if config.PRIMARY_TIMEFRAME in timeframe_data:
            signal_type = timeframe_data[config.PRIMARY_TIMEFRAME]['status']

            if signal_type in ['OVERBOUGHT', 'OVERSOLD']:
                if alert_manager.can_send_alert(symbol, config.PRIMARY_TIMEFRAME, signal_type):
                    logger.info(f"🔔 Alert: {signal_type}")
                    if send_telegram_alert(symbol, signal_type, timeframe_data, config.PRIMARY_TIMEFRAME):
                        alert_manager.record_alert(symbol, config.PRIMARY_TIMEFRAME, signal_type)
                        alert_manager.clear_opposite_signal(symbol, config.PRIMARY_TIMEFRAME, signal_type)
                else:
                    logger.info("⏳ Cooldown active")
            else:
                logger.info("✓ NEUTRAL")

        return True
    except Exception as e:
        logger.error(f"Error: {e}")
        return False


# ============================================================================
# MAIN
# ============================================================================

def main():
    start = time.time()
    logger.info("="*60)
    logger.info("STOCHASTIC RSI ALERTS - START")
    logger.info("="*60)

    try:
        exchange = get_exchange()
    except:
        logger.error("Failed to initialize exchange")
        return

    alert_manager = AlertManager()
    coins = load_coins()

    if not coins:
        logger.error("No coins loaded")
        return

    # Validate coins
    available, unavailable = validate_coins(exchange, coins)

    if not available:
        logger.error("No available coins")
        return

    logger.info(f"\nAnalyzing {len(available)} coins on {len(config.TIMEFRAMES)} timeframes")

    success = 0
    for i, symbol in enumerate(available, 1):
        logger.info(f"\n[{i}/{len(available)}] {symbol}")
        if analyze_symbol(exchange, symbol, alert_manager):
            success += 1
        if i < len(available):
            time.sleep(exchange.rateLimit / 1000)

    elapsed = time.time() - start
    logger.info("\n" + "="*60)
    logger.info("COMPLETE")
    logger.info(f"Analyzed: {success}/{len(available)}")
    logger.info(f"Skipped: {len(unavailable)}")
    logger.info(f"Exchange: {exchange.id.upper()}")
    logger.info(f"Time: {elapsed:.2f}s")
    logger.info("="*60)


if __name__ == "__main__":
    main()
