"""
Telegram alert system
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

# Import inside functions to avoid issues
def send_telegram_alert(symbol, signal_type, timeframe_data, primary_timeframe):
    """Send alert to Telegram (synchronous wrapper)"""
    return asyncio.run(send_alert_async(symbol, signal_type, timeframe_data, primary_timeframe))


async def send_alert_async(symbol, signal_type, timeframe_data, primary_timeframe):
    """Send formatted alert to Telegram"""
    try:
        from telegram import Bot
        import config

        if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
            logger.error("Telegram credentials not configured")
            return False

        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)

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

        clean_symbol = symbol.replace('/', '')
        tv_link = f"https://www.tradingview.com/chart/?symbol=BINANCE:{clean_symbol}"
        message += f"\n[View on TradingView]({tv_link})"

        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

        logger.info(f"Alert sent for {symbol} - {signal_type}")
        return True
    except Exception as e:
        logger.error(f"Error sending Telegram alert: {e}")
        return False
