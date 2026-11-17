"""
overpass_provider.py
--------------------
OpenStreetMap Overpass & Nominatim Discovery Provider.

Compliant with OpenStreetMap & Nominatim Usage Policies:
- Enforces >= 1.1s rate limiting on Nominatim queries (max 1 req/sec policy).
- Local persistent disk caching with configurable TTL (default 24h) to eliminate duplicate upstream queries.
- Clear identifying User-Agent containing project documentation link and operator contact email.
- ODbL attribution recorded on all discovered records ("OpenStreetMap (ODbL)").
- Real business discovery: uses spatial bounding box geocoding and intelligent multi-term POI retrieval.
"""

from __future__ import annotations

import abc
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

import config
from discovery.discovery_schemas import BusinessRecord, DiscoveryQuery
from discovery.discovery_validator import get_industry_config, normalize_country

logger = logging.getLogger(__name__)

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"

# Rate limiter tracking for Nominatim
_last_nominatim_request_time: float = 0.0
_NOMINATIM_MIN_INTERVAL: float = 1.1  # Seconds between requests (OSM policy: max 1/sec)

# In-memory geocode cache: "city, country" -> dict(bbox, lat, lon)
_GEOCODE_CACHE: dict[str, dict[str, Any] | None] = {}

# Generic names that are not distinct commercial businesses
_GENERIC_NAMES = {
    "gym", "fitness", "restaurant", "cafe", "coffee", "food", "bar",
    "salon", "hair", "dentist", "doctor", "clinic", "hospital",
    "shop", "store", "supermarket", "hotel", "motel", "hostel",
    "logistics", "warehouse", "depot", "bank", "atm", "pharmacy",
    "toilet", "public toilet", "bench", "parking", "car park",
    "real estate", "realtor", "office", "bakery", "lawyer",
}


def _throttle_nominatim() -> None:
    """Enforce OSM Policy: Maximum 1 request per second."""
    global _last_nominatim_request_time
    elapsed = time.time() - _last_nominatim_request_time
    if elapsed < _NOMINATIM_MIN_INTERVAL:
        sleep_needed = _NOMINATIM_MIN_INTERVAL - elapsed
        time.sleep(sleep_needed)
    _last_nominatim_request_time = time.time()


class BaseDiscoveryProvider(abc.ABC):
    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        pass

    @abc.abstractmethod
    def discover_businesses(self, query: DiscoveryQuery) -> list[BusinessRecord]:
        pass


