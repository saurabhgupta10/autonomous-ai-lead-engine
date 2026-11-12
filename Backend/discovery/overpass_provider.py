"""
overpass_provider.py
--------------------
OpenStreetMap Overpass & Nominatim Discovery Provider.

Compliant with OpenStreetMap & Nominatim Usage Policies:
- Enforces >= 1.1s rate limiting on Nominatim queries (max 1 req/sec policy).
- Local persistent disk caching with configurable TTL (default 24h) to eliminate duplicate upstream queries.
- Clear identifying User-Agent containing project documentation link and operator contact email.
- ODbL attribution recorded on all discovered records ("OpenStreetMap (ODbL)").
"""

from __future__ import annotations

import abc
import hashlib
import json
import logging
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

        records: list[BusinessRecord] = []

        # 2. Attempt Overpass query first
        records = self._query_overpass(query, country_norm, ind_cfg)
        if records:
            logger.info("Overpass returned %d valid records.", len(records))
        else:
            # 3. Fall back to rate-throttled Nominatim POI directory
            logger.info("Overpass busy or returned 0. Using rate-throttled Nominatim directory.")
            records = self._query_nominatim(query, country_norm, search_term)

        # 4. Save to persistent cache
        if records:
            self._write_cache(query, country_norm, search_term, records)

        return records[: query.limit]

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
        self, query: DiscoveryQuery, country: str, ind_cfg: dict[str, Any]
    ) -> list[BusinessRecord]:
        osm_filters = "".join(
            f'node["{k}"="{v}"](area.city); way["{k}"="{v}"](area.city); '
            for k, v in ind_cfg["osm_keys"][:2]
        )

        ql = f"""
        [out:json][timeout:15];
        area["name"="{query.city}"]->.city;
        (
          {osm_filters}
        );
        out center {query.limit};
        """

        headers = {"User-Agent": config.OSM_USER_AGENT, "Accept": "application/json"}

        for endpoint in OVERPASS_MIRRORS:
            try:
                resp = requests.post(
                    endpoint, data={"data": ql}, headers=headers, timeout=12
                )
                if resp.status_code == 200:
                    data = resp.json()
                    elements = data.get("elements", [])
                    records = []
                    for el in elements:
                        rec = self._element_to_record(el, query, country, ind_cfg["category_name"])
                        if rec:
                            records.append(rec)
                    if records:
                        return records
            except Exception as exc:
                logger.debug("Overpass endpoint %s failed: %s", endpoint, exc)
                continue

        return []

    def _query_nominatim(
        self, query: DiscoveryQuery, country: str, search_term: str
    ) -> list[BusinessRecord]:
        global _last_nominatim_request_time

        # Enforce OSM Policy: Maximum 1 request per second
        elapsed = time.time() - _last_nominatim_request_time
        if elapsed < _NOMINATIM_MIN_INTERVAL:
            sleep_needed = _NOMINATIM_MIN_INTERVAL - elapsed
            time.sleep(sleep_needed)

        _last_nominatim_request_time = time.time()

        params = {
            "q": f"{search_term} in {query.city}, {country}",
            "format": "json",
            "limit": min(query.limit * 2, 50),
            "addressdetails": 1,
            "extratags": 1,
        }
        headers = {"User-Agent": config.OSM_USER_AGENT}

        try:
            resp = requests.get(NOMINATIM_SEARCH_URL, params=params, headers=headers, timeout=12)
            if resp.status_code != 200:
                logger.warning("Nominatim returned status %d", resp.status_code)
                return []

            items = resp.json()
            if not isinstance(items, list):
                return []

            results: list[BusinessRecord] = []
            seen_names: set[str] = set()

            for it in items:
                name = it.get("name") or it.get("display_name", "").split(",")[0].strip()
                if not name or len(name) < 2 or name.lower() in seen_names:
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

            return results

        except Exception as exc:
            logger.error("OSM Nominatim query failed: %s", exc)
            return []

    def _element_to_record(
        self, el: dict[str, Any], query: DiscoveryQuery, country: str, default_category: str
    ) -> BusinessRecord | None:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("brand")
        if not name:
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
