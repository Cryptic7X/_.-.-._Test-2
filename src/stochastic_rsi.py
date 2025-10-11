import pandas as pd
import numpy as np

def calculate_rsi_tradingview(close, period=14):
    """
    Calculate RSI using EXACT TradingView method (Wilder's RMA)
    
    TradingView uses RMA (Running Moving Average) with alpha = 1/period
    Formula: RMA(current) = (previous_RMA * (period-1) + current_value) / period
    
    This is equivalent to EMA with alpha = 1/period, NOT 2/(period+1)
    """
    close_series = pd.Series(close).copy()
    delta = close_series.diff()
    
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    # Use adjust=False to match TradingView's Wilder RMA method
    # alpha = 1/period for Wilder's smoothing
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    # Avoid division by zero
    rs = avg_gain / avg_loss
    rs = rs.replace([np.inf, -np.inf], np.nan)
    
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def calculate_stochastic_tradingview(values, period=14):
    """
    Calculate Stochastic %K using EXACT TradingView ta.stoch logic
    
    Pine Script: ta.stoch(source, high, low, length)
    For Stochastic RSI: ta.stoch(rsi, rsi, rsi, length)
    
    Formula: %K = 100 * (current - lowest_low) / (highest_high - lowest_low)
    """
    values_series = pd.Series(values).copy()
    
    # Calculate rolling highest and lowest over the period
    highest = values_series.rolling(window=period, min_periods=period).max()
    lowest = values_series.rolling(window=period, min_periods=period).min()
    
    # Calculate stochastic
    stoch = 100 * (values_series - lowest) / (highest - lowest)
    
    # Handle division by zero (when highest == lowest)
    stoch = stoch.replace([np.inf, -np.inf], 0)
    
    return stoch

def calculate_stochastic_rsi(close, smooth_k=3, smooth_d=3, rsi_length=14, stoch_length=14):
    """
    Calculate Stochastic RSI EXACTLY matching TradingView's implementation
    
    Pine Script equivalent:
    rsi1 = ta.rsi(src, lengthRSI)
    k = ta.sma(ta.stoch(rsi1, rsi1, rsi1, lengthStoch), smoothK)
    d = ta.sma(k, smoothD)
    
    Returns: tuple of (k_values, d_values) as pandas Series
    """
    close_series = pd.Series(close).copy()
    
    # Step 1: Calculate RSI using TradingView's Wilder method
    rsi = calculate_rsi_tradingview(close_series, period=rsi_length)
    
    # Step 2: Calculate Stochastic of RSI
    # ta.stoch(rsi1, rsi1, rsi1, lengthStoch) - uses same RSI for high/low/close
    stoch_rsi = calculate_stochastic_tradingview(rsi, period=stoch_length)
    
    # Step 3: Smooth %K with SMA (min_periods=smooth_k to match TradingView)
    k = stoch_rsi.rolling(window=smooth_k, min_periods=smooth_k).mean()
    
    # Step 4: Smooth %D (SMA of %K)
    d = k.rolling(window=smooth_d, min_periods=smooth_d).mean()
    
    return k, d

def get_latest_stoch_rsi(ohlcv_data, smooth_k=3, smooth_d=3, rsi_length=14, stoch_length=14):
    """
    Get the latest Stochastic RSI %K and %D values from OHLCV data
    
    Args:
        ohlcv_data: List of OHLCV candles [[timestamp, open, high, low, close, volume], ...]
        smooth_k, smooth_d, rsi_length, stoch_length: TradingView default parameters
    
    Returns:
        dict: {'k': float, 'd': float, 'timestamp': int}
    """
    # Need minimum candles for calculation
    # RSI needs: rsi_length + 1 (for diff)
    # Stoch needs: rsi_length + stoch_length
    # Smoothing needs: + smooth_k + smooth_d
    min_required = rsi_length + stoch_length + smooth_k + smooth_d + 10
    
    if len(ohlcv_data) < min_required:
        raise ValueError(f"Insufficient data: need at least {min_required} candles, got {len(ohlcv_data)}")
    
    # Extract close prices
    df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    close_prices = df['close'].values
    
    # Calculate Stochastic RSI
    k_series, d_series = calculate_stochastic_rsi(
        close_prices,
        smooth_k=smooth_k,
        smooth_d=smooth_d,
        rsi_length=rsi_length,
        stoch_length=stoch_length
    )
    
    # Get latest valid values (work backwards to find non-NaN)
    latest_k = None
    latest_d = None
    
    for i in range(len(k_series) - 1, -1, -1):
        if pd.notna(k_series.iloc[i]) and pd.notna(d_series.iloc[i]):
            latest_k = k_series.iloc[i]
            latest_d = d_series.iloc[i]
            break
    
    latest_timestamp = int(df['timestamp'].iloc[-1])
    
    return {
        'k': round(float(latest_k), 2) if latest_k is not None else None,
        'd': round(float(latest_d), 2) if latest_d is not None else None,
        'timestamp': latest_timestamp
    }
