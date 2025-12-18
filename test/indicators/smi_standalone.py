#!/usr/bin/env python3
"""
Standalone SMI for GitHub Actions Testing
No AWS/DynamoDB - uses JSON file for state tracking
"""

import numpy as np
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

class SMIStandalone:
    def __init__(self, length_k=10, length_d=3, length_ema=3, 
                 overbought=40, oversold=-40, state_file='smi_state.json'):
        """15M SMI with file-based state"""
        self.length_k = length_k
        self.length_d = length_d
        self.length_ema = length_ema
        self.overbought = overbought
        self.oversold = oversold
        self.state_file = state_file
        self.freshness_minutes = 90
        
        # Load state from file
        self.state = self.load_state()
    
    def load_state(self):
        """Load state from JSON file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    print(f"📂 Loaded state: {len(state)} entries")
                    return state
            except Exception as e:
                print(f"⚠️ Failed to load state: {e}")
        return {}
    
    def save_state(self):
        """Save state to JSON file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            print(f"💾 State saved")
        except Exception as e:
            print(f"⚠️ Failed to save state: {e}")
    
    def ema(self, series, length):
        """EMA calculation"""
        return pd.Series(series).ewm(span=length, adjust=False).mean().values
    
    def ema_ema(self, series, length):
        """Double EMA"""
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
    
    def detect_cross_detailed(self, k_prev, d_prev, k_curr, d_curr, candle_index, candle_time):
        """Detect crossover with detailed logging"""
        print(f"\n  🔍 Checking Candle #{candle_index} @ {candle_time}")
        print(f"     Previous: %K={k_prev:.2f} %D={d_prev:.2f}")
        print(f"     Current:  %K={k_curr:.2f} %D={d_curr:.2f}")
        
        if np.isnan(k_prev) or np.isnan(d_prev) or np.isnan(k_curr) or np.isnan(d_curr):
            print(f"     ⚠️ NaN values detected, skipping")
            return None
        
        # Detect crossovers
        bullish_cross = (k_prev <= d_prev) and (k_curr > d_curr)
        bearish_cross = (k_prev >= d_prev) and (k_curr < d_curr)
        
        if not bullish_cross and not bearish_cross:
            print(f"     ❌ No crossover detected")
            return None
        
        # Cross point approximation
        k_at_cross = (k_prev + k_curr) / 2
        
        print(f"     ✅ Crossover detected!")
        print(f"        Type: {'BULLISH (%K crossed above %D)' if bullish_cross else 'BEARISH (%K crossed below %D)'}")
        print(f"        Approximate %K at cross: {k_at_cross:.2f}")
        
        # Check zones
        in_oversold = k_at_cross <= self.oversold
        in_overbought = k_at_cross >= self.overbought
        
        print(f"        Zone check: OB={in_overbought} (>{self.overbought}) | OS={in_oversold} (<{self.oversold})")
        
        if bullish_cross and in_oversold:
            print(f"     🟢 VALID OVERSOLD SIGNAL!")
            return {
                'cross_type': 'OVERSOLD',
                'bullish_cross': True,
                'k_prev': k_prev,
                'd_prev': d_prev,
                'k_curr': k_curr,
                'd_curr': d_curr,
                'k_at_cross': k_at_cross,
                'valid': True
            }
        
        if bearish_cross and in_overbought:
            print(f"     🔴 VALID OVERBOUGHT SIGNAL!")
            return {
                'cross_type': 'OVERBOUGHT',
                'bearish_cross': True,
                'k_prev': k_prev,
                'd_prev': d_prev,
                'k_curr': k_curr,
                'd_curr': d_curr,
                'k_at_cross': k_at_cross,
                'valid': True
            }
        
        print(f"     ⚠️ Crossover detected but NOT in extreme zone")
        return None
    
    def check_last_3_candles(self, smi_k, smi_d, timestamps):
        """Check last 2 closed + 1 current running candle"""
        n = len(smi_k)
        crosses = []
        
        print(f"\n📊 Checking Last 3 Candles:")
        print(f"   Total candles available: {n}")
        
        if n < 3:
            print(f"   ⚠️ Not enough candles (need at least 3)")
            return crosses
        
        # Check last 3 candles
        for i in range(max(1, n - 2), n):
            candle_ts = timestamps[i] if isinstance(timestamps, pd.DatetimeIndex) else pd.Timestamp(timestamps[i])
            
            cross_info = self.detect_cross_detailed(
                smi_k[i-1], smi_d[i-1],
                smi_k[i], smi_d[i],
                i, candle_ts
            )
            
            if cross_info:
                crosses.append({
                    'candle_index': i,
                    'candle_timestamp': candle_ts,
                    'cross_info': cross_info
                })
        
        return crosses
    
    def check_cooldown(self, symbol, signal_type, candle_timestamp):
        """Check cooldown using in-memory state"""
        ts_str = candle_timestamp.strftime('%Y-%m-%dT%H:%M:00')
        state_key = f"{symbol}_15M_{signal_type}_{ts_str}"
        
        print(f"\n  🔒 Cooldown Check: {state_key}")
        
        # Check exact candle
        if state_key in self.state:
            print(f"     ❌ Already alerted for this candle")
            return False
        
        # Check freshness window
        now = datetime.utcnow()
        prefix = f"{symbol}_15M_{signal_type}"
        
        for key, value in list(self.state.items()):
            if key.startswith(prefix):
                last_alert = datetime.fromisoformat(value['last_alert_time'])
                minutes_passed = (now - last_alert).total_seconds() / 60
                
                if minutes_passed < self.freshness_minutes:
                    remaining = self.freshness_minutes - minutes_passed
                    print(f"     ⏳ In freshness window ({remaining:.0f} min remaining)")
                    return False
        
        print(f"     ✅ Allowed to send")
        return True
    
    def update_cooldown(self, symbol, signal_type, candle_timestamp):
        """Update cooldown state"""
        ts_str = candle_timestamp.strftime('%Y-%m-%dT%H:%M:00')
        state_key = f"{symbol}_15M_{signal_type}_{ts_str}"
        
        self.state[state_key] = {
            'symbol': symbol,
            'signal_type': signal_type,
            'candle_timestamp': ts_str,
            'last_alert_time': datetime.utcnow().isoformat()
        }
        
        # Cleanup old entries (older than 7 days)
        now = datetime.utcnow()
        cleanup_keys = []
        for key, value in self.state.items():
            last_time = datetime.fromisoformat(value['last_alert_time'])
            if (now - last_time).days > 7:
                cleanup_keys.append(key)
        
        for key in cleanup_keys:
            del self.state[key]
        
        self.save_state()
        print(f"  ✅ Cooldown updated")
    
    def analyze(self, high, low, close, timestamps, symbol):
        """Analyze with detailed logging"""
        print(f"\n{'='*60}")
        print(f"🔬 SMI 15M Analysis: {symbol}")
        print(f"{'='*60}")
        
        if len(close) < self.length_k + self.length_d + self.length_ema + 10:
            print(f"❌ Not enough data: {len(close)} candles")
            return None
        
        # Calculate SMI
        smi_k, smi_d = self.calculate_smi(high, low, close)
        
        # Latest values
        latest_k = smi_k[-1]
        latest_d = smi_d[-1]
        
        print(f"\n📈 Latest SMI Values:")
        print(f"   %K: {latest_k:.2f}")
        print(f"   %D: {latest_d:.2f}")
        print(f"   Zone: {'OVERBOUGHT' if latest_k >= self.overbought else 'OVERSOLD' if latest_k <= self.oversold else 'NEUTRAL'}")
        
        # Check last 3 candles
        crosses = self.check_last_3_candles(smi_k, smi_d, timestamps)
        
        if not crosses:
            print(f"\n❌ No valid crossovers found")
            return None
        
        print(f"\n✅ Found {len(crosses)} valid crossover(s)")
        
        # Check cooldown
        valid_crosses = []
        for cross_data in crosses:
            cross_info = cross_data['cross_info']
            candle_ts = cross_data['candle_timestamp']
            signal_type = cross_info['cross_type']
            
            if self.check_cooldown(symbol, signal_type, candle_ts):
                self.update_cooldown(symbol, signal_type, candle_ts)
                valid_crosses.append(cross_data)
        
        if not valid_crosses:
            print(f"\n⏭️ All crossovers in cooldown")
            return None
        
        return {
            'smi_k': smi_k,
            'smi_d': smi_d,
            'latest_k': latest_k,
            'latest_d': latest_d,
            'crosses': valid_crosses
        }
