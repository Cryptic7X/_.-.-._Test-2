import os
from telegram import Bot
from telegram.error import TelegramError

class TelegramNotifier:
    """Format and send Telegram alerts"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
    
    def format_bulk_message(self, alerts: list) -> str:
        """
        Format multiple alerts into a single consolidated message
        Changed: Using 1h as base timeframe (was 15m)
        
        Args:
            alerts: List of dicts with keys: base_symbol, symbol, timeframe_data, ticker_info
        
        Returns: Formatted consolidated message
        """
        if not alerts:
            return None
        
        # Count oversold vs overbought (based on 1h now)
        oversold = [a for a in alerts if a['timeframe_data'].get('1h', {}).get('signal') == 'OVERSOLD']
        overbought = [a for a in alerts if a['timeframe_data'].get('1h', {}).get('signal') == 'OVERBOUGHT']
        
        # Build header
        msg = "📊 **STOCHASTIC RSI ALERTS** 📊\n"
        msg += f"⏰ {alerts[0].get('timestamp', '')}\n"
        msg += f"📍 Base Timeframe: **1 HOUR**\n\n"
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
        msg += "💡 Signals based on 1-hour timeframe\n"
        msg += "📊 Use TradingView links for detailed analysis\n"
        
        return msg
    
    def _format_compact_alert(self, alert: dict) -> str:
        """
        Format a single alert in compact format
        Changed: Now shows 1h, 4h, 1d (removed 15m)
        Updated: CoinGlass link to Liquidation Heatmap
        """
        base_symbol = alert['base_symbol']
        ticker = alert['ticker_info']
        tf_data = alert['timeframe_data']
        
        # Price and change
        price = ticker.get('price', 0)
        change = ticker.get('change_24h', 0)
        change_emoji = '📈' if change > 0 else '📉'
        
        # Build compact format
        msg = f"**{base_symbol}** | ${price:.4f} | {change_emoji} {change:+.2f}%\n"
        
        # Timeframes in single line (1h, 4h, 1d)
        tf_labels = {'1h': '1h', '4h': '4h', '1d': '1D'}
        tf_line = "  "
        
        for tf in ['1h', '4h', '1d']:
            k = tf_data.get(tf, {}).get('k')
            d = tf_data.get(tf, {}).get('d')
            signal = tf_data.get(tf, {}).get('signal', 'NEUTRAL')
            
            # Signal emoji
            if signal == 'OVERBOUGHT':
                emoji = '🔴'
            elif signal == 'OVERSOLD':
                emoji = '🟢'
            else:
                emoji = '⚪'
            
            if k is not None and d is not None:
                tf_line += f"{emoji}{tf_labels[tf]}:{k:.0f}/{d:.0f} "
            else:
                tf_line += f"{emoji}{tf_labels[tf]}:N/A "
        
        msg += tf_line + "\n"
        
        # Updated links
        msg += f"  📊 [Chart](https://www.tradingview.com/chart/?symbol=BINANCE:{base_symbol}USDT&interval=60) | "
        msg += f"[Liquidation](https://www.coinglass.com/pro/futures/LiquidationHeatMapNew?coin={base_symbol})\n"
        
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
