import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import yfinance as yf


logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 15 * 60
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1
DEFAULT_PERIOD = "6mo"
VALID_INTERVALS = {"5m", "30m", "1h", "1d", "1wk", "1mo"}
NIFTY_INDEX_SYMBOLS = {
    "NIFTY 50": "^NSEI",
    "NIFTY50": "^NSEI",
    "NIFTY": "^NSEI",
    "NIFTY BANK": "^NSEBANK",
    "BANKNIFTY": "^NSEBANK",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY FINANCIAL SERVICES": "NIFTY_FIN_SERVICE.NS",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "NIFTY MIDCAP 50": "^NSEMDCP50",
    "NIFTY NEXT 50": "^NSMIDCP",
}

_CACHE: dict[str, dict] = {}


class StockDataError(Exception):
    """Base error for stock data failures."""


class StockNotFoundError(StockDataError):
    """Raised when a ticker or index cannot be resolved."""


class StockDataUnavailableError(StockDataError):
    """Raised when market data cannot be fetched."""


@dataclass(frozen=True)
class HistoryRequest:
    normalized_ticker: str
    period: str
    interval: str
    start: str | None
    end: str | None


def normalize_ticker(raw_ticker: str) -> str:
    ticker = (raw_ticker or "").strip().upper()
    if not ticker:
        raise StockNotFoundError("Ticker is required.")

    if ticker in NIFTY_INDEX_SYMBOLS:
        return NIFTY_INDEX_SYMBOLS[ticker]

    compact = " ".join(ticker.split())
    if compact in NIFTY_INDEX_SYMBOLS:
        return NIFTY_INDEX_SYMBOLS[compact]

    if ticker.startswith("^"):
        return ticker

    if ticker.endswith(".NS"):
        return ticker

    return f"{ticker}.NS"


def build_history_request(
    ticker: str,
    period: str = DEFAULT_PERIOD,
    interval: str = "1d",
    start: str | None = None,
    end: str | None = None,
) -> HistoryRequest:
    if interval not in VALID_INTERVALS:
        raise StockDataError(f"Unsupported interval '{interval}'. Allowed values: {sorted(VALID_INTERVALS)}")

    if start and end:
        _validate_iso_date(start, "start")
        _validate_iso_date(end, "end")
        period = ""
    elif start or end:
        raise StockDataError("Both start and end must be provided together.")

    return HistoryRequest(
        normalized_ticker=normalize_ticker(ticker),
        period=period,
        interval=interval,
        start=start,
        end=end,
    )


def _validate_iso_date(value: str, field_name: str) -> None:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise StockDataError(f"Invalid {field_name} date '{value}'. Expected YYYY-MM-DD.") from exc


def _cache_key(request: HistoryRequest) -> str:
    return "|".join(
        [
            request.normalized_ticker,
            request.period,
            request.interval,
            request.start or "",
            request.end or "",
        ]
    )


def _get_cached_payload(cache_key: str) -> dict | None:
    entry = _CACHE.get(cache_key)
    if not entry:
        return None

    if datetime.utcnow() - entry["cached_at"] > timedelta(seconds=CACHE_TTL_SECONDS):
        _CACHE.pop(cache_key, None)
        return None
    return entry["payload"]


def _store_cache_payload(cache_key: str, payload: dict) -> None:
    _CACHE[cache_key] = {
        "cached_at": datetime.utcnow(),
        "payload": payload,
    }


def fetch_stock_history(
    ticker: str,
    period: str = DEFAULT_PERIOD,
    interval: str = "1d",
    start: str | None = None,
    end: str | None = None,
) -> dict:
    request = build_history_request(ticker, period=period, interval=interval, start=start, end=end)
    cache_key = _cache_key(request)
    cached_payload = _get_cached_payload(cache_key)
    if cached_payload is not None:
        return cached_payload

    payload = _download_history_with_retries(request)
    _store_cache_payload(cache_key, payload)
    return payload


def _download_history_with_retries(request: HistoryRequest) -> dict:
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return _download_history(request)
        except StockNotFoundError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "Stock history fetch failed for %s on attempt %s/%s: %s",
                request.normalized_ticker,
                attempt,
                MAX_RETRIES,
                exc,
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

    raise StockDataUnavailableError(
        f"Unable to fetch stock history for {request.normalized_ticker} after {MAX_RETRIES} attempts."
    ) from last_error


def _download_history(request: HistoryRequest) -> dict:
    ticker = yf.Ticker(request.normalized_ticker)
    history_args = {
        "interval": request.interval,
        "auto_adjust": False,
    }
    if request.start and request.end:
        history_args["start"] = request.start
        history_args["end"] = request.end
    else:
        history_args["period"] = request.period

    dataframe = ticker.history(**history_args)
    if dataframe is None or dataframe.empty:
        raise StockNotFoundError(f"No OHLCV history found for {request.normalized_ticker}.")

    rows = []
    for index, row in dataframe.iterrows():
        timestamp = index.to_pydatetime() if hasattr(index, "to_pydatetime") else index
        rows.append(
            {
                "date": _serialize_timestamp(timestamp),
                "open": _to_number(row.get("Open")),
                "high": _to_number(row.get("High")),
                "low": _to_number(row.get("Low")),
                "close": _to_number(row.get("Close")),
                "volume": int(row.get("Volume", 0) or 0),
            }
        )

    return {
        "ticker": request.normalized_ticker,
        "interval": request.interval,
        "period": request.period or None,
        "start": request.start,
        "end": request.end,
        "currency": getattr(ticker, "fast_info", {}).get("currency"),
        "ohlcv": rows,
    }


def _serialize_timestamp(value: datetime | date) -> str:
    if isinstance(value, datetime):
        if value.time() == datetime.min.time():
            return value.date().isoformat()
        return value.isoformat()
    return value.isoformat()


def _to_number(value: object) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None
