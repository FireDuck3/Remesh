import json
import logging
from pathlib import Path

import pytest
import requests
import responses

from delivery.novaposhta import (
    API_URL,
    City,
    NovaPoshtaError,
    Warehouse,
    is_enabled,
    list_warehouses,
    search_cities,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def sent_body(call):
    return json.loads(call.request.body)


# --- search_cities ------------------------------------------------------------------------------------------


@responses.activate
def test_search_cities_parses_and_sends_method(settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    responses.post(API_URL, json=load_fixture("np_search_settlements.json"))
    cities = search_cities("Вінн")
    assert cities[0] == City("city-ref-1", "м. Вінниця, Вінницька обл.")
    assert [c.ref for c in cities] == ["city-ref-1", "city-ref-2"]
    body = sent_body(responses.calls[0])
    assert body["calledMethod"] == "searchSettlements" and body["methodProperties"]["CityName"] == "Вінн"


@responses.activate
def test_request_envelope_and_timeout(settings):
    settings.NOVA_POSHTA_API_KEY = "secret-key"
    responses.post(API_URL, json=load_fixture("np_search_settlements.json"))
    search_cities("Вінн", limit=3)
    call = responses.calls[0]
    assert sent_body(call) == {
        "apiKey": "secret-key",
        "modelName": "Address",
        "calledMethod": "searchSettlements",
        "methodProperties": {"CityName": "Вінн", "Limit": "3", "Page": "1"},
    }
    assert call.request.req_kwargs["timeout"] == 5


@responses.activate
def test_results_cached(settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    responses.post(API_URL, json=load_fixture("np_search_settlements.json"))
    search_cities("Біла Церква")
    search_cities("біла церква")
    assert len(responses.calls) == 1


@responses.activate
def test_short_query_no_request(settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    assert search_cities(" В ") == [] and len(responses.calls) == 0


@responses.activate
@pytest.mark.parametrize(
    "kwargs",
    [
        {"json": {"success": False, "data": [], "errors": ["API key expired"]}},
        {"status": 500, "body": "oops"},
        {"body": requests.ConnectionError("down")},
        {"body": "<html>not json</html>"},
    ],
)
def test_api_failure_raises(settings, kwargs):
    settings.NOVA_POSHTA_API_KEY = "k"
    responses.post(API_URL, **kwargs)
    with pytest.raises(NovaPoshtaError):
        search_cities("Вінниця")


def test_disabled_without_key():
    assert not is_enabled()
    with pytest.raises(NovaPoshtaError):
        search_cities("Вінниця")


def test_enabled_with_key(settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    assert is_enabled()


@responses.activate
def test_failure_is_not_cached(settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    responses.post(API_URL, status=500, body="oops")
    with pytest.raises(NovaPoshtaError):
        search_cities("Вінниця")
    responses.replace(responses.POST, API_URL, json=load_fixture("np_search_settlements.json"))
    assert search_cities("Вінниця")[0].ref == "city-ref-1"
    assert len(responses.calls) == 2


@responses.activate
def test_failure_is_logged_without_the_api_key(settings, caplog):
    settings.NOVA_POSHTA_API_KEY = "secret-key"
    responses.post(API_URL, json={"success": False, "data": [], "errors": ["API key expired"]})
    with caplog.at_level(logging.WARNING, logger="delivery"), pytest.raises(NovaPoshtaError):
        search_cities("Вінниця")
    records = [r for r in caplog.records if r.name == "delivery" and r.levelno == logging.WARNING]
    assert records
    assert all("secret-key" not in r.getMessage() for r in records)


@responses.activate
@pytest.mark.parametrize(
    "payload",
    [
        {"success": True, "data": [], "errors": []},
        {"success": True, "data": [{"TotalCount": "0"}], "errors": []},
        {"success": True, "errors": []},
        {"success": True, "data": [{"Addresses": [{"Present": "м. Київ"}]}], "errors": []},
        {"success": True, "data": [None], "errors": []},
    ],
)
def test_odd_successful_payload_gives_no_cities(settings, payload):
    settings.NOVA_POSHTA_API_KEY = "k"
    responses.post(API_URL, json=payload)
    assert search_cities("Київ") == []


# --- list_warehouses ----------------------------------------------------------------------------------------


@responses.activate
def test_list_warehouses(settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    responses.post(API_URL, json=load_fixture("np_get_warehouses.json"))
    warehouses = list_warehouses("city-ref-1")
    assert warehouses[0] == Warehouse("wh-ref-1", "Відділення №1: вул. Пирогова, 4")
    assert warehouses[0].ref == "wh-ref-1"
    assert sent_body(responses.calls[0])["methodProperties"]["CityRef"] == "city-ref-1"


@responses.activate
def test_list_warehouses_request_envelope(settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    responses.post(API_URL, json=load_fixture("np_get_warehouses.json"))
    list_warehouses("city-ref-1", " Пирогова ", limit=5)
    assert sent_body(responses.calls[0]) == {
        "apiKey": "k",
        "modelName": "Address",
        "calledMethod": "getWarehouses",
        "methodProperties": {"CityRef": "city-ref-1", "FindByString": "Пирогова", "Limit": "5", "Page": "1"},
    }


@responses.activate
def test_list_warehouses_empty_city_no_request(settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    assert list_warehouses("") == [] and list_warehouses("  ") == [] and len(responses.calls) == 0


@responses.activate
def test_list_warehouses_cached_per_city_and_query(settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    responses.post(API_URL, json=load_fixture("np_get_warehouses.json"))
    list_warehouses("city-ref-1", "Пирогова")
    list_warehouses("city-ref-1", "пирогова")
    assert len(responses.calls) == 1
    list_warehouses("city-ref-1", "Келецька")
    list_warehouses("city-ref-2", "Пирогова")
    assert len(responses.calls) == 3


@responses.activate
def test_list_warehouses_failure_raises(settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    responses.post(API_URL, json={"success": False, "data": [], "errors": ["nope"]})
    with pytest.raises(NovaPoshtaError):
        list_warehouses("city-ref-1")


def test_list_warehouses_disabled_without_key():
    with pytest.raises(NovaPoshtaError):
        list_warehouses("city-ref-1")


@responses.activate
def test_odd_successful_payload_gives_no_warehouses(settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    responses.post(API_URL, json={"success": True, "data": [{"Ref": "only-ref"}, None], "errors": []})
    assert list_warehouses("city-ref-1") == []
