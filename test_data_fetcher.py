#!/usr/bin/env python3
"""
TEST: Standalone Data Fetcher for SMI Testing
No circular imports, clean CCXT implementation
"""

import ccxt
import pandas as pd
from typing import Optional, List

class TestDataFetcher:
    """Fetch OHLCV data with exchange fallback"""
    
    def __init__(self):
        self.exchanges = self._init_exchanges()
    
    def _init_exchanges(self) -> List[ccxt.Exchange]:
        """Initialize exchanges in fallback order"""
        exchanges = []
        
        try:
            exchanges.append(ccxt.bingx({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            }))
            print("✓ BingX initialized")
        except Exception as e:
            print(f"⚠️ BingX init failed: {e}")
        
        try:
            exchanges.append(ccxt.kucoin({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            }))
            print("✓ KuCoin initialized")
        except Exception as e:
            print(f"⚠️ KuCoin init failed: {e}")
        
        try:
            exchanges.append(ccxt.okx({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            }))
            print("✓ OKX initialized")
        except Exception as e:
            print(f"⚠️ OKX init failed: {e}")
        
        if not exchanges:
            raise Exception("No exchanges available!")
        
        return exchanges
    
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data and return as pandas DataFrame
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Candle timeframe ('15m', '1h', '4h')
            limit: Number of candles
        
        Returns:
            pandas DataFrame with OHLCV data or None
        """
        for exchange in self.exchanges:
            try:
                # Load markets
                if not exchange.markets:
                    exchange.load_markets()
                
                # Check symbol exists
                if symbol not in exchange.markets:
                    print(f"  ⏭️ {symbol} not on {exchange.id}")
                    continue
                
                # Fetch OHLCV
                ohlcv_list = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                
                if not ohlcv_list or len(ohlcv_list) < 50:
                    print(f"  ⏭️ Insufficient data from {exchange.id}")
                    continue
                
                # Convert to DataFrame
                df = pd.DataFrame(
                    ohlcv_list, 
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                df.set_index('timestamp', inplace=True)
                df = df.sort_index()
                
                print(f"  ✅ Fetched {len(df)} candles from {exchange.id}")
                return df
                    
            except Exception as e:
                print(f"  ✗ {exchange.id} error: {str(e)[:50]}")
                continue
        
        print(f"  ❌ Failed to fetch {symbol} from all exchanges")
        return None
