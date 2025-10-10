import ccxt
import time
from typing import List, Dict, Optional

class DataFetcher:
    """Fetch OHLCV data with exchange fallback: BingX → KuCoin → OKX"""
    
    def __init__(self):
        self.exchanges = self._init_exchanges()
        self.current_exchange = None
    
    def _init_exchanges(self) -> List[ccxt.Exchange]:
        """Initialize exchanges in fallback order"""
        exchanges = []
        
        try:
            exchanges.append(ccxt.bingx({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            }))
        except Exception as e:
            print(f"Warning: BingX init failed: {e}")
        
        try:
            exchanges.append(ccxt.kucoin({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            }))
        except Exception as e:
            print(f"Warning: KuCoin init failed: {e}")
        
        try:
            exchanges.append(ccxt.okx({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            }))
        except Exception as e:
            print(f"Warning: OKX init failed: {e}")
        
        return exchanges
    
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> Optional[List]:
        """
        Fetch OHLCV data with automatic exchange fallback
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Candle timeframe ('15m', '1h', '4h', '1d')
            limit: Number of candles to fetch
        
        Returns:
            List of OHLCV data or None if all exchanges fail
        """
        for exchange in self.exchanges:
            try:
                # Load markets if not already loaded
                if not exchange.markets:
                    exchange.load_markets()
                
                # Check if symbol exists
                if symbol not in exchange.markets:
                    print(f"Symbol {symbol} not available on {exchange.id}, trying next...")
                    continue
                
                # Fetch OHLCV
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                
                if ohlcv and len(ohlcv) >= 50:
                    self.current_exchange = exchange.id
                    print(f"✓ Fetched {len(ohlcv)} candles for {symbol} {timeframe} from {exchange.id}")
                    return ohlcv
                else:
                    print(f"Insufficient data from {exchange.id}, trying next...")
                    continue
                    
            except Exception as e:
                print(f"Error fetching {symbol} from {exchange.id}: {str(e)}")
                continue
        
        print(f"✗ Failed to fetch {symbol} {timeframe} from all exchanges")
        return None
    
    def fetch_ticker(self, symbol: str) -> Optional[Dict]:
        """Fetch current price and 24h change"""
        for exchange in self.exchanges:
            try:
                if not exchange.markets:
                    exchange.load_markets()
                
                if symbol in exchange.markets:
                    ticker = exchange.fetch_ticker(symbol)
                    return {
                        'price': ticker.get('last'),
                        'change_24h': ticker.get('percentage', 0)
                    }
            except Exception as e:
                print(f"Error fetching ticker for {symbol} from {exchange.id}: {e}")
                continue
        
        return None
    
    def fetch_multi_timeframe_data(self, symbol: str, timeframes: List[str]) -> Dict:
        """
        Fetch OHLCV data for multiple timeframes
        
        Returns:
            Dict: {timeframe: ohlcv_data or None}
        """
        results = {}
        
        for tf in timeframes:
            results[tf] = self.fetch_ohlcv(symbol, tf, limit=100)
            time.sleep(0.1)  # Rate limiting
        
        return results