class OverpassDiscoveryProvider(BaseDiscoveryProvider):
    @property
    def provider_name(self) -> str:
        return "OpenStreetMap (ODbL)"

    def discover_businesses(self, query: DiscoveryQuery) -> list[BusinessRecord]:
        country_norm = normalize_country(query.country)
        ind_cfg = get_industry_config(query.industry)
        search_term = query.keyword or ind_cfg["search_term"]

        # 1. Check local cache first (OSM Policy: Cache your results)
        cached = self._read_cache(query, country_norm, search_term)
        if cached is not None:
            logger.info("Serving %d businesses from local OSM cache (query cached).", len(cached))
            return cached[: query.limit]

        logger.info(
            "Starting OSM discovery: '%s' in %s, %s (limit: %d)",
            search_term,
            query.city,
            country_norm,
            query.limit,
        )

        # 2. Geocode the target city to get precise bounding box & coordinates
        geo_data = self._geocode_location(query.city, country_norm)

        records: list[BusinessRecord] = []

        # 3. Attempt Overpass query using spatial bounding box
        if geo_data and geo_data.get("bbox"):
            records = self._query_overpass(query, country_norm, ind_cfg, geo_data)
            if records:
                logger.info("Overpass returned %d valid records.", len(records))

        # 4. Fall back to rate-throttled Nominatim bounded POI directory
        if len(records) < query.limit:
            needed = query.limit - len(records)
            logger.info("Using rate-throttled Nominatim directory (need %d more records)...", needed)
            nom_records = self._query_nominatim(query, country_norm, search_term, ind_cfg, geo_data, needed)
            # Combine without duplicates, preferring records with website/contact data
            existing_name_map = {r.business_name.lower().strip(): idx for idx, r in enumerate(records)}
            existing_ids = {r.provider_id for r in records}
            for nr in nom_records:
                clean_name = nr.business_name.lower().strip()
                if clean_name in existing_name_map:
                    idx = existing_name_map[clean_name]
                    # If existing record lacks website/phone, upgrade to the richer listing
                    if not records[idx].website and nr.website:
                        records[idx] = nr
                    continue
                if nr.provider_id in existing_ids:
                    continue
                records.append(nr)
                existing_name_map[clean_name] = len(records) - 1
                existing_ids.add(nr.provider_id)
                if len(records) >= query.limit:
                    break

        # 5. Save genuine records to persistent cache
        if records:
            self._write_cache(query, country_norm, search_term, records)

        return records[: query.limit]

    # ── Geocoding Helper ──────────────────────────────────────────────────────

    def _geocode_location(self, city: str, country: str) -> dict[str, Any] | None:
        """Resolve city and country into bounding box and center coordinates with caching."""
        cache_key = f"{city.strip().lower()}|{country.strip().lower()}"
        if cache_key in _GEOCODE_CACHE:
            return _GEOCODE_CACHE[cache_key]

        geo_cache_file = config.CACHE_DIR / f"geo_{hashlib.sha256(cache_key.encode('utf-8')).hexdigest()[:16]}.json"
        if geo_cache_file.exists():
            try:
                data = json.loads(geo_cache_file.read_text(encoding="utf-8"))
                _GEOCODE_CACHE[cache_key] = data
                return data
            except Exception:
                pass

        _throttle_nominatim()

        headers = {"User-Agent": config.OSM_USER_AGENT, "Accept": "application/json"}
        # Try structured city + country first, then query string
        queries = [
            {"city": city, "country": country, "format": "json", "limit": 1},
            {"q": f"{city}, {country}", "format": "json", "limit": 1},
            {"q": city, "format": "json", "limit": 1},
        ]

        for p in queries:
            try:
                resp = requests.get(NOMINATIM_SEARCH_URL, params=p, headers=headers, timeout=6)
                if resp.status_code == 200:
                    items = resp.json()
                    if isinstance(items, list) and items:
                        it = items[0]
                        bbox_raw = it.get("boundingbox")
                        if bbox_raw and len(bbox_raw) == 4:
                            south, north, west, east = (
                                float(bbox_raw[0]),
                                float(bbox_raw[1]),
                                float(bbox_raw[2]),
                                float(bbox_raw[3]),
                            )
                            lat = float(it.get("lat")) if it.get("lat") else (south + north) / 2
                            lon = float(it.get("lon")) if it.get("lon") else (west + east) / 2
                            result = {
                                "bbox": [south, north, west, east],
                                "center": [lat, lon],
                                "display_name": it.get("display_name", f"{city}, {country}"),
                                "osm_type": it.get("osm_type", "relation"),
                                "osm_id": it.get("osm_id", ""),
                            }
                            _GEOCODE_CACHE[cache_key] = result
                            try:
                                geo_cache_file.write_text(json.dumps(result), encoding="utf-8")
                            except Exception:
                                pass
                            return result
            except Exception as exc:
                logger.debug("Geocoding attempt for %s failed: %s", city, exc)

        _GEOCODE_CACHE[cache_key] = None
        return None

    # ── Cache Helpers ─────────────────────────────────────────────────────────

    def _get_cache_path(self, query: DiscoveryQuery, country: str, search_term: str) -> Path:
        key = f"{country}|{query.city}|{search_term}".lower().strip()
        hash_digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return config.CACHE_DIR / f"osm_{hash_digest}.json"

    def _read_cache(
        self, query: DiscoveryQuery, country: str, search_term: str
    ) -> list[BusinessRecord] | None:
        path = self._get_cache_path(query, country, search_term)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data.get("cached_at", "1970-01-01T00:00:00+00:00"))
            age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
            if age_hours > config.CACHE_TTL_HOURS:
                return None  # expired
            records = [BusinessRecord.model_validate(r) for r in data.get("records", [])]
            return records
        except Exception as exc:
            logger.debug("Cache read error for %s: %s", path, exc)
            return None

    def _write_cache(
        self, query: DiscoveryQuery, country: str, search_term: str, records: list[BusinessRecord]
    ) -> None:
        path = self._get_cache_path(query, country, search_term)
        try:
            payload = {
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "query": query.model_dump(),
                "records": [r.model_dump() for r in records],
            }
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.debug("Cache write error: %s", exc)

    # ── Upstream Query Engines ────────────────────────────────────────────────

    def _query_overpass(
        self,
        query: DiscoveryQuery,
        country: str,
        ind_cfg: dict[str, Any],
        geo_data: dict[str, Any],
    ) -> list[BusinessRecord]:
        bbox = geo_data.get("bbox")
        if not bbox or len(bbox) != 4:
            return []

        south, north, west, east = bbox[0], bbox[1], bbox[2], bbox[3]

        osm_filters = "".join(
            f'node["{k}"="{v}"]({south},{west},{north},{east}); way["{k}"="{v}"]({south},{west},{north},{east}); relation["{k}"="{v}"]({south},{west},{north},{east}); '
            for k, v in ind_cfg["osm_keys"][:4]
        )

        ql = f"""
        [out:json][timeout:10];
        (
          {osm_filters}
        );
        out center {query.limit * 2};
        """

        headers = {"User-Agent": config.OSM_USER_AGENT, "Accept": "application/json"}

        for endpoint in OVERPASS_MIRRORS:
            try:
                resp = requests.post(
                    endpoint, data={"data": ql}, headers=headers, timeout=(4.0, 8.0)
                )
                if resp.status_code == 200:
                    data = resp.json()
                    elements = data.get("elements", [])
                    records: list[BusinessRecord] = []
                    seen_names: set[str] = set()

                    for el in elements:
                        rec = self._element_to_record(el, query, country, ind_cfg["category_name"])
                        if rec and rec.business_name.lower() not in seen_names:
                            seen_names.add(rec.business_name.lower())
                            records.append(rec)
                    if records:
                        return records
                elif resp.status_code in {429, 502, 504}:
                    logger.debug("Overpass endpoint %s busy (status %d).", endpoint, resp.status_code)
            except Exception as exc:
                logger.debug("Overpass endpoint %s failed or timed out: %s", endpoint, exc)
                continue

        return []

    def _query_nominatim(
        self,
        query: DiscoveryQuery,
        country: str,
        search_term: str,
        ind_cfg: dict[str, Any],
        geo_data: dict[str, Any] | None,
        needed_count: int,
    ) -> list[BusinessRecord]:
        terms = ind_cfg.get("search_terms") or [search_term]
        if search_term not in terms:
            terms = [search_term] + terms

        results: list[BusinessRecord] = []
        seen_names: set[str] = set()

        bbox = geo_data.get("bbox") if geo_data else None
        viewbox_str = f"{bbox[2]},{bbox[1]},{bbox[3]},{bbox[0]}" if bbox else None  # west, north, east, south

        headers = {"User-Agent": config.OSM_USER_AGENT, "Accept": "application/json"}

        for term in terms:
            _throttle_nominatim()

            params: dict[str, Any] = {
                "q": term,
                "format": "json",
                "limit": min(needed_count * 2, 50),
                "addressdetails": 1,
                "extratags": 1,
            }

            if viewbox_str:
                params["viewbox"] = viewbox_str
                params["bounded"] = 1
            else:
                params["q"] = f"{term} in {query.city}, {country}"

            try:
                resp = requests.get(NOMINATIM_SEARCH_URL, params=params, headers=headers, timeout=8)
                if resp.status_code == 429:
                    logger.warning("Nominatim rate-limited (429). Waiting 2.0s before retrying...")
                    time.sleep(2.0)
                    resp = requests.get(NOMINATIM_SEARCH_URL, params=params, headers=headers, timeout=8)

                if resp.status_code != 200:
                    logger.warning("Nominatim returned status %d for query %s", resp.status_code, params.get("q"))
                    continue

                items = resp.json()
                if not isinstance(items, list):
                    continue

                for it in items:
                    name = it.get("name") or it.get("display_name", "").split(",")[0].strip()
                    if not self._is_valid_business_name(name):
                        continue

                    if name.lower() in seen_names:
                        continue
                    seen_names.add(name.lower())

                    extra = it.get("extratags") or {}
                    address = it.get("address") or {}

                    raw_website = (
                        extra.get("website")
                        or extra.get("contact:website")
                        or extra.get("url")
                        or ""
                    ).strip()
                    website = self._clean_website(raw_website)

                    phone = (
                        extra.get("phone")
                        or extra.get("contact:phone")
                        or extra.get("telephone")
                        or None
                    )
                    if phone:
                        phone = str(phone).strip()

                    email = (
                        extra.get("email")
                        or extra.get("contact:email")
                        or None
                    )
                    if email:
                        email = str(email).strip()

                    osm_type = it.get("osm_type", "node")
                    osm_id = it.get("osm_id", "")
                    provider_id = f"osm_{osm_type}_{osm_id}"
                    source_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"

                    try:
                        lat = float(it.get("lat")) if it.get("lat") else None
                        lon = float(it.get("lon")) if it.get("lon") else None
                    except (ValueError, TypeError):
                        lat, lon = None, None

                    city_resolved = (
                        address.get("city")
                        or address.get("town")
                        or address.get("suburb")
                        or query.city
                    )

                    record = BusinessRecord(
                        provider_id=provider_id,
                        business_name=name,
                        business_category=query.industry,
                        country=country,
                        city=city_resolved,
                        latitude=lat,
                        longitude=lon,
                        website=website or None,
                        email=email or None,
                        phone=phone or None,
                        discovery_provider="OpenStreetMap (ODbL)",
                        source_url=source_url,
                    )
                    results.append(record)

                    if len(results) >= needed_count:
                        return results

            except Exception as exc:
                logger.error("OSM Nominatim query failed for '%s': %s", term, exc)

        return results

    def _is_valid_business_name(self, name: str) -> bool:
        """Filter out generic POI labels and meaningless names."""
        if not name:
            return False
        clean = name.strip()
        if len(clean) < 2:
            return False
        # Remove numbers and punctuation to check generic words
        alpha_clean = re.sub(r"[^\w\s]", "", clean).strip().lower()
        if alpha_clean in _GENERIC_NAMES:
            return False
        # Must contain at least one letter
        if not any(c.isalpha() for c in clean):
            return False
        return True

    def _element_to_record(
        self, el: dict[str, Any], query: DiscoveryQuery, country: str, default_category: str
    ) -> BusinessRecord | None:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("brand")
        if not self._is_valid_business_name(name):
            return None

        el_type = el.get("type", "node")
        el_id = el.get("id", "")
        provider_id = f"osm_{el_type}_{el_id}"
        source_url = f"https://www.openstreetmap.org/{el_type}/{el_id}"

        raw_website = tags.get("website") or tags.get("contact:website") or tags.get("url") or ""
        website = self._clean_website(raw_website)

        email = tags.get("email") or tags.get("contact:email") or None
        phone = tags.get("phone") or tags.get("contact:phone") or None

        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")

        return BusinessRecord(
            provider_id=provider_id,
            business_name=name,
            business_category=query.industry or default_category,
            country=country,
            city=query.city,
            latitude=lat,
            longitude=lon,
            website=website or None,
            email=email,
            phone=phone,
            discovery_provider="OpenStreetMap (ODbL)",
            source_url=source_url,
        )

    def _clean_website(self, raw_url: str) -> str | None:
        if not raw_url or raw_url.lower() in {"none", "n/a", "null"}:
            return None
        url = raw_url.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        try:
            p = urlparse(url)
            if p.netloc and "." in p.netloc:
                return url
        except Exception:
            pass
        return None
