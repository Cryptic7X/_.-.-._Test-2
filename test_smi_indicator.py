#!/usr/bin/env python3
"""
TEST: Stochastic Momentum Index with Debug Logging
15M Crossover Detection - Last 2 candles + current running
"""

import numpy as np
import pandas as pd
from datetime import datetime

class TestSMI:
    def __init__(self, length_k=10, length_d=3, length_ema=3, 
                 overbought=40, oversold=-40):
        """Initialize SMI for testing"""
        self.length_k = length_k
        self.length_d = length_d
        self.length_ema = length_ema
        self.overbought = overbought
        self.oversold = oversold
        
        print(f"🔧 SMI Config: K={length_k}, D={length_d}, EMA={length_ema}, OB={overbought}, OS={oversold}")
    
    def ema(self, series, length):
        """EMA - Pine Script ta.ema()"""
        return pd.Series(series).ewm(span=length, adjust=False).mean().values
    
    def ema_ema(self, series, length):
        """Double EMA - Pine Script emaEma()"""
        first_ema = self.ema(series, length)
        second_ema = self.ema(first_ema, length)
        return second_ema
    
    def calculate_smi(self, high, low, close):
        """Calculate SMI %K and %D"""
        high_series = pd.Series(high)
        low_series = pd.Series(low)
        close_series = pd.Series(close)
        
        highest_high = high_series.rolling(window=self.length_k).max()
        lowest_low = low_series.rolling(window=self.length_k).min()
        
        highest_lowest_range = highest_high - lowest_low
        relative_range = close_series - (highest_high + lowest_low) / 2
        
        numerator = self.ema_ema(relative_range.values, self.length_d)
        denominator = self.ema_ema(highest_lowest_range.values, self.length_d)
        
        smi_k = np.zeros_like(close)
        valid = denominator != 0
        smi_k[valid] = 200 * (numerator[valid] / denominator[valid])
        
        smi_d = self.ema(smi_k, self.length_ema)
        
        return smi_k, smi_d
    
    def detect_cross_in_candle(self, k_prev, d_prev, k_curr, d_curr, candle_time):
        """Detect crossover in single candle with debug output"""
        if np.isnan(k_prev) or np.isnan(d_prev) or np.isnan(k_curr) or np.isnan(d_curr):
            return None
        
        # Detect cross
        bullish_cross = (k_prev <= d_prev) and (k_curr > d_curr)
        bearish_cross = (k_prev >= d_prev) and (k_curr < d_curr)
        
        if not bullish_cross and not bearish_cross:
            return None
        
        # Check zone at cross point
        k_at_cross = (k_prev + k_curr) / 2
        in_oversold = k_at_cross <= self.oversold
        in_overbought = k_at_cross >= self.overbought
        
        cross_type = None
        if bullish_cross and in_oversold:
            cross_type = 'OVERSOLD'
        elif bearish_cross and in_overbought:
            cross_type = 'OVERBOUGHT'
        
        if not cross_type:
            return None
        
        # Debug output
        print(f"    ✅ CROSS DETECTED @ {candle_time}")
        print(f"       Type: {'Bullish' if bullish_cross else 'Bearish'} in {cross_type}")
        print(f"       Prev: %K={k_prev:.2f} %D={d_prev:.2f}")
        print(f"       Curr: %K={k_curr:.2f} %D={d_curr:.2f}")
        print(f"       At Cross: %K≈{k_at_cross:.2f}")
        
        return {
            'cross_type': cross_type,
            'bullish_cross': bullish_cross,
            'bearish_cross': bearish_cross,
            'k_prev': k_prev,
            'd_prev': d_prev,
            'k_curr': k_curr,
            'd_curr': d_curr,
            'k_at_cross': k_at_cross,
            'candle_time': candle_time
        }
    
    def analyze_15m(self, high, low, close, timestamps):
        """
        Analyze 15M with last 2 closed + current running candle
        """
        if len(close) < self.length_k + self.length_d + self.length_ema + 10:
            print(f"  ⚠️ Not enough data: {len(close)} candles")
            return None
        
        # Calculate SMI
        smi_k, smi_d = self.calculate_smi(high, low, close)
        
        valid_indices = np.where(~np.isnan(smi_k) & ~np.isnan(smi_d))[0]
        if len(valid_indices) == 0:
            print(f"  ⚠️ No valid SMI values")
            return None
        
        latest_idx = valid_indices[-1]
        
        print(f"  📊 Latest values: %K={smi_k[latest_idx]:.2f} %D={smi_d[latest_idx]:.2f}")
        
        # Check last 3 candles (2 closed + 1 current)
        crosses = []
        lookback = 3
        
        print(f"  🔍 Checking last {lookback} candles for crosses...")
        
        for i in range(max(1, latest_idx - lookback + 1), latest_idx + 1):
            if i >= len(smi_k):
                continue
            
            k_prev = smi_k[i - 1]
            d_prev = smi_d[i - 1]
            k_curr = smi_k[i]
            d_curr = smi_d[i]
            
            candle_time = timestamps[i] if isinstance(timestamps, pd.DatetimeIndex) else pd.Timestamp(timestamps[i])
            
            print(f"    Candle {i} @ {candle_time}: %K={k_curr:.2f} %D={d_curr:.2f}")
            
            cross_info = self.detect_cross_in_candle(k_prev, d_prev, k_curr, d_curr, candle_time)
            
            if cross_info:
                crosses.append(cross_info)
        
        if crosses:
            print(f"  ✅ Found {len(crosses)} crossover(s)")
        else:
            print(f"  ℹ️ No crossovers detected")
        
        return {
            'smi_k': smi_k,
            'smi_d': smi_d,
            'latest_k': smi_k[latest_idx],
            'latest_d': smi_d[latest_idx],
            'crosses': crosses
        }
