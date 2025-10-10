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
    """Load coin list from file"""
    with open(file_path, 'r') as f:
        coins = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return coins

def analyze_coin(symbol, data_fetcher, signal_detector):
    """Analyze single coin across all timeframes"""
    print(f"\n{'='*50}")
    print(f"Analyzing {symbol}")
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
    coins = load_coin_list()
    print(f"📋 Loaded {len(coins)} coins from coins.txt\n")
    
    # Track statistics
    stats = {
        'total_analyzed': 0,
        'alerts_sent': 0,
        'errors': 0,
        'start_time': time.time()
    }
    
    # Analyze each coin
    for coin in coins:
        try:
            result = analyze_coin(coin, data_fetcher, signal_detector)
            stats['total_analyzed'] += 1
            
            # Check if alert should be sent (based on 15m timeframe)
            base_signal = result['timeframe_data']['15m']['signal']
            
            if signal_detector.should_send_alert(coin, base_signal):
                if telegram_notifier:
                    message = telegram_notifier.format_message(
                        result['symbol'],
                        result['timeframe_data'],
                        result['ticker_info']
                    )
                    
                    if telegram_notifier.send_message(message):
                        print(f"  ✓ Alert sent for {coin} [{base_signal}]")
                        signal_detector.update_cooldown(coin, base_signal)
                        stats['alerts_sent'] += 1
                    else:
                        print(f"  ✗ Failed to send alert for {coin}")
                        stats['errors'] += 1
            
            time.sleep(0.5)  # Rate limiting between coins
            
        except Exception as e:
            print(f"  ✗ Error analyzing {coin}: {e}")
            stats['errors'] += 1
            continue
    
    # Print summary
    elapsed_time = time.time() - stats['start_time']
    print(f"\n{'='*50}")
    print(f"📊 Analysis Complete")
    print(f"{'='*50}")
    print(f"Coins Analyzed: {stats['total_analyzed']}/{len(coins)}")
    print(f"Alerts Sent: {stats['alerts_sent']}")
    print(f"Errors: {stats['errors']}")
    print(f"Time Elapsed: {elapsed_time:.1f}s ({elapsed_time/60:.1f}min)")
    print(f"{'='*50}\n")

if __name__ == "__main__":
    main()
