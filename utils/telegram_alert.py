"""
Telegram alert system for Stochastic RSI signals
"""
import asyncio
from telegram import Bot
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from utils.logging_setup import setup_logger

logger = setup_logger(__name__)


async def send_telegram_alert(symbol, signal_type, timeframe_data, primary_timeframe):
    """
    Send formatted alert to Telegram

    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        signal_type: 'OVERBOUGHT' or 'OVERSOLD'
        timeframe_data: Dictionary with timeframe analysis
        primary_timeframe: The main timeframe that triggered the alert
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram credentials not configured")
        return False

    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)

        # Create formatted message
        emoji = "🔴" if signal_type == "OVERBOUGHT" else "🟢"

        message = f"{emoji} *Stochastic RSI Alert*\n\n"
        message += f"*Symbol:* {symbol}\n"
        message += f"*Signal:* {signal_type}\n"
        message += f"*Primary Timeframe:* {primary_timeframe}\n\n"

        message += "*Multi-Timeframe Analysis:*\n"
        message += "```\n"

        for tf in ['15m', '1h', '4h', '1d']:
            if tf in timeframe_data:
                data = timeframe_data[tf]
                k_val = data.get('k', 0)
                d_val = data.get('d', 0)
                status = data.get('status', 'NEUTRAL')

                message += f"{tf:4} | K: {k_val:5.2f} | D: {d_val:5.2f} | {status}\n"

        message += "```\n"

        # Add TradingView link
        clean_symbol = symbol.replace('USDT', '')
        tv_link = f"https://www.tradingview.com/chart/?symbol=BINANCE:{symbol}"
        message += f"\n[View on TradingView]({tv_link})"

        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

        logger.info(f"Alert sent for {symbol} - {signal_type}")
        return True

    except Exception as e:
        logger.error(f"Error sending Telegram alert: {e}")
        return False


def send_alert_sync(symbol, signal_type, timeframe_data, primary_timeframe):
    """
    Synchronous wrapper for sending alerts
    """
    return asyncio.run(send_telegram_alert(symbol, signal_type, timeframe_data, primary_timeframe))
