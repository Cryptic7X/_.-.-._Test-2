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
        """Load alert cache from file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
                logger.info(f"Loaded cache with {len(cache)} entries")
                return cache
            except Exception as e:
                logger.error(f"Error loading cache: {e}")
                return {}
        return {}

    def save_cache(self):
        """Save alert cache to file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
            logger.debug("Cache saved")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def can_send_alert(self, symbol, timeframe, signal_type):
        """Check if enough time has passed since last alert"""
        cache_key = f"{symbol}_{timeframe}_{signal_type}"

        if cache_key not in self.cache:
            return True

        last_alert_time = datetime.fromisoformat(self.cache[cache_key])
        cooldown_minutes = config.COOLDOWN_PERIODS.get(timeframe, 15)
        cooldown_delta = timedelta(minutes=cooldown_minutes)

        time_since_alert = datetime.now() - last_alert_time

        if time_since_alert >= cooldown_delta:
            logger.info(f"Cooldown expired for {cache_key}")
            return True
        else:
            remaining_minutes = (cooldown_delta - time_since_alert).seconds // 60
            logger.debug(f"Cooldown active for {cache_key} ({remaining_minutes}m remaining)")
            return False

    def record_alert(self, symbol, timeframe, signal_type):
        """Record that an alert was sent"""
        cache_key = f"{symbol}_{timeframe}_{signal_type}"
        self.cache[cache_key] = datetime.now().isoformat()
        self.save_cache()
        logger.info(f"Recorded alert for {cache_key}")

    def clear_opposite_signal(self, symbol, timeframe, signal_type):
        """Clear opposite signal from cache"""
        opposite_signal = 'OVERSOLD' if signal_type == 'OVERBOUGHT' else 'OVERBOUGHT'
        opposite_key = f"{symbol}_{timeframe}_{opposite_signal}"

        if opposite_key in self.cache:
            del self.cache[opposite_key]
            self.save_cache()
            logger.info(f"Cleared opposite signal: {opposite_key}")


# ============================================================================
# STOCHASTIC RSI CALCULATION
# ============================================================================

def calculate_rsi(src, length):
    """Calculate RSI using Wilder's smoothing (matches Pine Script ta.rsi)"""
    delta = src.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, min_periods=length, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_stoch(src, high, low, length):
    """Calculate Stochastic (matches Pine Script ta.stoch)"""
    lowest_low = low.rolling(window=length, min_periods=length).min()
    highest_high = high.rolling(window=length, min_periods=length).max()

    stoch = 100 * (src - lowest_low) / (highest_high - lowest_low)
    stoch = stoch.replace([np.inf, -np.inf], np.nan)
    return stoch


def calculate_stochastic_rsi(close_prices, length_rsi=14, length_stoch=14, smooth_k=3, smooth_d=3):
    """
    Calculate Stochastic RSI using exact Pine Script logic:
    rsi1 = ta.rsi(src, lengthRSI)
    k = ta.sma(ta.stoch(rsi1, rsi1, rsi1, lengthStoch), smoothK)
    d = ta.sma(k, smoothD)
    """
    try:
        src = pd.Series(close_prices)

        # Step 1: Calculate RSI
        rsi1 = calculate_rsi(src, length_rsi)

        # Step 2: Calculate Stochastic of RSI
        stoch_rsi = calculate_stoch(rsi1, rsi1, rsi1, length_stoch)

        # Step 3: Smooth to get K line
        k = stoch_rsi.rolling(window=smooth_k, min_periods=smooth_k).mean()

        # Step 4: Smooth K to get D line
        d = k.rolling(window=smooth_d, min_periods=smooth_d).mean()

        k_current = k.iloc[-1] if not pd.isna(k.iloc[-1]) else None
        d_current = d.iloc[-1] if not pd.isna(d.iloc[-1]) else None

        if k_current is None or d_current is None:
            return None

        return {
            'k': round(k_current, 2),
            'd': round(d_current, 2)
        }
    except Exception as e:
        logger.error(f"Error calculating Stochastic RSI: {e}")
        return None


