import pandas as pd
import numpy as np

def calculate_rsi(close, period=14):
    """
    Calculate RSI using TradingView's exact method (RMA-based)
    
    TradingView uses RMA (Running Moving Average) with alpha = 1/period
    NOT the standard EMA with alpha = 2/(period+1)
    """
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    # First value uses simple average
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def calculate_stochastic(values, period=14):
    """
    Calculate Stochastic %K using TradingView's ta.stoch logic
    
    For Stochastic RSI: ta.stoch(rsi, rsi, rsi, length) 
    Uses the SAME RSI values for high, low, and close
    """
    stoch_values = []
    
    for i in range(len(values)):
        if i < period - 1:
            stoch_values.append(np.nan)
            continue
        
        window = values[i - period + 1:i + 1]
        highest = window.max()
        lowest = window.min()
        
        if highest == lowest:
            stoch_k = 0
        else:
            stoch_k = 100 * (values[i] - lowest) / (highest - lowest)
        
        stoch_values.append(stoch_k)
    
    return pd.Series(stoch_values, index=values.index)

def calculate_stochastic_rsi(close, smooth_k=3, smooth_d=3, rsi_length=14, stoch_length=14):
    """
    Calculate Stochastic RSI exactly matching TradingView's implementation
    
    Pine Script equivalent:
    rsi1 = ta.rsi(src, lengthRSI)
    k = ta.sma(ta.stoch(rsi1, rsi1, rsi1, lengthStoch), smoothK)
    d = ta.sma(k, smoothD)
    
    Returns: tuple of (k_values, d_values) as pandas Series
    """
    close_series = pd.Series(close)
    
    # Step 1: Calculate RSI
    rsi = calculate_rsi(close_series, period=rsi_length)
    
    # Step 2: Calculate Stochastic of RSI
    # ta.stoch(rsi1, rsi1, rsi1, lengthStoch) - uses same RSI for high/low/close
    stoch_rsi = calculate_stochastic(rsi, period=stoch_length)
    
    # Step 3: Smooth %K with SMA
    k = stoch_rsi.rolling(window=smooth_k).mean()
    
    # Step 4: Smooth %D (SMA of %K)
    d = k.rolling(window=smooth_d).mean()
    
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
    if len(ohlcv_data) < 50:
        raise ValueError(f"Insufficient data: need at least 50 candles, got {len(ohlcv_data)}")
    
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
    
    # Get latest valid values
    latest_k = k_series.iloc[-1]
    latest_d = d_series.iloc[-1]
    latest_timestamp = int(df['timestamp'].iloc[-1])
    
    return {
        'k': round(float(latest_k), 2) if not pd.isna(latest_k) else None,
        'd': round(float(latest_d), 2) if not pd.isna(latest_d) else None,
        'timestamp': latest_timestamp
    }
