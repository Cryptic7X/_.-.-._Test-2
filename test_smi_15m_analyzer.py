#!/usr/bin/env python3
"""
TEST: 15M SMI Crossover Analyzer
GitHub Actions Testing - No AWS
"""

import os
import sys
import requests
from datetime import datetime
from test_smi_indicator import TestSMI
from data_fetcher import DataFetcher

class Test15MAnalyzer:
    def __init__(self):
        self.smi = TestSMI(
            length_k=10,
            length_d=3,
            length_ema=3,
            overbought=40,
            oversold=-40
        )
        self.data_fetcher = DataFetcher()
        self.telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        self.test_coins = self.load_coins()
    
    def load_coins(self):
        """Load coins from coins.txt"""
        try:
            with open('coins.txt', 'r') as f:
                coins = [line.strip().upper() for line in f if line.strip() and not line.startswith('#')]
            print(f"📋 Loaded {len(coins)} test coins: {coins}")
            return coins
        except Exception as e:
            print(f"❌ Failed to load coins.txt: {e}")
            return []
    
    def analyze_coin(self, symbol):
        """Analyze single coin on 15M"""
        print(f"\n{'='*60}")
        print(f"🔍 Analyzing {symbol} on 15M")
        print(f"{'='*60}")
        
        try:
            # Fetch 15M data
            df = self.data_fetcher.fetch_ohlcv(symbol, '15m', limit=100)
            
            if df is None or len(df) < 30:
                print(f"  ❌ Insufficient data for {symbol}")
                return None
            
            print(f"  ✅ Fetched {len(df)} candles")
            print(f"  📅 Latest candle: {df.index[-1]}")
            
            # Analyze SMI
            result = self.smi.analyze_15m(
                df['high'].values,
                df['low'].values,
                df['close'].values,
                df.index
            )
            
            if not result:
                return None
            
            crosses = result.get('crosses', [])
            
            if not crosses:
                return None
            
            # Prepare alerts
            alerts = []
            for cross in crosses:
                price = float(df['close'].iloc[-1])
                
                alerts.append({
                    'symbol': symbol,
                    'cross_type': cross['cross_type'],
                    'candle_time': cross['candle_time'],
                    'k_prev': cross['k_prev'],
                    'd_prev': cross['d_prev'],
                    'k_curr': cross['k_curr'],
                    'd_curr': cross['d_curr'],
                    'k_at_cross': cross['k_at_cross'],
                    'price': price,
                    'bullish_cross': cross['bullish_cross']
                })
            
            return alerts
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def send_telegram(self, alerts):
        """Send alerts to Telegram"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            print("⚠️ Telegram credentials missing, skipping send")
            return False
        
        msg = "🧪 **TEST: 15M SMI CROSSOVER** 🧪\n"
        msg += f"⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, alert in enumerate(alerts, 1):
            symbol = alert['symbol']
            cross_type = alert['cross_type']
            candle_time = alert['candle_time']
            price = alert['price']
            k_prev = alert['k_prev']
            d_prev = alert['d_prev']
            k_curr = alert['k_curr']
            d_curr = alert['d_curr']
            k_at_cross = alert['k_at_cross']
            
            emoji = '🟢' if cross_type == 'OVERSOLD' else '🔴'
            cross_dir = '↗️' if alert['bullish_cross'] else '↘️'
            
            msg += f"{i}. {emoji} **{symbol}** - {cross_type}\n"
            msg += f"   💰 Price: ${price:.4f}\n"
            msg += f"   {cross_dir} Cross @ {candle_time.strftime('%H:%M UTC')}\n"
            msg += f"   📊 Previous: %K={k_prev:.2f} %D={d_prev:.2f}\n"
            msg += f"   📊 Current: %K={k_curr:.2f} %D={d_curr:.2f}\n"
            msg += f"   📊 At Cross: %K≈{k_at_cross:.2f}\n"
            
            tv_url = f"https://www.tradingview.com/chart/?symbol=BINANCE:{symbol}USDT&interval=15"
            msg += f"   📊 [15M Chart]({tv_url})\n\n"
        
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"Total Crosses: {len(alerts)}\n"
        msg += "🧪 GitHub Actions Test\n"
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': msg,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            print(f"\n✅ Telegram sent successfully")
            return True
            
        except Exception as e:
            print(f"\n❌ Telegram failed: {e}")
            return False
    
    def run(self):
        """Run test analysis"""
        print(f"\n{'#'*60}")
        print(f"# TEST: 15M SMI CROSSOVER DETECTION")
        print(f"# Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"{'#'*60}\n")
        
        if not self.test_coins:
            print("❌ No test coins loaded")
            return
        
        all_alerts = []
        
        for symbol in self.test_coins:
            alerts = self.analyze_coin(symbol)
            if alerts:
                all_alerts.extend(alerts)
        
        print(f"\n{'='*60}")
        print(f"📊 SUMMARY")
        print(f"{'='*60}")
        print(f"Coins analyzed: {len(self.test_coins)}")
        print(f"Crosses found: {len(all_alerts)}")
        
        if all_alerts:
            print(f"\n📨 Sending {len(all_alerts)} alerts to Telegram...")
            self.send_telegram(all_alerts)
        else:
            print(f"\nℹ️ No crossovers detected in any coin")
        
        print(f"\n{'#'*60}")
        print(f"# TEST COMPLETE")
        print(f"{'#'*60}\n")


if __name__ == '__main__':
    analyzer = Test15MAnalyzer()
    analyzer.run()
