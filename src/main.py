import os
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
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
        base_symbols = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return base_symbols

def get_trading_symbol(base_symbol, data_fetcher, quote_currencies=['USDT', 'USDC', 'USD']):
    """Convert base symbol to trading pair"""
    for exchange in data_fetcher.exchanges:
        try:
            if not exchange.markets:
                exchange.load_markets()
            
            for quote in quote_currencies:
                symbol = f"{base_symbol}/{quote}"
                if symbol in exchange.markets:
                    return symbol
        except Exception as e:
            continue
    
    return f"{base_symbol}/USDT"

def analyze_single_coin(base_symbol, data_fetcher, signal_detector):
    """Analyze single coin (thread-safe function)"""
    try:
        symbol = get_trading_symbol(base_symbol, data_fetcher)
        
        timeframes = ['15m', '1h', '4h', '1d']
        timeframe_data = {}
        
        # Fetch OHLCV for all timeframes
        ohlcv_data = data_fetcher.fetch_multi_timeframe_data(symbol, timeframes)
        
        # Calculate Stochastic RSI for each timeframe
        for tf in timeframes:
            if ohlcv_data[tf] is None:
                timeframe_data[tf] = {'k': None, 'd': None, 'signal': 'NEUTRAL'}
                continue
            
            try:
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
                
            except Exception as e:
                timeframe_data[tf] = {'k': None, 'd': None, 'signal': 'NEUTRAL'}
        
        # Get ticker info
        ticker_info = data_fetcher.fetch_ticker(symbol)
        if ticker_info is None:
            ticker_info = {'price': 0, 'change_24h': 0}
        
        # Print result
        base_signal = timeframe_data['15m']['signal']
        k_val = timeframe_data['15m']['k']
        d_val = timeframe_data['15m']['d']
        
        if k_val and d_val:
            print(f"✓ {base_symbol:8s} | 15m: K={k_val:6.2f} D={d_val:6.2f} [{base_signal}]")
        else:
            print(f"✗ {base_symbol:8s} | No data")
        
        return {
            'base_symbol': base_symbol,
            'symbol': symbol,
            'timeframe_data': timeframe_data,
            'ticker_info': ticker_info
        }
        
    except Exception as e:
        print(f"✗ {base_symbol:8s} | Error: {str(e)[:50]}")
        return None

async def analyze_coins_parallel(coins, data_fetcher, signal_detector, max_workers=10):
    """Analyze multiple coins in parallel using ThreadPoolExecutor"""
    loop = asyncio.get_event_loop()
    results = []
    
    # Process in batches to avoid overwhelming exchanges
    batch_size = max_workers
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for i in range(0, len(coins), batch_size):
            batch = coins[i:i + batch_size]
            print(f"\n📊 Processing batch {i//batch_size + 1} ({len(batch)} coins)...")
            
            # Submit all tasks in batch
            futures = [
                loop.run_in_executor(
                    executor,
                    analyze_single_coin,
                    coin,
                    data_fetcher,
                    signal_detector
                )
                for coin in batch
            ]
            
            # Wait for batch to complete
            batch_results = await asyncio.gather(*futures)
            results.extend([r for r in batch_results if r is not None])
            
            # Small delay between batches to respect rate limits
            if i + batch_size < len(coins):
                await asyncio.sleep(1)
    
    return results

async def send_alerts(results, signal_detector, telegram_notifier):
    """Send Telegram alerts for qualifying signals (ASYNC VERSION)"""
    alerts_sent = 0
    
    for result in results:
        base_signal = result['timeframe_data']['15m']['signal']
        
        if signal_detector.should_send_alert(result['base_symbol'], base_signal):
            if telegram_notifier:
                message = telegram_notifier.format_message(
                    result['base_symbol'],
                    result['symbol'],
                    result['timeframe_data'],
                    result['ticker_info']
                )
                
                # AWAIT the async send_message function
                if await telegram_notifier.send_message(message):
                    signal_detector.update_cooldown(result['base_symbol'], base_signal)
                    alerts_sent += 1
                    print(f"  📤 Alert sent: {result['base_symbol']} [{base_signal}]")
                
                # Small delay between messages
                await asyncio.sleep(0.5)
    
    return alerts_sent

async def main_async():
    """Main analysis loop with parallel processing"""
    print("🚀 Starting Stochastic RSI Analysis System (PARALLEL MODE)")
    print(f"⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    start_time = time.time()
    
    # Initialize components
    data_fetcher = DataFetcher()
    signal_detector = SignalDetector(cooldown_hours=4)
    
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not telegram_token or not telegram_chat_id:
        print("⚠️  Warning: Telegram credentials not found. Alerts will not be sent.\n")
        telegram_notifier = None
    else:
        telegram_notifier = TelegramNotifier(telegram_token, telegram_chat_id)
    
    # Load coin list
    coins = load_coin_list()
    print(f"📋 Loaded {len(coins)} coins from coins.txt")
    print(f"🔧 Parallel workers: 10 coins at a time\n")
    
    # Analyze all coins in parallel
    results = await analyze_coins_parallel(coins, data_fetcher, signal_detector, max_workers=10)
    
    analysis_time = time.time() - start_time
    
    # Send alerts (NOW ASYNC)
    print(f"\n{'='*60}")
    print(f"📨 Sending Alerts...")
    print(f"{'='*60}")
    
    alerts_sent = await send_alerts(results, signal_detector, telegram_notifier)
    
    # Print summary
    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"✅ Analysis Complete")
    print(f"{'='*60}")
    print(f"Coins Analyzed: {len(results)}/{len(coins)}")
    print(f"Alerts Sent: {alerts_sent}")
    print(f"Analysis Time: {analysis_time:.1f}s")
    print(f"Total Time: {total_time:.1f}s")
    print(f"Avg per coin: {analysis_time/max(len(results), 1):.1f}s")
    print(f"{'='*60}\n")

def main():
    """Entry point"""
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