def determine_signal(k_value, d_value, overbought=80, oversold=20):
    """Determine if in overbought or oversold zone"""
    if k_value >= overbought and d_value >= overbought:
        return 'OVERBOUGHT'
    elif k_value <= oversold and d_value <= oversold:
        return 'OVERSOLD'
    else:
        return 'NEUTRAL'


# ============================================================================
# EXCHANGE AND DATA FETCHING - MULTI-EXCHANGE SUPPORT
# ============================================================================

def get_exchange():
    """
    Initialize CCXT exchange with fallback support
    Tries exchanges in priority order: Bybit -> KuCoin -> OKX -> BingX
    """
    for exchange_name in config.EXCHANGE_PRIORITY:
        try:
            exchange_class = getattr(ccxt, exchange_name)
            exchange = exchange_class(config.EXCHANGE_OPTIONS)

            # Test the exchange by loading markets
            exchange.load_markets()
            logger.info(f"✓ Successfully initialized {exchange_name.upper()} exchange")
            return exchange

        except Exception as e:
            logger.warning(f"✗ Failed to initialize {exchange_name}: {e}")
            continue

    # If all exchanges fail
    raise Exception("Failed to initialize any exchange. Please check your internet connection.")


def normalize_symbol(symbol, exchange):
    """
    Normalize symbol format for the exchange
    Converts BTC/USDT to exchange-specific format
    """
    try:
        # Check if symbol exists in exchange markets
        if symbol in exchange.markets:
            return symbol

        # Try alternative formats
        base_symbol = symbol.replace('/', '').replace('USDT', '/USDT')
        if base_symbol in exchange.markets:
            return base_symbol

        # If still not found, return original
        return symbol
    except:
        return symbol


def fetch_ohlcv_data(exchange, symbol, timeframe, limit=100):
    """
    Fetch OHLCV data with error handling
    """
    try:
        # Normalize symbol for this exchange
        normalized_symbol = normalize_symbol(symbol, exchange)

        ohlcv = exchange.fetch_ohlcv(normalized_symbol, timeframe, limit=limit)

        if not ohlcv or len(ohlcv) == 0:
            logger.warning(f"No data for {symbol} {timeframe}")
            return None

        logger.debug(f"Fetched {len(ohlcv)} candles for {symbol} {timeframe}")
        return ohlcv

    except ccxt.BadSymbol as e:
        logger.warning(f"Symbol {symbol} not available on {exchange.id}: {e}")
        return None
    except ccxt.NetworkError as e:
        logger.error(f"Network error fetching {symbol} {timeframe}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching {symbol} {timeframe}: {e}")
        return None


# ============================================================================
# COIN LOADING
# ============================================================================

def load_coins():
    """
    Load coins from coins.txt (comma-separated format)
    Handles: ETHUSDT, BTCUSDT or ETH/USDT, BTC/USDT
    """
    try:
        with open(config.COINS_FILE, 'r') as f:
            content = f.read()

        # Split by comma and clean up
        coins = [coin.strip() for coin in content.split(',') if coin.strip()]

        # Convert to CCXT format (BTC/USDT)
        formatted_coins = []
        for coin in coins:
            if '/' not in coin:
                # Convert BTCUSDT to BTC/USDT
                if coin.endswith('USDT'):
                    formatted = coin[:-4] + '/USDT'
                else:
                    formatted = coin + '/USDT'
                formatted_coins.append(formatted)
            else:
                formatted_coins.append(coin)

        logger.info(f"Loaded {len(formatted_coins)} coins")
        return formatted_coins

    except Exception as e:
        logger.error(f"Error loading coins: {e}")
        return []


# ============================================================================
# ANALYSIS
# ============================================================================

