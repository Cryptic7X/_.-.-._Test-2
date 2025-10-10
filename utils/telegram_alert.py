# utils/telegram_alert.py

import os
import logging
from telegram import Bot
from datetime import datetime

logger = logging.getLogger(__name__)
BOT = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
CHAT= os.getenv('TELEGRAM_CHAT_ID')

def create_chart_links(symbol: str, timeframe_minutes: int):
    tv = f"https://www.tradingview.com/chart/?symbol=BINANCE:{symbol}USDT&interval={timeframe_minutes}"
    cg = f"https://www.coinglass.com/currencies/{symbol.lower()}"
    return tv, cg

def send_alert(symbol, signal, tf_data, primary_tf, tv_link, cg_link):
    head = f"🔴 Stochastic RSI {primary_tf.upper()}\n⏰ {datetime.now():%Y-%m-%d %H:%M IST}"
    lines=[f"🔸 {symbol} {signal}"]
    for tf,d in tf_data.items():
        lines.append(f"• {tf:<3} | K:{d['k']:.2f} | D:{d['d']:.2f} | {d['status']}")
    footer = f"[TV]({tv_link}) | [CG]({cg_link})"
    text = f"{head}\n\n" + "\n".join(lines) + "\n\n" + footer + "\n\n#StochasticRSI"
    try:
        BOT.send_message(chat_id=CHAT, text=text, parse_mode='Markdown', disable_web_page_preview=True)
        logger.info("Alert sent")
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
