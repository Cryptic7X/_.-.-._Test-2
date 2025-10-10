"""
Stochastic RSI Calculation - Exact Pine Script Logic
Translates Pine Script ta.rsi and ta.stoch functions
"""
import pandas as pd
import numpy as np
from utils.logging_setup import setup_logger

logger = setup_logger(__name__)


def calculate_rsi(src, length):
    """
    Calculate RSI exactly as Pine Script ta.rsi() does
    Uses Wilder's smoothing method (RMA)

    Args:
        src: Price series (typically close prices)
        length: RSI period length

    Returns:
        RSI values as pandas Series
    """
    delta = src.diff()

    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    # Use Wilder's smoothing (RMA - Running Moving Average)
    # This matches Pine Script's ta.rma() used in ta.rsi()
    avg_gain = gain.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, min_periods=length, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_stoch(src, high, low, length):
    """
    Calculate Stochastic exactly as Pine Script ta.stoch() does

    In Pine Script: ta.stoch(src, high, low, length)
    For Stochastic RSI: ta.stoch(rsi1, rsi1, rsi1, lengthStoch)
    This means we're finding where RSI is within its own range

    Args:
        src: Source series (for StochRSI, this is RSI itself)
        high: High series (for StochRSI, this is also RSI)
        low: Low series (for StochRSI, this is also RSI)
        length: Lookback period

    Returns:
        Stochastic values as pandas Series
    """
    lowest_low = low.rolling(window=length, min_periods=length).min()
    highest_high = high.rolling(window=length, min_periods=length).max()

    stoch = 100 * (src - lowest_low) / (highest_high - lowest_low)

    # Handle division by zero
    stoch = stoch.replace([np.inf, -np.inf], np.nan)

    return stoch


def calculate_stochastic_rsi(close_prices, length_rsi=14, length_stoch=14, smooth_k=3, smooth_d=3):
    """
    Calculate Stochastic RSI using exact Pine Script logic

    Pine Script code:
    rsi1 = ta.rsi(src, lengthRSI)
    k = ta.sma(ta.stoch(rsi1, rsi1, rsi1, lengthStoch), smoothK)
    d = ta.sma(k, smoothD)

    Args:
        close_prices: List or array of close prices
        length_rsi: RSI period (default 14)
        length_stoch: Stochastic period (default 14)
        smooth_k: K line smoothing period (default 3)
        smooth_d: D line smoothing period (default 3)

    Returns:
        Dictionary with 'k' and 'd' values, or None if calculation fails
    """
    try:
        # Convert to pandas Series
        src = pd.Series(close_prices)

        # Step 1: Calculate RSI (matching Pine Script ta.rsi)
        rsi1 = calculate_rsi(src, length_rsi)

        # Step 2: Calculate Stochastic of RSI (matching Pine Script ta.stoch)
        # ta.stoch(rsi1, rsi1, rsi1, lengthStoch) means:
        # Find where current RSI is within its own high/low range
        stoch_rsi = calculate_stoch(rsi1, rsi1, rsi1, length_stoch)

        # Step 3: Smooth with SMA to get K line (matching Pine Script ta.sma)
        k = stoch_rsi.rolling(window=smooth_k, min_periods=smooth_k).mean()

        # Step 4: Smooth K to get D line (matching Pine Script ta.sma)
        d = k.rolling(window=smooth_d, min_periods=smooth_d).mean()

        # Get the most recent values
        k_current = k.iloc[-1] if not pd.isna(k.iloc[-1]) else None
        d_current = d.iloc[-1] if not pd.isna(d.iloc[-1]) else None

        if k_current is None or d_current is None:
            logger.warning("Insufficient data for Stochastic RSI calculation")
            return None

        return {
            'k': round(k_current, 2),
            'd': round(d_current, 2),
            'k_series': k,
            'd_series': d
        }

    except Exception as e:
        logger.error(f"Error calculating Stochastic RSI: {e}")
        return None


def determine_signal(k_value, d_value, overbought=80, oversold=20):
    """
    Determine if K and D are in overbought or oversold zones

    Args:
        k_value: Current K value
        d_value: Current D value
        overbought: Overbought threshold (default 80)
        oversold: Oversold threshold (default 20)

    Returns:
        Signal type: 'OVERBOUGHT', 'OVERSOLD', or 'NEUTRAL'
    """
    # Both K and D should be in the zone for signal
    if k_value >= overbought and d_value >= overbought:
        return 'OVERBOUGHT'
    elif k_value <= oversold and d_value <= oversold:
        return 'OVERSOLD'
    else:
        return 'NEUTRAL'
