"""
CCXT Exchange Client Wrapper
"""
import ccxt
from config import EXCHANGE_NAME, EXCHANGE_OPTIONS
from utils.logging_setup import setup_logger

logger = setup_logger(__name__)


def get_exchange():
    """
    Initialize and return CCXT exchange instance

    Returns:
        CCXT exchange object
    """
    try:
        exchange_class = getattr(ccxt, EXCHANGE_NAME)
        exchange = exchange_class(EXCHANGE_OPTIONS)
        logger.info(f"Initialized {EXCHANGE_NAME} exchange")
        return exchange
    except Exception as e:
        logger.error(f"Error initializing exchange: {e}")
        raise


def fetch_ohlcv_data(exchange, symbol, timeframe, limit=100):
    """
    Fetch OHLCV data for a symbol and timeframe

    Args:
        exchange: CCXT exchange instance
        symbol: Trading pair (e.g., 'BTC/USDT')
        timeframe: Timeframe string (e.g., '15m', '1h', '4h', '1d')
        limit: Number of candles to fetch

    Returns:
        List of OHLCV data or None on error
    """
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not ohlcv or len(ohlcv) == 0:
            logger.warning(f"No data returned for {symbol} {timeframe}")
            return None

        logger.debug(f"Fetched {len(ohlcv)} candles for {symbol} {timeframe}")
        return ohlcv

    except Exception as e:
        logger.error(f"Error fetching OHLCV for {symbol} {timeframe}: {e}")
        return None
