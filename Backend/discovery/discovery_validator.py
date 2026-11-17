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
    "france": "France",
    "fr": "France",
    "spain": "Spain",
    "es": "Spain",
    "italy": "Italy",
    "it": "Italy",
    "netherlands": "Netherlands",
    "nl": "Netherlands",
    "singapore": "Singapore",
    "sg": "Singapore",
    "new zealand": "New Zealand",
    "nz": "New Zealand",
    "ireland": "Ireland",
    "ie": "Ireland",
    "south africa": "South Africa",
    "za": "South Africa",
    "japan": "Japan",
    "jp": "Japan",
}

# Standard industry mappings to OpenStreetMap tags and fallback search terms
INDUSTRY_TAGS: dict[str, dict[str, Any]] = {
    "restaurants": {
        "osm_keys": [("amenity", "restaurant"), ("amenity", "cafe"), ("amenity", "fast_food")],
        "search_term": "restaurant",
        "search_terms": ["restaurant", "cafe", "eatery"],
        "category_name": "Restaurants & Hospitality",
    },
    "cafes": {
        "osm_keys": [("amenity", "cafe"), ("shop", "coffee"), ("shop", "bakery")],
        "search_term": "cafe",
        "search_terms": ["cafe", "coffee", "bakery"],
        "category_name": "Cafes & Bakeries",
    },
    "salons": {
        "osm_keys": [("shop", "hairdresser"), ("shop", "beauty"), ("leisure", "spa")],
        "search_term": "salon",
        "search_terms": ["salon", "hairdresser", "beauty salon", "spa"],
        "category_name": "Hair & Beauty Salons",
    },
    "dentists": {
        "osm_keys": [("amenity", "dentist"), ("amenity", "clinic"), ("healthcare", "dentist")],
        "search_term": "dentist",
        "search_terms": ["dentist", "dental clinic", "orthodontist"],
        "category_name": "Dental Clinics & Healthcare",
    },
    "healthcare": {
        "osm_keys": [("amenity", "clinic"), ("amenity", "doctors"), ("amenity", "hospital")],
        "search_term": "clinic",
        "search_terms": ["clinic", "doctors", "hospital"],
        "category_name": "Medical & Healthcare",
    },
    "fitness": {
        "osm_keys": [("leisure", "fitness_centre"), ("leisure", "sports_centre"), ("amenity", "gym")],
        "search_term": "gym",
        "search_terms": ["gym", "fitness", "fitness centre", "sports centre"],
        "category_name": "Fitness & Gyms",
    },
    "logistics": {
        "osm_keys": [("industrial", "logistics"), ("industrial", "warehouse"), ("office", "logistics"), ("amenity", "freight")],
        "search_term": "logistics",
        "search_terms": ["logistics", "freight", "warehouse"],
        "category_name": "Logistics & Warehousing",
    },
    "bakeries": {
        "osm_keys": [("shop", "bakery"), ("shop", "pastry")],
        "search_term": "bakery",
        "search_terms": ["bakery", "pastry shop"],
        "category_name": "Bakeries & Confectionery",
    },
    "law firms": {
        "osm_keys": [("office", "lawyer"), ("office", "legal")],
        "search_term": "lawyer",
        "search_terms": ["lawyer", "law firm", "attorney"],
        "category_name": "Legal & Law Firms",
    },
    "real estate": {
        "osm_keys": [("office", "estate_agent"), ("shop", "estate_agent")],
        "search_term": "real estate",
        "search_terms": ["real estate", "estate agent", "realtor"],
        "category_name": "Real Estate Agencies",
    },
    "hotels": {
        "osm_keys": [("tourism", "hotel"), ("tourism", "motel"), ("tourism", "guest_house")],
        "search_term": "hotel",
        "search_terms": ["hotel", "motel", "hospitality"],
        "category_name": "Hotels & Hospitality",
    },
    "automotive": {
        "osm_keys": [("shop", "car_repair"), ("shop", "car"), ("amenity", "car_wash")],
        "search_term": "car repair",
        "search_terms": ["car repair", "auto repair", "mechanic"],
        "category_name": "Automotive Services",
    },
    "accounting": {
        "osm_keys": [("office", "accountant"), ("office", "financial")],
        "search_term": "accountant",
        "search_terms": ["accountant", "accounting", "cpa", "tax"],
        "category_name": "Accounting & Finance",
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
        "search_terms": [clean_term],
        "category_name": industry.strip().title(),
    }
