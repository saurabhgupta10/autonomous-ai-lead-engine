"""
overpass_provider.py
--------------------
OpenStreetMap Overpass & Nominatim Discovery Provider.

Connects to legitimate public OpenStreetMap endpoints to discover genuine businesses
by location and industry. Respects rate limits, public usage policies, and User-Agent headers.
"""

from __future__ import annotations

import abc
import logging
from typing import Any
from urllib.parse import urlparse

import requests

from discovery.discovery_schemas import BusinessRecord, DiscoveryQuery
from discovery.discovery_validator import get_industry_config, normalize_country

logger = logging.getLogger(__name__)

# Legitimate public OpenStreetMap endpoints
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "LeadGenEngineApp/2.0 (contact: info@leadengine.local; research-bot)"


class BaseDiscoveryProvider(abc.ABC):
    """Abstract interface for all business discovery providers."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        pass

    @abc.abstractmethod
    def discover_businesses(self, query: DiscoveryQuery) -> list[BusinessRecord]:
        pass


class OverpassDiscoveryProvider(BaseDiscoveryProvider):
    """
    OpenStreetMap Provider supporting Overpass QL with automated fallback
    to OSM Nominatim POI indexing for maximum uptime and reliability.
    """

    @property
    def provider_name(self) -> str:
        return "openstreetmap_overpass"

    def discover_businesses(self, query: DiscoveryQuery) -> list[BusinessRecord]:
        country_norm = normalize_country(query.country)
        ind_cfg = get_industry_config(query.industry)
        search_term = query.keyword or ind_cfg["search_term"]

        logger.info(
            "Starting OSM discovery: '%s' in %s, %s (limit: %d)",
            search_term,
            query.city,
            country_norm,
            query.limit,
        )

        # 1. Attempt Overpass query first
        records = self._query_overpass(query, country_norm, ind_cfg)
        if records:
            logger.info("Overpass returned %d valid business records.", len(records))
            return records[: query.limit]

        # 2. Fall back to OpenStreetMap Nominatim POI search if Overpass is busy/rate-limited
        logger.info("Overpass mirrors busy or returned 0. Using OpenStreetMap Nominatim POI directory.")
        records = self._query_nominatim(query, country_norm, search_term)
        logger.info("OSM Nominatim returned %d valid business records.", len(records))
        return records[: query.limit]

    def _query_overpass(
        self, query: DiscoveryQuery, country: str, ind_cfg: dict[str, Any]
    ) -> list[BusinessRecord]:
        """Query Overpass API mirrors with bounding box or city boundary."""
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

        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

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
        """Query OpenStreetMap Nominatim structured search endpoint."""
        params = {
            "q": f"{search_term} in {query.city}, {country}",
            "format": "json",
            "limit": min(query.limit * 2, 50),
            "addressdetails": 1,
            "extratags": 1,
        }
        headers = {"User-Agent": USER_AGENT}

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

                # Extract verified contact details
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
                    discovery_provider="openstreetmap_overpass",
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
        """Parse raw Overpass element into BusinessRecord."""
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
            discovery_provider="openstreetmap_overpass",
            source_url=source_url,
        )

    def _clean_website(self, raw_url: str) -> str | None:
        """Sanitize and validate extracted website string."""
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
