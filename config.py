"""
Configuration file for Stochastic RSI Alerts System
All parameters are adjustable here
"""

# Stochastic RSI Parameters (matching Pine Script)
SMOOTH_K = 3
SMOOTH_D = 3
LENGTH_RSI = 14
LENGTH_STOCH = 14

# Timeframes to analyze
TIMEFRAMES = ['15m', '1h', '4h', '1d']
PRIMARY_TIMEFRAME = '15m'  # The main timeframe for alerts

# Alert Zones
OVERBOUGHT_LEVEL = 80
OVERSOLD_LEVEL = 20

# Cooldown Configuration (in minutes)
# Cooldown period after alert is sent before next alert can be triggered
COOLDOWN_PERIODS = {
    '15m': 15,   # 15 minutes cooldown for 15m timeframe
    '1h': 60,    # 60 minutes cooldown for 1h timeframe
    '4h': 240,   # 240 minutes cooldown for 4h timeframe
    '1d': 1440   # 1440 minutes (1 day) cooldown for daily timeframe
}

# Exchange Configuration
EXCHANGE_NAME = 'binance'  # Can be changed to 'bybit', 'okx', 'bingx', etc.
EXCHANGE_OPTIONS = {
    'enableRateLimit': True,
    'rateLimit': 1200
}

# Data Fetching
CANDLES_LIMIT = 100  # Number of candles to fetch for calculation
MIN_CANDLES_REQUIRED = 50  # Minimum candles needed for accurate calculation

# Telegram Configuration (loaded from environment variables)
import os
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# File Paths
COINS_FILE = 'coins.txt'
CACHE_FILE = 'alert_cache.json'

# Logging
LOG_LEVEL = 'INFO'  # Can be DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
