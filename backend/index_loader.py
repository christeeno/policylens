import csv
import io
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
INDEX_CACHE_TTL_HOURS = int(os.getenv("INDEX_CACHE_TTL_HOURS", "24"))
INDEX_HTTP_TIMEOUT_SECONDS = int(os.getenv("INDEX_HTTP_TIMEOUT_SECONDS", "20"))
INDEX_LIVE_ON_MISS = os.getenv("INDEX_LIVE_ON_MISS", "0").lower() in {"1", "true", "yes"}
INDEX_CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "index_constituents")
LEGACY_UNIVERSE_FILE = os.path.join(os.path.dirname(__file__), "stock_universe.json")
REGISTRY_FILE = os.path.join(os.path.dirname(__file__), "index_registry.json")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _normalize_symbol(symbol: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9&-]", "", (symbol or "").upper())
    return cleaned.strip()


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None

    raw = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _pick_first(row: dict, candidates: list[str]) -> str:
    normalized = {str(key).strip().lower(): value for key, value in row.items()}
    for candidate in candidates:
        value = normalized.get(candidate.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _parse_weight(row: dict) -> float | None:
    raw = _pick_first(
        row,
        [
            "weightage(%)",
            "weightage (%)",
            "weight",
            "index weight",
            "index weight (%)",
        ],
    )
    if not raw:
        return None
    cleaned = raw.replace("%", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


@dataclass
class IndexDefinition:
    key: str
    display_name: str
    page_url: str
    rate_sensitivity: int
    default_type: str
    aliases: list[str]


@dataclass
class Constituent:
    ticker: str
    name: str
    sector: str
    source_index: str
    source_index_name: str
    weight: float | None
    rank: int
    exposure: int
    rate_sensitivity: int
    stock_type: str


class OfficialNiftyIndexUniverse:
    def __init__(self, registry_path: str = REGISTRY_FILE, cache_dir: str = INDEX_CACHE_DIR):
        registry_data = _load_json(registry_path)
        self.definitions = {
            key: IndexDefinition(
                key=key,
                display_name=value["display_name"],
                page_url=value["page_url"],
                rate_sensitivity=int(value.get("rate_sensitivity", 1)),
                default_type=value.get("default_type", "Index Constituent"),
                aliases=list(value.get("aliases", [])),
            )
            for key, value in registry_data.items()
        }
        self.alias_to_key = {}
        for key, definition in self.definitions.items():
            self.alias_to_key[key] = key
            for alias in definition.aliases:
                self.alias_to_key[alias] = key
        self.cache_dir = cache_dir
        _ensure_dir(self.cache_dir)

    def resolve_sector_key(self, value: str) -> str | None:
        normalized = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
        return self.alias_to_key.get(normalized)

    def available_sectors(self) -> list[str]:
        return sorted(self.definitions.keys())

    def load_for_sectors(self, sectors: list[str], force_refresh: bool = False) -> tuple[dict[str, list[Constituent]], list[dict]]:
        normalized_sectors = []
        for sector in sectors:
            resolved = self.resolve_sector_key(sector)
            if resolved and resolved not in normalized_sectors:
                normalized_sectors.append(resolved)

        if not normalized_sectors:
            normalized_sectors = ["broad_market"]

        universes: dict[str, list[Constituent]] = {}
        metadata: list[dict] = []
        for sector in normalized_sectors:
            constituents, meta = self.load_sector(sector, force_refresh=force_refresh)
            universes[sector] = constituents
            metadata.append(meta)
        return universes, metadata

    def load_sector(self, sector: str, force_refresh: bool = False) -> tuple[list[Constituent], dict]:
        definition = self.definitions[sector]
        cache_path = os.path.join(self.cache_dir, f"{sector}.json")
        cached = self._read_cache(cache_path)
        if cached and not force_refresh and not self._is_stale(cached):
            return self._deserialize_constituents(cached, definition), self._cache_metadata(cached, cache_path, sector)

        if not force_refresh and not INDEX_LIVE_ON_MISS:
            legacy = self._load_legacy_fallback(sector, definition)
            if legacy:
                fallback_meta = {
                    "sector": sector,
                    "index_name": definition.display_name,
                    "source": "legacy_fallback",
                    "cache_path": cache_path,
                    "warning": "Live fetch skipped because INDEX_LIVE_ON_MISS is disabled.",
                    "constituent_count": len(legacy),
                    "fetched_at": None,
                }
                return legacy, fallback_meta

        live_error = None
        try:
            constituents, discovered_csv_url = self._fetch_live(definition)
            snapshot = {
                "sector": definition.key,
                "display_name": definition.display_name,
                "page_url": definition.page_url,
                "csv_url": discovered_csv_url,
                "fetched_at": _utc_now().isoformat(),
                "constituents": [asdict(item) for item in constituents],
            }
            self._write_cache(cache_path, snapshot)
            meta = self._cache_metadata(snapshot, cache_path, sector)
            meta["source"] = "live"
            return constituents, meta
        except Exception as exc:  # noqa: BLE001
            live_error = str(exc)

        if cached:
            stale_meta = self._cache_metadata(cached, cache_path, sector)
            stale_meta["source"] = "stale_cache"
            stale_meta["warning"] = live_error
            return self._deserialize_constituents(cached, definition), stale_meta

        legacy = self._load_legacy_fallback(sector, definition)
        fallback_meta = {
            "sector": sector,
            "index_name": definition.display_name,
            "source": "legacy_fallback",
            "cache_path": cache_path,
            "warning": live_error,
            "constituent_count": len(legacy),
            "fetched_at": None,
        }
        return legacy, fallback_meta

    def _fetch_live(self, definition: IndexDefinition) -> tuple[list[Constituent], str]:
        page_html = self._http_get(definition.page_url)
        csv_url = self._discover_csv_url(definition.page_url, page_html)
        csv_text = self._http_get(csv_url)
        constituents = self._parse_constituents(definition, csv_text)
        if not constituents:
            raise ValueError(f"No constituents parsed for {definition.display_name}")
        return constituents, csv_url

    def _http_get(self, url: str) -> str:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml,text/csv,*/*",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(request, timeout=INDEX_HTTP_TIMEOUT_SECONDS) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")

    def _discover_csv_url(self, page_url: str, html: str) -> str:
        matches = re.findall(r'href=["\']([^"\']*IndexConstituent[^"\']+\.csv)["\']', html, flags=re.IGNORECASE)
        if not matches:
            raise ValueError(f"Could not discover constituent CSV URL from {page_url}")

        for match in matches:
            if "IndexConstituent" in match:
                return urllib.parse.urljoin(page_url, match)
        raise ValueError(f"Discovered constituent links were unusable for {page_url}")

    def _parse_constituents(self, definition: IndexDefinition, csv_text: str) -> list[Constituent]:
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = [row for row in reader if any(value for value in row.values())]
        if not rows:
            return []

        parsed_rows = []
        for row in rows:
            ticker = _normalize_symbol(
                _pick_first(row, ["symbol", "ticker", "company symbol", "trading symbol"])
            )
            name = _pick_first(row, ["company name", "company", "security name", "name"])
            if not ticker or not name:
                continue
            parsed_rows.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "weight": _parse_weight(row),
                }
            )

        if not parsed_rows:
            return []

        parsed_rows.sort(
            key=lambda row: (
                row["weight"] is None,
                -(row["weight"] or 0.0),
                row["ticker"],
            )
        )

        total = len(parsed_rows)
        constituents = []
        seen = set()
        for rank, row in enumerate(parsed_rows, start=1):
            ticker = row["ticker"]
            if ticker in seen:
                continue
            seen.add(ticker)
            constituents.append(
                Constituent(
                    ticker=ticker,
                    name=row["name"],
                    sector=definition.key,
                    source_index=definition.key,
                    source_index_name=definition.display_name,
                    weight=row["weight"],
                    rank=rank,
                    exposure=self._derive_exposure(row["weight"], rank, total),
                    rate_sensitivity=definition.rate_sensitivity,
                    stock_type=definition.default_type,
                )
            )
        return constituents

    def _derive_exposure(self, weight: float | None, rank: int, total: int) -> int:
        if weight is not None:
            if weight >= 8:
                return 5
            if weight >= 4:
                return 4
            if weight >= 2:
                return 3
            if weight >= 1:
                return 2
            return 1

        bucket = math.ceil((rank / max(total, 1)) * 5)
        return max(1, 6 - bucket)

    def _read_cache(self, cache_path: str) -> dict | None:
        if not os.path.exists(cache_path):
            return None
        try:
            return _load_json(cache_path)
        except (OSError, json.JSONDecodeError):
            return None

    def _write_cache(self, cache_path: str, payload: dict) -> None:
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def _is_stale(self, payload: dict) -> bool:
        fetched_at = _parse_iso8601(payload.get("fetched_at"))
        if fetched_at is None:
            return True
        return _utc_now() - fetched_at > timedelta(hours=INDEX_CACHE_TTL_HOURS)

    def _deserialize_constituents(self, payload: dict, definition: IndexDefinition) -> list[Constituent]:
        items = []
        for item in payload.get("constituents", []):
            items.append(
                Constituent(
                    ticker=item["ticker"],
                    name=item["name"],
                    sector=item.get("sector", definition.key),
                    source_index=item.get("source_index", definition.key),
                    source_index_name=item.get("source_index_name", definition.display_name),
                    weight=item.get("weight"),
                    rank=int(item.get("rank", 0)),
                    exposure=int(item.get("exposure", 1)),
                    rate_sensitivity=int(item.get("rate_sensitivity", definition.rate_sensitivity)),
                    stock_type=item.get("stock_type", definition.default_type),
                )
            )
        return items

    def _cache_metadata(self, payload: dict, cache_path: str, sector: str) -> dict:
        return {
            "sector": sector,
            "index_name": payload.get("display_name", self.definitions[sector].display_name),
            "source": "cache",
            "cache_path": cache_path,
            "fetched_at": payload.get("fetched_at"),
            "constituent_count": len(payload.get("constituents", [])),
            "csv_url": payload.get("csv_url"),
            "page_url": payload.get("page_url", self.definitions[sector].page_url),
        }

    def _load_legacy_fallback(self, sector: str, definition: IndexDefinition) -> list[Constituent]:
        if not os.path.exists(LEGACY_UNIVERSE_FILE):
            return []
        legacy = _load_json(LEGACY_UNIVERSE_FILE).get(sector, {})
        items = []
        for rank, (ticker, data) in enumerate(legacy.items(), start=1):
            items.append(
                Constituent(
                    ticker=ticker,
                    name=data.get("name", ticker),
                    sector=sector,
                    source_index=sector,
                    source_index_name=f"{definition.display_name} (Legacy Seed)",
                    weight=None,
                    rank=rank,
                    exposure=int(data.get("exposure", 1)),
                    rate_sensitivity=int(data.get("rate_sensitivity", definition.rate_sensitivity)),
                    stock_type=data.get("type", definition.default_type),
                )
            )
        return items
