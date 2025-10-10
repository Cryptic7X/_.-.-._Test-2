# config.py
import os

TIMEFRAMES        = ['15m','1h','4h','1d']
PRIMARY_TIMEFRAME = '15m'

LENGTH_RSI        = 14
LENGTH_STOCH      = 14
SMOOTH_K          = 3
SMOOTH_D          = 3

OVERBOUGHT_LEVEL  = 80
OVERSOLD_LEVEL    = 20

COOLDOWN_PERIODS  = {'15m':15,'1h':60,'4h':240,'1d':1440}

EXCHANGE_PRIORITY = ['bybit','kucoin','okx','bingx']
EXCHANGE_OPTIONS  = {'enableRateLimit':True,'rateLimit':1200,'options':{'defaultType':'spot'}}

COINS_FILE        = 'coins.txt'

LOG_LEVEL         = 'INFO'
LOG_FORMAT        = '%(asctime)s - %(levelname)s - %(message)s'

TELEGRAM_BOT_TOKEN= os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID  = os.getenv('TELEGRAM_CHAT_ID')
