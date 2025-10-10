import os
from telegram import Bot
from telegram.error import TelegramError

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
    
    def format_bulk_message(self, alerts: list) -> str:
        """
        Format multiple alerts into a single consolidated message
        
        Args:
            alerts: List of dicts with keys: base_symbol, symbol, timeframe_data, ticker_info
        
        Returns: Formatted consolidated message
        """
        if not alerts:
            return None
        
        # Count oversold vs overbought
        oversold = [a for a in alerts if a['timeframe_data']['15m']['signal'] == 'OVERSOLD']
        overbought = [a for a in alerts if a['timeframe_data']['15m']['signal'] == 'OVERBOUGHT']
        
        # Build header
        msg = "📊 **STOCHASTIC RSI ALERTS** 📊\n"
        msg += f"⏰ {alerts[0].get('timestamp', '')}\n\n"
        msg += f"**Total Signals:** {len(alerts)}\n"
        msg += f"🟢 Oversold: {len(oversold)} | 🔴 Overbought: {len(overbought)}\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Group by signal type
        if oversold:
            msg += "🟢 **OVERSOLD SIGNALS**\n\n"
            for alert in oversold:
                msg += self._format_compact_alert(alert)
                msg += "\n"
        
        if overbought:
            msg += "🔴 **OVERBOUGHT SIGNALS**\n\n"
            for alert in overbought:
                msg += self._format_compact_alert(alert)
                msg += "\n"
        
        # Footer
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "💡 Use TradingView links for detailed chart analysis\n"
        
        return msg
    
    def _format_compact_alert(self, alert: dict) -> str:
        """Format a single alert in compact format"""
        base_symbol = alert['base_symbol']
        ticker = alert['ticker_info']
        tf_data = alert['timeframe_data']
        
        # Price and change
        price = ticker.get('price', 0)
        change = ticker.get('change_24h', 0)
        change_emoji = '📈' if change > 0 else '📉'
        
        # Build compact format
        msg = f"**{base_symbol}** | ${price:.4f} | {change_emoji} {change:+.2f}%\n"
        
        # Timeframes in single line
        tf_labels = {'15m': '15m', '1h': '1h', '4h': '4h', '1d': '1D'}
        tf_line = "  "
        
        for tf in ['15m', '1h', '4h', '1d']:
            k = tf_data[tf]['k']
            d = tf_data[tf]['d']
            signal = tf_data[tf]['signal']
            
            # Signal emoji
            if signal == 'OVERBOUGHT':
                emoji = '🔴'
            elif signal == 'OVERSOLD':
                emoji = '🟢'
            else:
                emoji = '⚪'
            
            if k and d:
                tf_line += f"{emoji}{tf_labels[tf]}:{k:.0f}/{d:.0f} "
            else:
                tf_line += f"{emoji}{tf_labels[tf]}:N/A "
        
        msg += tf_line + "\n"
        msg += f"  📊 [Chart](https://www.tradingview.com/chart/?symbol=BINANCE:{base_symbol}USDT&interval=15) | "
        msg += f"[Analytics](https://www.coinglass.com/currencies/{base_symbol.lower()})\n"
        
        return msg
    
    async def send_message(self, message: str) -> bool:
        """Send Telegram message asynchronously - MUST BE AWAITED"""
        try:
            # Check message length and split if needed (Telegram limit: 4096 chars)
            if len(message) <= 4096:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
            else:
                # Split message into chunks
                chunks = self._split_message(message, 4096)
                for i, chunk in enumerate(chunks):
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=f"[Part {i+1}/{len(chunks)}]\n\n{chunk}",
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                    # Small delay between chunks
                    import asyncio
                    await asyncio.sleep(0.5)
            
            return True
        except TelegramError as e:
            print(f"Telegram error: {e}")
            return False
    
    def _split_message(self, message: str, limit: int) -> list:
        """Split long message into chunks respecting word boundaries"""
        if len(message) <= limit:
            return [message]
        
        chunks = []
        lines = message.split('\n')
        current_chunk = ""
        
        for line in lines:
            if len(current_chunk) + len(line) + 1 <= limit:
                current_chunk += line + '\n'
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line + '\n'
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
