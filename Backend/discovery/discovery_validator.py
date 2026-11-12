"""
discovery_validator.py
----------------------
Validates discovery input parameters and maps business industries into standard OSM tags.
"""

from __future__ import annotations

import re
from typing import Any

# Standard country aliases and ISO-3166 codes
COUNTRY_MAP: dict[str, str] = {
    "usa": "United States",
    "united states": "United States",
    "us": "United States",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "gb": "United Kingdom",
    "australia": "Australia",
    "au": "Australia",
    "uae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
    "ae": "United Arab Emirates",
    "canada": "Canada",
    "ca": "Canada",
    "germany": "Germany",
    "de": "Germany",
    "india": "India",
    "in": "India",
}

# Standard industry mappings to OpenStreetMap tags and fallback search terms
INDUSTRY_TAGS: dict[str, dict[str, Any]] = {
    "restaurants": {
        "osm_keys": [("amenity", "restaurant"), ("amenity", "cafe"), ("amenity", "fast_food")],
        "search_term": "restaurant",
        "category_name": "Restaurants & Hospitality",
    },
    "cafes": {
        "osm_keys": [("amenity", "cafe")],
        "search_term": "cafe",
        "category_name": "Cafes & Bakeries",
    },
    "salons": {
        "osm_keys": [("shop", "hairdresser"), ("shop", "beauty"), ("leisure", "spa")],
        "search_term": "hairdresser",
        "category_name": "Hair & Beauty Salons",
    },
    "dentists": {
        "osm_keys": [("amenity", "dentist"), ("amenity", "clinic"), ("amenity", "doctors")],
        "search_term": "dentist",
        "category_name": "Dental Clinics & Healthcare",
    },
    "healthcare": {
        "osm_keys": [("amenity", "clinic"), ("amenity", "doctors"), ("amenity", "hospital")],
        "search_term": "clinic",
        "category_name": "Medical & Healthcare",
    },
    "fitness": {
        "osm_keys": [("leisure", "fitness_centre"), ("leisure", "sports_centre")],
        "search_term": "fitness centre",
        "category_name": "Fitness & Gyms",
    },
    "logistics": {
        "osm_keys": [("industrial", "logistics"), ("industrial", "warehouse"), ("office", "logistics")],
        "search_term": "logistics",
        "category_name": "Logistics & Warehousing",
    },
    "bakeries": {
        "osm_keys": [("shop", "bakery")],
        "search_term": "bakery",
        "category_name": "Bakeries & Confectionery",
    },
    "law firms": {
        "osm_keys": [("office", "lawyer")],
        "search_term": "lawyer",
        "category_name": "Legal & Law Firms",
    },
    "real estate": {
        "osm_keys": [("office", "estate_agent")],
        "search_term": "estate agent",
        "category_name": "Real Estate Agencies",
    },
}


def normalize_country(country: str) -> str:
    """Resolve user-entered country into standard formal name."""
    clean = country.strip().lower()
    return COUNTRY_MAP.get(clean, country.strip().title())


def get_industry_config(industry: str) -> dict[str, Any]:
    """Retrieve OSM tags and query terms for an industry."""
    clean = industry.strip().lower()
    # Match exact or partial
    for key, cfg in INDUSTRY_TAGS.items():
        if key in clean or clean in key:
            return cfg

    # Default fallback using the user string directly
    clean_term = re.sub(r"[^\w\s]", "", industry).strip()
    return {
        "osm_keys": [("amenity", clean_term.lower()), ("shop", clean_term.lower()), ("office", clean_term.lower())],
        "search_term": clean_term,
        "category_name": industry.strip().title(),
    }
