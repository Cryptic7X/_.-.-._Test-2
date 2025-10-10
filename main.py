"""
Main script for Stochastic RSI Alerts System
Fetches OHLCV data, calculates Stochastic RSI across multiple timeframes, and sends alerts
"""
import time
from ccxt_client import get_exchange, fetch_ohlcv_data
from stoch_rsi import calculate_stochastic_rsi, determine_signal
from alert_manager import AlertManager
from utils.telegram_alert import send_alert_sync
from utils.logging_setup import setup_logger
from config import (
    COINS_FILE, TIMEFRAMES, PRIMARY_TIMEFRAME, 
    OVERBOUGHT_LEVEL, OVERSOLD_LEVEL,
    SMOOTH_K, SMOOTH_D, LENGTH_RSI, LENGTH_STOCH,
    CANDLES_LIMIT, MIN_CANDLES_REQUIRED
)

logger = setup_logger(__name__)


def load_coins():
    """
    Load coin symbols from coins.txt file
    Handles comma-separated format: "ETHUSDT, BTCUSDT"

    Returns:
        List of trading pairs in CCXT format (e.g., ['BTC/USDT', 'ETH/USDT'])
    """
    try:
        with open(COINS_FILE, 'r') as f:
            content = f.read()

        # Split by comma and clean up
        coins = [coin.strip() for coin in content.split(',') if coin.strip()]

        # Convert from BTCUSDT to BTC/USDT format for CCXT
        formatted_coins = []
        for coin in coins:
            if '/' not in coin:
                # Assume USDT pair and add slash
                if coin.endswith('USDT'):
                    formatted = coin[:-4] + '/USDT'
                else:
                    formatted = coin + '/USDT'
                formatted_coins.append(formatted)
            else:
                formatted_coins.append(coin)

        logger.info(f"Loaded {len(formatted_coins)} coins from {COINS_FILE}")
        return formatted_coins

    except Exception as e:
        logger.error(f"Error loading coins file: {e}")
        return []


def analyze_symbol(exchange, symbol, alert_manager):
    """
    Analyze a single symbol across multiple timeframes

    Args:
        exchange: CCXT exchange instance
        symbol: Trading pair symbol
        alert_manager: AlertManager instance

    Returns:
        True if analysis completed, False on error
    """
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"Analyzing {symbol}")
        logger.info(f"{'='*60}")

        timeframe_data = {}

        # Analyze each timeframe
        for timeframe in TIMEFRAMES:
            logger.info(f"Fetching {timeframe} data for {symbol}...")

            ohlcv = fetch_ohlcv_data(exchange, symbol, timeframe, CANDLES_LIMIT)

            if not ohlcv or len(ohlcv) < MIN_CANDLES_REQUIRED:
                logger.warning(f"Insufficient data for {symbol} {timeframe}")
                continue

            # Extract close prices
            close_prices = [candle[4] for candle in ohlcv]

            # Calculate Stochastic RSI
            stoch_rsi = calculate_stochastic_rsi(
                close_prices,
                length_rsi=LENGTH_RSI,
                length_stoch=LENGTH_STOCH,
                smooth_k=SMOOTH_K,
                smooth_d=SMOOTH_D
            )

            if not stoch_rsi:
                logger.warning(f"Failed to calculate Stochastic RSI for {symbol} {timeframe}")
                continue

            k_value = stoch_rsi['k']
            d_value = stoch_rsi['d']

            # Determine signal
            signal = determine_signal(k_value, d_value, OVERBOUGHT_LEVEL, OVERSOLD_LEVEL)

            timeframe_data[timeframe] = {
                'k': k_value,
                'd': d_value,
                'status': signal
            }

            logger.info(f"{timeframe}: K={k_value:.2f}, D={d_value:.2f}, Status={signal}")

        # Check if primary timeframe has a signal
        if PRIMARY_TIMEFRAME in timeframe_data:
            primary_data = timeframe_data[PRIMARY_TIMEFRAME]
            signal_type = primary_data['status']

            if signal_type in ['OVERBOUGHT', 'OVERSOLD']:
                # Check cooldown
                if alert_manager.can_send_alert(symbol, PRIMARY_TIMEFRAME, signal_type):
                    logger.info(f"🔔 Sending {signal_type} alert for {symbol}")

                    # Send alert with multi-timeframe data
                    success = send_alert_sync(symbol, signal_type, timeframe_data, PRIMARY_TIMEFRAME)

                    if success:
                        alert_manager.record_alert(symbol, PRIMARY_TIMEFRAME, signal_type)
                        alert_manager.clear_opposite_signal(symbol, PRIMARY_TIMEFRAME, signal_type)
                else:
                    logger.info(f"⏳ Alert cooldown active for {symbol} {signal_type}")
            else:
                logger.info(f"✓ {symbol} is NEUTRAL on {PRIMARY_TIMEFRAME}")

        return True

    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        return False


def main():
    """
    Main execution function
    """
    start_time = time.time()
    logger.info("\n" + "="*60)
    logger.info("STOCHASTIC RSI ALERTS SYSTEM - STARTING")
    logger.info("="*60)

    # Initialize components
    exchange = get_exchange()
    alert_manager = AlertManager()
    coins = load_coins()

    if not coins:
        logger.error("No coins loaded. Exiting.")
        return

    logger.info(f"Analyzing {len(coins)} coins across {len(TIMEFRAMES)} timeframes")
    logger.info(f"Parameters: RSI={LENGTH_RSI}, Stoch={LENGTH_STOCH}, K={SMOOTH_K}, D={SMOOTH_D}")
    logger.info(f"Zones: Overbought={OVERBOUGHT_LEVEL}, Oversold={OVERSOLD_LEVEL}")
    logger.info(f"Primary Timeframe: {PRIMARY_TIMEFRAME}")

    # Analyze each coin
    success_count = 0
    for i, symbol in enumerate(coins, 1):
        logger.info(f"\nProcessing {i}/{len(coins)}: {symbol}")

        if analyze_symbol(exchange, symbol, alert_manager):
            success_count += 1

        # Rate limiting between symbols
        if i < len(coins):
            time.sleep(exchange.rateLimit / 1000)

    # Cleanup old cache entries
    alert_manager.cleanup_old_entries(days=7)

    # Summary
    elapsed_time = time.time() - start_time
    logger.info("\n" + "="*60)
    logger.info("ANALYSIS COMPLETE")
    logger.info(f"Successfully analyzed: {success_count}/{len(coins)} coins")
    logger.info(f"Time elapsed: {elapsed_time:.2f} seconds")
    logger.info("="*60)


if __name__ == "__main__":
    main()
