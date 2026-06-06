import math
from typing import Any

import pandas as pd

try:
    import pandas_ta as ta
except ImportError as exc:
    raise ImportError(
        "technical_indicators requires pandas-ta. Install backend dependencies first."
    ) from exc


REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


def _normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized.columns = [str(column).lower() for column in normalized.columns]
    return normalized


def _validate_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("ohlcv_df must be a pandas DataFrame")

    normalized = _normalize_columns(frame)
    missing = [column for column in REQUIRED_COLUMNS if column not in normalized.columns]
    if missing:
        raise ValueError(f"OHLCV DataFrame is missing required columns: {', '.join(missing)}")

    if normalized.empty:
        raise ValueError("OHLCV DataFrame must contain at least one row")

    for column in REQUIRED_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    if normalized[list(REQUIRED_COLUMNS)].isnull().all().any():
        raise ValueError("OHLCV DataFrame contains a required column with no numeric values")

    return normalized


def _to_json_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return round(float(value), 6)
    return value


def _series_payload(series: pd.Series) -> dict[str, Any]:
    return {
        "value": _to_json_value(series.iloc[-1]),
        "series": [_to_json_value(value) for value in series.tolist()],
    }


def calculate_technical_indicators(ohlcv_df: pd.DataFrame) -> dict[str, Any]:
    frame = _validate_ohlcv(ohlcv_df)

    rsi = ta.rsi(frame["close"], length=14)
    macd = ta.macd(frame["close"], fast=12, slow=26, signal=9)
    ema20 = ta.ema(frame["close"], length=20)
    ema50 = ta.ema(frame["close"], length=50)
    ema200 = ta.ema(frame["close"], length=200)
    bbands = ta.bbands(frame["close"], length=20, std=2.0)
    atr = ta.atr(frame["high"], frame["low"], frame["close"], length=14)
    adx = ta.adx(frame["high"], frame["low"], frame["close"], length=14)

    vwap_frame = frame.copy()
    if not isinstance(vwap_frame.index, pd.DatetimeIndex):
        vwap_frame.index = pd.date_range(
            start="2024-01-01", periods=len(vwap_frame), freq="min"
        )
    vwap = ta.vwap(
        high=vwap_frame["high"],
        low=vwap_frame["low"],
        close=vwap_frame["close"],
        volume=vwap_frame["volume"],
    )

    return {
        "rsi": _series_payload(rsi),
        "macd": {
            "macd": _series_payload(macd["MACD_12_26_9"]),
            "histogram": _series_payload(macd["MACDh_12_26_9"]),
            "signal": _series_payload(macd["MACDs_12_26_9"]),
        },
        "ema20": _series_payload(ema20),
        "ema50": _series_payload(ema50),
        "ema200": _series_payload(ema200),
        "bollinger_bands": {
            "lower": _series_payload(bbands["BBL_20_2.0"]),
            "middle": _series_payload(bbands["BBM_20_2.0"]),
            "upper": _series_payload(bbands["BBU_20_2.0"]),
            "bandwidth": _series_payload(bbands["BBB_20_2.0"]),
            "percent": _series_payload(bbands["BBP_20_2.0"]),
        },
        "atr": _series_payload(atr),
        "adx": {
            "adx": _series_payload(adx["ADX_14"]),
            "di_plus": _series_payload(adx["DMP_14"]),
            "di_minus": _series_payload(adx["DMN_14"]),
        },
        "vwap": _series_payload(vwap),
    }
