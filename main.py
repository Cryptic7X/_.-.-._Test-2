#!/usr/bin/env python3
"""
Simple Stochastic RSI Alerts System
"""
import sys
import os
import time
import json
import logging
from datetime import datetime, timedelta
import ccxt
import pandas as pd
import numpy as np
from utils.telegram_alert import send_telegram_alert
import config

# Setup logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL), format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)

class AlertManager:
    def __init__(self):
        self.cache_file = 'alert_cache.json'
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
                json.dump(self.cache, f)
        except:
            pass
    
    def can_send_alert(self, symbol, timeframe, signal_type):
        key = f"{symbol}_{timeframe}_{signal_type}"
        if key not in self.cache:
            return True
        last_time = datetime.fromisoformat(self.cache[key])
        cooldown = timedelta(minutes=config.COOLDOWN_PERIODS.get(timeframe, 15))
        return datetime.now() - last_time >= cooldown
    
    def record_alert(self, symbol, timeframe, signal_type):
        key = f"{symbol}_{timeframe}_{signal_type}"
        self.cache[key] = datetime.now().isoformat()
        self.save_cache()

def calculate_rsi(prices, period=14):
    """Simple RSI calculation"""
    df = pd.Series(prices)
    delta = df.diff()
    gain = delta.where(delta > 0, 0).ewm(span=period).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_stochastic_rsi(prices, rsi_period=14, stoch_period=14, k_smooth=3, d_smooth=3):
    """Calculate Stochastic RSI"""
    try:
        # Step 1: Calculate RSI
        rsi = calculate_rsi(prices, rsi_period)
        
        # Step 2: Calculate Stochastic of RSI
        rsi_df = pd.Series(rsi)
        lowest = rsi_df.rolling(stoch_period).min()
        highest = rsi_df.rolling(stoch_period).max()
        stoch = 100 * (rsi_df - lowest) / (highest - lowest)
        
        # Step 3: Smooth K and D
        k = stoch.rolling(k_smooth).mean()
        d = k.rolling(d_smooth).mean()
        
        k_val = k.iloc[-1]
        d_val = d.iloc[-1]
        
        if pd.isna(k_val) or pd.isna(d_val):
            return None
        
        return {'k': round(k_val, 2), 'd': round(d_val, 2)}
    except:
        return None

def get_exchange():
    """Initialize exchange"""
    for name in config.EXCHANGE_PRIORITY:
        try:
            exchange = getattr(ccxt, name)(config.EXCHANGE_OPTIONS)
            exchange.load_markets()
            logger.info(f"✓ Connected to {name.upper()}")
            return exchange
        except Exception as e:
            logger.warning(f"✗ {name} failed: {e}")
    raise Exception("All exchanges failed")

def load_coins():
    """Load coins from file"""
    try:
        with open(config.COINS_FILE, 'r') as f:
            content = f.read()
        
        coins = []
        for line in content.split('\n'):
            for coin in line.split(','):
                coin = coin.strip()
                if coin:
                    # Convert BTC to BTC/USDT format
                    if '/' not in coin:
                        coin = coin + '/USDT'
                    coins.append(coin)
        
        logger.info(f"Loaded {len(coins)} coins")
        return coins
    except Exception as e:
        logger.error(f"Error loading coins: {e}")
        return []

def analyze_symbol(exchange, symbol, alert_manager):
    """Analyze one symbol"""
    try:
        logger.info(f"\nAnalyzing {symbol}")
        
        # Check if symbol exists
        if symbol not in exchange.markets:
            logger.warning(f"❌ {symbol} not found on {exchange.id}")
            return False
        
        timeframe_data = {}
        
        for tf in config.TIMEFRAMES:
            try:
                # Fetch OHLCV data
                ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=100)
                if not ohlcv or len(ohlcv) < 50:
                    logger.warning(f"  {tf}: No data")
                    continue
                
                # Extract close prices
                closes = [candle[4] for candle in ohlcv]
                
                # Calculate Stochastic RSI
                result = calculate_stochastic_rsi(closes, config.LENGTH_RSI, config.LENGTH_STOCH, config.SMOOTH_K, config.SMOOTH_D)
                if not result:
                    logger.warning(f"  {tf}: Calc failed")
                    continue
                
                k, d = result['k'], result['d']
                
                # Determine signal
                if k >= config.OVERBOUGHT_LEVEL and d >= config.OVERBOUGHT_LEVEL:
                    signal = 'OVERBOUGHT'
                elif k <= config.OVERSOLD_LEVEL and d <= config.OVERSOLD_LEVEL:
                    signal = 'OVERSOLD'
                else:
                    signal = 'NEUTRAL'
                
                timeframe_data[tf] = {'k': k, 'd': d, 'status': signal}
                logger.info(f"  {tf}: K={k:.2f} D={d:.2f} {signal}")
                
            except Exception as e:
                logger.warning(f"  {tf}: Error - {e}")
        
        # Check for alerts
        if config.PRIMARY_TIMEFRAME in timeframe_data:
            data = timeframe_data[config.PRIMARY_TIMEFRAME]
            signal = data['status']
            
            if signal in ['OVERBOUGHT', 'OVERSOLD']:
                if alert_manager.can_send_alert(symbol, config.PRIMARY_TIMEFRAME, signal):
                    logger.info(f"🚨 ALERT: {symbol} {signal}")
                    success = send_telegram_alert(symbol, signal, timeframe_data, config.PRIMARY_TIMEFRAME)
                    if success:
                        alert_manager.record_alert(symbol, config.PRIMARY_TIMEFRAME, signal)
                else:
                    logger.info(f"⏳ Cooldown active")
            else:
                logger.info(f"✅ {symbol} NEUTRAL")
        
        return True
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        return False

def main():
    """Main function"""
    logger.info("="*50)
    logger.info("STOCHASTIC RSI ALERTS START")
    logger.info("="*50)
    
    try:
        exchange = get_exchange()
        alert_manager = AlertManager()
        coins = load_coins()
        
        if not coins:
            logger.error("No coins loaded")
            return
        
        logger.info(f"\nAnalyzing {len(coins)} coins...")
        
        success_count = 0
        for i, symbol in enumerate(coins, 1):
            logger.info(f"[{i}/{len(coins)}] {symbol}")
            
            if analyze_symbol(exchange, symbol, alert_manager):
                success_count += 1
            
            # Rate limit
            time.sleep(1.2)  # 1.2 seconds between requests
        
        logger.info("="*50)
        logger.info(f"COMPLETE: {success_count}/{len(coins)} analyzed")
        logger.info("="*50)
        
    except Exception as e:
        logger.error(f"Main error: {e}")

if __name__ == "__main__":
    main()