def analyze_symbol(exchange, symbol, alert_manager):
    """Analyze a single symbol across multiple timeframes"""
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"Analyzing {symbol}")
        logger.info(f"{'='*60}")

        timeframe_data = {}

        for timeframe in config.TIMEFRAMES:
            logger.info(f"Fetching {timeframe} data for {symbol}...")

            ohlcv = fetch_ohlcv_data(exchange, symbol, timeframe, config.CANDLES_LIMIT)

            if not ohlcv or len(ohlcv) < config.MIN_CANDLES_REQUIRED:
                logger.warning(f"Insufficient data for {symbol} {timeframe}")
                continue

            close_prices = [candle[4] for candle in ohlcv]

            stoch_rsi = calculate_stochastic_rsi(
                close_prices,
                length_rsi=config.LENGTH_RSI,
                length_stoch=config.LENGTH_STOCH,
                smooth_k=config.SMOOTH_K,
                smooth_d=config.SMOOTH_D
            )

            if not stoch_rsi:
                logger.warning(f"Failed to calculate for {symbol} {timeframe}")
                continue

            k_value = stoch_rsi['k']
            d_value = stoch_rsi['d']
            signal = determine_signal(k_value, d_value, config.OVERBOUGHT_LEVEL, config.OVERSOLD_LEVEL)

            timeframe_data[timeframe] = {
                'k': k_value,
                'd': d_value,
                'status': signal
            }

            logger.info(f"{timeframe}: K={k_value:.2f}, D={d_value:.2f}, Status={signal}")

        # Check primary timeframe for alerts
        if config.PRIMARY_TIMEFRAME in timeframe_data:
            primary_data = timeframe_data[config.PRIMARY_TIMEFRAME]
            signal_type = primary_data['status']

            if signal_type in ['OVERBOUGHT', 'OVERSOLD']:
                if alert_manager.can_send_alert(symbol, config.PRIMARY_TIMEFRAME, signal_type):
                    logger.info(f"🔔 Sending {signal_type} alert for {symbol}")

                    success = send_telegram_alert(symbol, signal_type, timeframe_data, config.PRIMARY_TIMEFRAME)

                    if success:
                        alert_manager.record_alert(symbol, config.PRIMARY_TIMEFRAME, signal_type)
                        alert_manager.clear_opposite_signal(symbol, config.PRIMARY_TIMEFRAME, signal_type)
                else:
                    logger.info(f"⏳ Cooldown active for {symbol} {signal_type}")
            else:
                logger.info(f"✓ {symbol} is NEUTRAL")

        return True

    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        return False


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main execution function"""
    start_time = time.time()
    logger.info("\n" + "="*60)
    logger.info("STOCHASTIC RSI ALERTS SYSTEM - STARTING")
    logger.info("="*60)

    # Initialize exchange with fallback
    try:
        exchange = get_exchange()
        logger.info(f"Using exchange: {exchange.id.upper()}")
    except Exception as e:
        logger.error(f"Failed to initialize any exchange: {e}")
        return

    alert_manager = AlertManager()
    coins = load_coins()

    if not coins:
        logger.error("No coins loaded. Exiting.")
        return

    logger.info(f"Analyzing {len(coins)} coins across {len(config.TIMEFRAMES)} timeframes")
    logger.info(f"Parameters: RSI={config.LENGTH_RSI}, Stoch={config.LENGTH_STOCH}, K={config.SMOOTH_K}, D={config.SMOOTH_D}")
    logger.info(f"Primary Timeframe: {config.PRIMARY_TIMEFRAME}")

    # Analyze each coin
    success_count = 0
    for i, symbol in enumerate(coins, 1):
        logger.info(f"\nProcessing {i}/{len(coins)}: {symbol}")

        if analyze_symbol(exchange, symbol, alert_manager):
            success_count += 1

        # Rate limiting between symbols
        if i < len(coins):
            time.sleep(exchange.rateLimit / 1000)

    elapsed_time = time.time() - start_time
    logger.info("\n" + "="*60)
    logger.info("ANALYSIS COMPLETE")
    logger.info(f"Successfully analyzed: {success_count}/{len(coins)} coins")
    logger.info(f"Exchange used: {exchange.id.upper()}")
    logger.info(f"Time elapsed: {elapsed_time:.2f} seconds")
    logger.info("="*60)


if __name__ == "__main__":
    main()
