import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List

class SignalDetector:
    """Detect overbought/oversold signals with cooldown management"""
    
    def __init__(self, cooldown_file='data/cooldowns.json', cooldown_hours=4):
        self.cooldown_file = cooldown_file
        self.cooldown_hours = cooldown_hours
        self.cooldowns = self._load_cooldowns()
    
    def _load_cooldowns(self) -> Dict:
        """Load cooldown data from JSON file"""
        os.makedirs(os.path.dirname(self.cooldown_file), exist_ok=True)
        
        if os.path.exists(self.cooldown_file):
            try:
                with open(self.cooldown_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_cooldowns(self):
        """Save cooldown data to JSON file"""
        with open(self.cooldown_file, 'w') as f:
            json.dump(self.cooldowns, f, indent=2)
    
    def classify_signal(self, k_value: float, d_value: float) -> str:
        """
        Classify signal based on %K and %D thresholds
        
        Returns: 'OVERBOUGHT', 'OVERSOLD', or 'NEUTRAL'
        """
        if k_value is None or d_value is None:
            return 'NEUTRAL'
        
        # Overbought: either %K or %D above 80
        if k_value > 80 or d_value > 80:
            return 'OVERBOUGHT'
        
        # Oversold: either %K or %D below 20
        if k_value < 20 or d_value < 20:
            return 'OVERSOLD'
        
        return 'NEUTRAL'
    
    def check_cooldown(self, symbol: str, signal_type: str) -> bool:
        """
        Check if symbol is in cooldown period
        
        Returns: True if can send alert, False if in cooldown
        """
        cooldown_key = f"{symbol}_{signal_type}"
        
        if cooldown_key in self.cooldowns:
            last_alert_time = datetime.fromisoformat(self.cooldowns[cooldown_key])
            cooldown_end = last_alert_time + timedelta(hours=self.cooldown_hours)
            
            if datetime.now() < cooldown_end:
                remaining = (cooldown_end - datetime.now()).total_seconds() / 60
                print(f"  ⏳ {symbol} {signal_type} in cooldown ({remaining:.0f}min remaining)")
                return False
        
        return True
    
    def update_cooldown(self, symbol: str, signal_type: str):
        """Record new alert timestamp"""
        cooldown_key = f"{symbol}_{signal_type}"
        self.cooldowns[cooldown_key] = datetime.now().isoformat()
        self._save_cooldowns()
    
    def should_send_alert(self, symbol: str, base_tf_signal: str) -> bool:
        """
        Determine if alert should be sent based on 15m timeframe signal
        
        Args:
            symbol: Trading pair
            base_tf_signal: Signal from 15m timeframe ('OVERBOUGHT', 'OVERSOLD', 'NEUTRAL')
        
        Returns: True if alert should be sent
        """
        # Only send alerts for OVERBOUGHT or OVERSOLD on base timeframe
        if base_tf_signal == 'NEUTRAL':
            return False
        
        # Check cooldown
        return self.check_cooldown(symbol, base_tf_signal)
