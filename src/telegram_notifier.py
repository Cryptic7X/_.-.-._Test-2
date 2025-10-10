import os
from telegram import Bot
from telegram.error import TelegramError
import asyncio

class TelegramNotifier:
    """Format and send Telegram alerts"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
    
    def format_message(self, base_symbol: str, full_symbol: str, timeframe_data: dict, ticker_info: dict) -> str:
        """
        Format comprehensive alert message
        
        Args:
            base_symbol: Base currency (e.g., 'BTC')
            full_symbol: Full trading pair (e.g., 'BTC/USDT')
            timeframe_data: {timeframe: {'k': float, 'd': float, 'signal': str}}
            ticker_info: {'price': float, 'change_24h': float}
        
        Returns: Formatted message string
        """
        # Determine alert type from 15m timeframe
        base_signal = timeframe_data.get('15m', {}).get('signal', 'NEUTRAL')
        
        # Emoji based on signal type
        if base_signal == 'OVERBOUGHT':
            emoji = '🔴'
            alert_type = 'OVERBOUGHT ALERT'
        elif base_signal == 'OVERSOLD':
            emoji = '🟢'
            alert_type = 'OVERSOLD ALERT'
        else:
            emoji = '⚪'
            alert_type = 'NEUTRAL'
        
        # Build message
        msg = f"{emoji} **{alert_type}** {emoji}\n\n"
        msg += f"**Symbol:** {base_symbol}\n"
        msg += f"**Pair:** {full_symbol}\n"
        msg += f"**Price:** ${ticker_info.get('price', 0):.4f}\n"
        
        change = ticker_info.get('change_24h', 0)
        change_emoji = '📈' if change > 0 else '📉'
        msg += f"**24h Change:** {change_emoji} {change:+.2f}%\n\n"
        
        msg += "**Stochastic RSI Analysis:**\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Timeframe analysis (15m, 1h, 4h, 1D)
        timeframes = ['15m', '1h', '4h', '1d']
        tf_labels = {'15m': '15 Minutes', '1h': '1 Hour', '4h': '4 Hours', '1d': 'Daily'}
        
        for tf in timeframes:
            data = timeframe_data.get(tf, {})
            k = data.get('k', 'N/A')
            d = data.get('d', 'N/A')
            signal = data.get('signal', 'NEUTRAL')
            
            # Format values
            k_str = f"{k:.2f}" if isinstance(k, (int, float)) else k
            d_str = f"{d:.2f}" if isinstance(d, (int, float)) else d
            
            # Signal indicator
            if signal == 'OVERBOUGHT':
                indicator = '🔴'
            elif signal == 'OVERSOLD':
                indicator = '🟢'
            else:
                indicator = '⚪'
            
            msg += f"{indicator} **{tf_labels[tf]}**\n"
            msg += f"   %K: {k_str}  |  %D: {d_str}\n"
            msg += f"   Status: {signal}\n\n"
        
        # Links - use base symbol for TradingView
        msg += "**Quick Links:**\n"
        msg += f"📊 [TradingView 15m Chart](https://www.tradingview.com/chart/?symbol=BINANCE:{base_symbol}USDT&interval=15)\n"
        msg += f"📈 [CoinGlass Analytics](https://www.coinglass.com/currencies/{base_symbol.lower()})\n"
        
        return msg
    
    async def send_message_async(self, message: str) -> bool:
        """Send Telegram message asynchronously"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            return True
        except TelegramError as e:
            print(f"Telegram error: {e}")
            return False
    
    def send_message(self, message: str) -> bool:
        """Send Telegram message (synchronous wrapper)"""
        return asyncio.run(self.send_message_async(message))
