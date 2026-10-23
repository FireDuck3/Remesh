"""Thin Nova Poshta API 2.0 client: city and warehouse lookup for the checkout autocomplete.

Every failure (no key, network error, non-200, malformed JSON, ``"success": false``) becomes ``NovaPoshtaError``;
callers decide how to degrade. Successful lookups are cached for a day, failures never are.
"""

import hashlib
import logging
from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.cache import cache

API_URL = "https://api.novaposhta.ua/v2.0/json/"
TIMEOUT = 5
CACHE_TIMEOUT = 24 * 60 * 60
MIN_CITY_QUERY = 2

logger = logging.getLogger("delivery")


@dataclass(frozen=True)
class City:
    ref: str
    name: str


@dataclass(frozen=True)
class Warehouse:
    ref: str
    name: str


class NovaPoshtaError(Exception):
    """The Nova Poshta API is unavailable, not configured, or answered with an error."""


def is_enabled():
    return bool(settings.NOVA_POSHTA_API_KEY)


def _failure(method, reason):
    """Log the failure (never the API key) and return the exception for the caller to raise."""
    logger.warning("Nova Poshta %s failed: %s", method, reason)
    return NovaPoshtaError(reason)


def _call(method, properties):
    """POST one Address-model request and return the ``data`` payload of a successful answer."""
    if not is_enabled():
        raise _failure(method, "NOVA_POSHTA_API_KEY is not set")
    payload = {
        "apiKey": settings.NOVA_POSHTA_API_KEY,
        "modelName": "Address",
        "calledMethod": method,
        "methodProperties": properties,
    }
    try:
        response = requests.post(API_URL, json=payload, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise _failure(method, f"{type(exc).__name__}: {exc}") from exc
    if response.status_code != 200:
        raise _failure(method, f"HTTP {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise _failure(method, "response is not valid JSON") from exc
    if not isinstance(body, dict) or not body.get("success"):
        errors = body.get("errors") if isinstance(body, dict) else None
        raise _failure(method, f"API reported failure: {errors}")
    return body.get("data")


def _cache_key(prefix, value):
    return prefix + hashlib.sha1(value.encode("utf-8")).hexdigest()


def _items(value):
    """``value`` if it is a list, else an empty one (a successful answer may still lack the expected shape)."""
    return value if isinstance(value, list) else []


def _parse_cities(data):
    first = _items(data)[:1]
    addresses = _items(first[0].get("Addresses")) if first and isinstance(first[0], dict) else []
    return [
        City(ref=a["DeliveryCity"], name=a["Present"])
        for a in addresses
        if isinstance(a, dict) and a.get("DeliveryCity") and a.get("Present")
    ]


def _parse_warehouses(data):
    return [
        Warehouse(ref=w["Ref"], name=w["Description"])
        for w in _items(data)
        if isinstance(w, dict) and w.get("Ref") and w.get("Description")
    ]


def search_cities(query, limit=10):
    """Settlements matching ``query`` (at least two characters), best match first."""
    query = query.strip()
    if len(query) < MIN_CITY_QUERY:
        return []
    key = _cache_key("np:c:", query.lower())
    cities = cache.get(key)
    if cities is None:
        properties = {"CityName": query, "Limit": str(limit), "Page": "1"}
        cities = _parse_cities(_call("searchSettlements", properties))
        cache.set(key, cities, timeout=CACHE_TIMEOUT)
    return cities


def list_warehouses(city_ref, query="", limit=50):
    """Warehouses of the city ``city_ref``, optionally narrowed down by a free-text ``query``."""
    city_ref = city_ref.strip()
    query = query.strip()
    if not city_ref:
        return []
    key = _cache_key("np:w:", f"{city_ref}|{query.lower()}")
    warehouses = cache.get(key)
    if warehouses is None:
        properties = {"CityRef": city_ref, "FindByString": query, "Limit": str(limit), "Page": "1"}
        warehouses = _parse_warehouses(_call("getWarehouses", properties))
        cache.set(key, warehouses, timeout=CACHE_TIMEOUT)
    return warehouses
