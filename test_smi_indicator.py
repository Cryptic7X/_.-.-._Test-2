#!/usr/bin/env python3
"""
TEST: SMI - 100% Exact Pine Script Match
Fixes calculation discrepancies
"""

import numpy as np
import pandas as pd
from datetime import datetime

class TestSMI:
    def __init__(self, length_k=10, length_d=3, length_ema=3, 
                 overbought=40, oversold=-40):
        """Initialize SMI - EXACT Pine Script parameters"""
        self.length_k = length_k
        self.length_d = length_d
        self.length_ema = length_ema
        self.overbought = overbought
        self.oversold = oversold
        
        print(f"🔧 SMI Config: K={length_k}, D={length_d}, EMA={length_ema}, OB={overbought}, OS={oversold}")
    
    def ema(self, series, length):
        """
        EMA - EXACT Pine Script ta.ema()
        Uses pandas ewm with adjust=False to match Pine Script
        """
        return pd.Series(series).ewm(span=length, adjust=False).mean().values
    
    def ema_ema(self, series, length):
        """
        Double EMA - EXACT Pine Script emaEma()
        emaEma(source, length) => ta.ema(ta.ema(source, length), length)
        """
        first_ema = self.ema(series, length)
        second_ema = self.ema(first_ema, length)
        return second_ema
    
    def calculate_smi(self, high, low, close):
        """
        Calculate SMI - 100% EXACT Pine Script Formula
        
        Pine Script:
        highestHigh = ta.highest(lengthK)              // uses 'high' series
        lowestLow = ta.lowest(lengthK)                 // uses 'low' series  
        highestLowestRange = highestHigh - lowestLow
        relativeRange = close - (highestHigh + lowestLow) / 2
        smi = 200 * (emaEma(relativeRange, lengthD) / emaEma(highestLowestRange, lengthD))
        """
        # Convert to pandas Series for rolling calculations
        high_series = pd.Series(high)
        low_series = pd.Series(low)
        close_series = pd.Series(close)
        
        # CRITICAL: Pine Script ta.highest/ta.lowest include current bar
        # pandas rolling(N) includes current + previous (N-1) bars ✓
        highest_high = high_series.rolling(window=self.length_k, min_periods=self.length_k).max()
        lowest_low = low_series.rolling(window=self.length_k, min_periods=self.length_k).min()
        
        # Calculate ranges
        highest_lowest_range = highest_high - lowest_low
        relative_range = close_series - (highest_high + lowest_low) / 2
        
        # Double EMA smoothing
        numerator = self.ema_ema(relative_range.values, self.length_d)
        denominator = self.ema_ema(highest_lowest_range.values, self.length_d)
        
        # SMI calculation (%K)
        smi_k = np.full_like(close, np.nan, dtype=float)
        
        # Only calculate where denominator is valid and non-zero
        valid_mask = (~np.isnan(denominator)) & (np.abs(denominator) > 1e-10)
        smi_k[valid_mask] = 200 * (numerator[valid_mask] / denominator[valid_mask])
        
        # %D = EMA of %K (signal line)
        smi_d = self.ema(smi_k, self.length_ema)
        
        return smi_k, smi_d
    
    def detect_cross_in_candle(self, k_prev, d_prev, k_curr, d_curr, candle_time):
        """Detect crossover with detailed debug output"""
        if np.isnan(k_prev) or np.isnan(d_prev) or np.isnan(k_curr) or np.isnan(d_curr):
            return None
        
        # Bullish cross: %K crosses above %D
        bullish_cross = (k_prev <= d_prev) and (k_curr > d_curr)
        
        # Bearish cross: %K crosses below %D
        bearish_cross = (k_prev >= d_prev) and (k_curr < d_curr)
        
        if not bullish_cross and not bearish_cross:
            return None
        
        # Check zone at cross point (average of prev and current)
        k_at_cross = (k_prev + k_curr) / 2
        in_oversold = k_at_cross <= self.oversold
        in_overbought = k_at_cross >= self.overbought
        
        cross_type = None
        if bullish_cross and in_oversold:
            cross_type = 'OVERSOLD'
        elif bearish_cross and in_overbought:
            cross_type = 'OVERBOUGHT'
        
        if not cross_type:
            print(f"    ⏭️ Cross @ {candle_time} but NOT in OB/OS zone (K≈{k_at_cross:.2f})")
            return None
        
        # Debug output
        print(f"    ✅ CROSS DETECTED @ {candle_time}")
        print(f"       Type: {'Bullish ↗️' if bullish_cross else 'Bearish ↘️'} in {cross_type}")
        print(f"       Prev: %K={k_prev:.2f} %D={d_prev:.2f}")
        print(f"       Curr: %K={k_curr:.2f} %D={d_curr:.2f}")
        print(f"       @Cross: %K≈{k_at_cross:.2f}")
        
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
    
    def find_latest_cross(self, smi_k, smi_d, timestamps):
        """
        Priority-based cross detection:
        1. Check current/running candle first
        2. Check previous candle if current has no cross
        
        Returns: Single most recent cross or None
        """
        n = len(smi_k)
        
        if n < 2:
            print(f"  ⚠️ Not enough data points: {n}")
            return None
        
        print(f"  🔍 Checking last 2 candles for crosses...")
        
        # Priority 1: Current/running candle (index -1)
        current_idx = n - 1
        if current_idx >= 1:
            k_prev = smi_k[current_idx - 1]
            d_prev = smi_d[current_idx - 1]
            k_curr = smi_k[current_idx]
            d_curr = smi_d[current_idx]
            candle_time = timestamps[current_idx]
            
            print(f"    Candle {current_idx} (CURRENT) @ {candle_time}: %K={k_curr:.2f} %D={d_curr:.2f}")
            
            cross = self.detect_cross_in_candle(k_prev, d_prev, k_curr, d_curr, candle_time)
            
            if cross:
                return {
                    'candle_index': current_idx,
                    'candle_timestamp': candle_time,
                    'cross_info': cross
                }
        
        # Priority 2: Previous candle (index -2)
        prev_idx = n - 2
        if prev_idx >= 1:
            k_prev = smi_k[prev_idx - 1]
            d_prev = smi_d[prev_idx - 1]
            k_curr = smi_k[prev_idx]
            d_curr = smi_d[prev_idx]
            candle_time = timestamps[prev_idx]
            
            print(f"    Candle {prev_idx} (PREVIOUS) @ {candle_time}: %K={k_curr:.2f} %D={d_curr:.2f}")
            
            cross = self.detect_cross_in_candle(k_prev, d_prev, k_curr, d_curr, candle_time)
            
            if cross:
                return {
                    'candle_index': prev_idx,
                    'candle_timestamp': candle_time,
                    'cross_info': cross
                }
        
        print(f"    ℹ️ No crosses in last 2 candles")
        return None
    
    def analyze_15m(self, high, low, close, timestamps):
        """
        Analyze 15M with Priority-based cross detection
        Returns latest cross only (no duplicates)
        """
        if len(close) < self.length_k + self.length_d + self.length_ema + 10:
            print(f"  ⚠️ Not enough data: {len(close)} candles (need {self.length_k + self.length_d + self.length_ema + 10})")
            return None
        
        # Calculate SMI
        print(f"  📊 Calculating SMI...")
        smi_k, smi_d = self.calculate_smi(high, low, close)
        
        # Find valid indices
        valid_indices = np.where(~np.isnan(smi_k) & ~np.isnan(smi_d))[0]
        if len(valid_indices) == 0:
            print(f"  ⚠️ No valid SMI values")
            return None
        
        latest_idx = valid_indices[-1]
        latest_k = smi_k[latest_idx]
        latest_d = smi_d[latest_idx]
        
        print(f"  📊 Latest SMI: %K={latest_k:.2f} %D={latest_d:.2f}")
        print(f"  📊 TradingView should show: %K≈{latest_k:.2f} %D≈{latest_d:.2f}")
        
        # Find latest cross (Priority: current, then previous)
        cross_data = self.find_latest_cross(smi_k, smi_d, timestamps)
        
        if cross_data:
            print(f"  ✅ Found crossover")
            return {
                'smi_k': smi_k,
                'smi_d': smi_d,
                'latest_k': latest_k,
                'latest_d': latest_d,
                'cross': cross_data
            }
        else:
            print(f"  ℹ️ No crossover detected")
            return {
                'smi_k': smi_k,
                'smi_d': smi_d,
                'latest_k': latest_k,
                'latest_d': latest_d,
                'cross': None
            }
