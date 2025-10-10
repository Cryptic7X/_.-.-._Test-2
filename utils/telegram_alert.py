# utils/telegram_alert.py

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def create_chart_links(symbol: str, timeframe_minutes: int):
    """Generate TradingView and CoinGlass links"""
    tv = f"https://www.tradingview.com/chart/?symbol=BINANCE:{symbol}USDT&interval={timeframe_minutes}"
    cg = f"https://www.coinglass.com/currencies/{symbol.lower()}"
    return tv, cg


def send_alert(symbol, signal, tf_data, primary_tf, tv_link, cg_link):
    """Send Telegram alert with exact K/D values"""
    try:
        from telegram import Bot
        
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not bot_token or not chat_id:
            logger.error("Telegram credentials missing")
            return
        
        bot = Bot(token=bot_token)
        
        # Format message with exact values
        head = f"🔴 Stochastic RSI {primary_tf.upper()}\n⏰ {datetime.now():%Y-%m-%d %H:%M IST}"
        lines = [f"🔸 {symbol} {signal}\n"]
        
        # Show all timeframes with exact K/D values
        for tf in ['15m', '1h', '4h', '1d']:
            if tf in tf_data:
                d = tf_data[tf]
                lines.append(f"• {tf:<3} | K:{d['k']:6.2f} | D:{d['d']:6.2f} | {d['status']}")
        
        footer = f"\n[TV]({tv_link}) | [CG]({cg_link})"
        text = f"{head}\n" + "\n".join(lines) + footer + "\n\n#StochasticRSI"
        
        bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        logger.info("✓ Alert sent")
        
    except Exception as e:
        logger.error(f"Alert error: {e}")
