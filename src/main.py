import os
import time
from dotenv import load_dotenv
from data_fetcher import DataFetcher
from stochastic_rsi import get_latest_stoch_rsi
from signal_detector import SignalDetector
from telegram_notifier import TelegramNotifier

# Load environment variables
load_dotenv()

def load_coin_list(file_path='config/coins.txt'):
    """
    Load coin list from file and convert to trading pairs
    
    Supports multiple quote currencies with priority: USDT > USDC > USD
    """
    with open(file_path, 'r') as f:
        base_symbols = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    return base_symbols

def get_trading_symbol(base_symbol, data_fetcher, quote_currencies=['USDT', 'USDC', 'USD']):
    """
    Convert base symbol (e.g., 'BTC') to full trading pair (e.g., 'BTC/USDT')
    Tries multiple quote currencies until finding an available market
    
    Args:
        base_symbol: Base currency code (e.g., 'BTC', 'ETH')
        data_fetcher: DataFetcher instance
        quote_currencies: List of quote currencies to try in priority order
    
    Returns:
        Trading pair string (e.g., 'BTC/USDT') or None if not found
    """
    for exchange in data_fetcher.exchanges:
        try:
            if not exchange.markets:
                exchange.load_markets()
            
            # Try each quote currency in priority order
            for quote in quote_currencies:
                symbol = f"{base_symbol}/{quote}"
                if symbol in exchange.markets:
                    return symbol
            
        except Exception as e:
            continue
    
    # Default to USDT if no exchange has markets loaded yet
    return f"{base_symbol}/USDT"

def analyze_coin(base_symbol, data_fetcher, signal_detector):
    """Analyze single coin across all timeframes"""
    
    # Convert base symbol to full trading pair
    symbol = get_trading_symbol(base_symbol, data_fetcher)
    
    print(f"\n{'='*50}")
    print(f"Analyzing {base_symbol} ({symbol})")
    print(f"{'='*50}")
    
    timeframes = ['15m', '1h', '4h', '1d']
    timeframe_data = {}
    
    # Fetch OHLCV for all timeframes
    ohlcv_data = data_fetcher.fetch_multi_timeframe_data(symbol, timeframes)
    
    # Calculate Stochastic RSI for each timeframe
    for tf in timeframes:
        if ohlcv_data[tf] is None:
            print(f"  ✗ Skipping {tf} - no data")
            timeframe_data[tf] = {'k': None, 'd': None, 'signal': 'NEUTRAL'}
            continue
        
        try:
            # Calculate using exact TradingView logic
            stoch_data = get_latest_stoch_rsi(
                ohlcv_data[tf],
                smooth_k=3,
                smooth_d=3,
                rsi_length=14,
                stoch_length=14
            )
            
            k = stoch_data['k']
            d = stoch_data['d']
            signal = signal_detector.classify_signal(k, d)
            
            timeframe_data[tf] = {
                'k': k,
                'd': d,
                'signal': signal
            }
            
            print(f"  {tf:4s}: K={k:6.2f}  D={d:6.2f}  [{signal}]")
            
        except Exception as e:
            print(f"  ✗ Error calculating {tf}: {e}")
            timeframe_data[tf] = {'k': None, 'd': None, 'signal': 'NEUTRAL'}
    
    # Get ticker info
    ticker_info = data_fetcher.fetch_ticker(symbol)
    if ticker_info is None:
        ticker_info = {'price': 0, 'change_24h': 0}
    
    return {
        'base_symbol': base_symbol,
        'symbol': symbol,
        'timeframe_data': timeframe_data,
        'ticker_info': ticker_info
    }

def main():
    """Main analysis loop"""
    print("🚀 Starting Stochastic RSI Analysis System")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize components
    data_fetcher = DataFetcher()
    signal_detector = SignalDetector(cooldown_hours=4)
    
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not telegram_token or not telegram_chat_id:
        print("⚠️  Warning: Telegram credentials not found. Alerts will not be sent.")
        telegram_notifier = None
    else:
        telegram_notifier = TelegramNotifier(telegram_token, telegram_chat_id)
    
    # Load coin list
    base_symbols = load_coin_list()
    print(f"📋 Loaded {len(base_symbols)} coins from coins.txt")
    print(f"Coins: {', '.join(base_symbols[:10])}{'...' if len(base_symbols) > 10 else ''}\n")
    
    # Track statistics
    stats = {
        'total_analyzed': 0,
        'alerts_sent': 0,
        'errors': 0,
        'start_time': time.time()
    }
    
    # Analyze each coin
    for base_symbol in base_symbols:
        try:
            result = analyze_coin(base_symbol, data_fetcher, signal_detector)
            stats['total_analyzed'] += 1
            
            # Check if alert should be sent (based on 15m timeframe)
            base_signal = result['timeframe_data']['15m']['signal']
            
            # Use base symbol for cooldown tracking (not full trading pair)
            if signal_detector.should_send_alert(base_symbol, base_signal):
                if telegram_notifier:
                    message = telegram_notifier.format_message(
                        result['base_symbol'],
                        result['symbol'],
                        result['timeframe_data'],
                        result['ticker_info']
                    )
                    
                    if telegram_notifier.send_message(message):
                        print(f"  ✓ Alert sent for {base_symbol} [{base_signal}]")
                        signal_detector.update_cooldown(base_symbol, base_signal)
                        stats['alerts_sent'] += 1
                    else:
                        print(f"  ✗ Failed to send alert for {base_symbol}")
                        stats['errors'] += 1
            
            time.sleep(0.5)  # Rate limiting between coins
            
        except Exception as e:
            print(f"  ✗ Error analyzing {base_symbol}: {e}")
            stats['errors'] += 1
            continue
    
    # Print summary
    elapsed_time = time.time() - stats['start_time']
    print(f"\n{'='*50}")
    print(f"📊 Analysis Complete")
    print(f"{'='*50}")
    print(f"Coins Analyzed: {stats['total_analyzed']}/{len(base_symbols)}")
    print(f"Alerts Sent: {stats['alerts_sent']}")
    print(f"Errors: {stats['errors']}")
    print(f"Time Elapsed: {elapsed_time:.1f}s ({elapsed_time/60:.1f}min)")
    print(f"Average per coin: {elapsed_time/max(stats['total_analyzed'], 1):.1f}s")
    print(f"{'='*50}\n")

if __name__ == "__main__":
    main()
