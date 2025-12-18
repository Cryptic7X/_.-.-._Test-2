#!/usr/bin/env python3
"""
SMI 15M Test Analyzer - BTC Only
Runs every 15 minutes via GitHub Actions
"""

import os
import sys
import json
import boto3
from datetime import datetime

sys.path.insert(0, '/var/task')

from indicators.smi_debug import SMIDebug
from exchange.simple_exchange import SimpleExchangeManager

class SMI15MTestAnalyzer:
    def __init__(self):
        self.exchange_manager = SimpleExchangeManager()
        self.smi = SMIDebug(
            length_k=10,
            length_d=3,
            length_ema=3,
            overbought=40,
            oversold=-40
        )
        self.telegram_bot_token = None
        self.telegram_chat_id = None
    
    def send_telegram(self, message):
        """Send test alert"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            print("⚠️ Telegram not configured")
            return False
        
        try:
            import requests
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            print("✅ Telegram sent")
            return True
        except Exception as e:
            print(f"❌ Telegram failed: {e}")
            return False
    
    def analyze_btc(self):
        """Analyze BTC on 15M"""
        print(f"\n{'='*70}")
        print(f"🧪 SMI 15M TEST - BTC ONLY")
        print(f"{'='*70}")
        print(f"⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        try:
            # Fetch 15M data
            df_15m, exchange = self.exchange_manager.get_ohlcv_data('BTC/USDT', '15m', 100)
            
            if df_15m is None or len(df_15m) < 30:
                print("❌ Failed to fetch BTC 15M data")
                return
            
            print(f"\n✅ Fetched {len(df_15m)} candles from {exchange}")
            print(f"   Last candle: {df_15m.index[-1]}")
            
            # Analyze
            result = self.smi.analyze(
                df_15m['high'].values,
                df_15m['low'].values,
                df_15m['close'].values,
                df_15m.index,
                'BTC'
            )
            
            if not result:
                print(f"\n{'='*70}")
                print(f"ℹ️ No signals found")
                print(f"{'='*70}\n")
                return
            
            # Found signals!
            crosses = result['crosses']
            price = float(df_15m['close'].iloc[-1])
            
            print(f"\n{'='*70}")
            print(f"🚨 ALERT: {len(crosses)} Signal(s) Found!")
            print(f"{'='*70}")
            
            # Build Telegram message
            msg = "🧪 **SMI 15M TEST** 🧪\n"
            msg += f"⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for i, cross_data in enumerate(crosses, 1):
                cross_info = cross_data['cross_info']
                candle_ts = cross_data['candle_timestamp']
                signal_type = cross_info['cross_type']
                
                emoji = '🟢' if signal_type == 'OVERSOLD' else '🔴'
                
                msg += f"{i}. {emoji} **BTC {signal_type}**\n"
                msg += f"   💰 Price: ${price:.2f}\n"
                msg += f"   ⏰ Candle: {candle_ts}\n"
                msg += f"   📊 %K={cross_info['k_curr']:.2f} | %D={cross_info['d_curr']:.2f}\n"
                msg += f"   📊 At Cross: %K≈{cross_info['k_at_cross']:.2f}\n"
                
                tv_url = f"https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT&interval=15"
                msg += f"   📊 [15M Chart]({tv_url})\n\n"
            
            msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "🧪 Test Mode: 15M Crossover Detection\n"
            msg += "🔍 Lookback: Last 3 candles (2 closed + 1 running)\n"
            msg += "⏱️ Cooldown: 90 minutes\n"
            
            self.send_telegram(msg)
            
        except Exception as e:
            print(f"❌ Analysis failed: {e}")
            import traceback
            traceback.print_exc()


def lambda_handler(event, context):
    print("🚀 SMI 15M Test Analyzer")
    
    try:
        sm = boto3.client('secretsmanager')
        secrets = json.loads(sm.get_secret_value(SecretId='crypto-trading-api-keys')['SecretString'])
        
        analyzer = SMI15MTestAnalyzer()
        analyzer.telegram_bot_token = secrets['TELEGRAM_BOT_TOKEN']
        analyzer.telegram_chat_id = secrets.get('TELEGRAM_CHAT_ID_TEST', secrets.get('TELEGRAM_CHAT_ID'))
        
        analyzer.analyze_btc()
        
        return {'statusCode': 200, 'body': json.dumps({'status': 'success'})}
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return {'statusCode': 500, 'body': str(e)}


if __name__ == '__main__':
    # Local testing
    lambda_handler(None, None)
