from delivery import novaposhta
from delivery.novaposhta import City, NovaPoshtaError, Warehouse

HINT = "введіть вручну"


def boom(*args, **kwargs):
    raise NovaPoshtaError("down")


# --- cities -------------------------------------------------------------------------------------------------


def test_cities_view_renders_options(client, monkeypatch):
    monkeypatch.setattr(novaposhta, "search_cities", lambda q, limit=10: [City("r1", "м. Вінниця")])
    html = client.get("/delivery/cities/?q=Він").content.decode()
    assert 'data-ref="r1"' in html and 'data-name="м. Вінниця"' in html


def test_cities_view_passes_query_through(client, monkeypatch):
    seen = []
    monkeypatch.setattr(novaposhta, "search_cities", lambda q, limit=10: seen.append(q) or [])
    client.get("/delivery/cities/?q=Він")
    client.get("/delivery/cities/")
    assert seen == ["Він", ""]


def test_cities_view_error_shows_manual_hint(client, monkeypatch):
    monkeypatch.setattr(novaposhta, "search_cities", boom)
    r = client.get("/delivery/cities/?q=Він")
    assert r.status_code == 200 and HINT in r.content.decode()


def test_cities_view_without_results_has_no_options(client, monkeypatch):
    monkeypatch.setattr(novaposhta, "search_cities", lambda q, limit=10: [])
    r = client.get("/delivery/cities/?q=В")
    assert r.status_code == 200 and "np-option" not in r.content.decode()


def test_cities_view_escapes_names(client, monkeypatch):
    evil = 'м. "><script>alert(1)</script>'
    monkeypatch.setattr(novaposhta, "search_cities", lambda q, limit=10: [City('r"1', evil)])
    html = client.get("/delivery/cities/?q=Він").content.decode()
    assert "<script>" not in html and 'data-ref="r&quot;1"' in html


def test_cities_view_is_get_only(client):
    assert client.post("/delivery/cities/?q=Він").status_code == 405


def test_cities_view_without_api_key_shows_hint(client):
    # The autouse fixture blanks the key: the real client raises NovaPoshtaError, the view must still answer 200.
    r = client.get("/delivery/cities/?q=Вінниця")
    assert r.status_code == 200 and HINT in r.content.decode()


# --- warehouses ---------------------------------------------------------------------------------------------


def test_warehouses_view_renders_options(client, monkeypatch):
    seen = []

    def fake(city_ref, query="", limit=50):
        seen.append((city_ref, query))
        return [Warehouse("w1", "Відділення №1"), Warehouse("w2", "Відділення №2")]

    monkeypatch.setattr(novaposhta, "list_warehouses", fake)
    html = client.get("/delivery/warehouses/?city_ref=c1&q=1").content.decode()
    assert seen == [("c1", "1")]
    assert 'data-ref="w1"' in html and 'data-name="Відділення №2"' in html
    assert html.count('class="np-option"') == 2


def test_warehouses_view_error_shows_manual_hint(client, monkeypatch):
    monkeypatch.setattr(novaposhta, "list_warehouses", boom)
    r = client.get("/delivery/warehouses/?city_ref=c1")
    assert r.status_code == 200 and HINT in r.content.decode()


def test_warehouses_view_without_city_has_no_options(client):
    r = client.get("/delivery/warehouses/")
    assert r.status_code == 200 and "np-option" not in r.content.decode()


def test_warehouses_view_escapes_names(client, monkeypatch):
    evil = "<img src=x onerror=alert(1)>"
    monkeypatch.setattr(novaposhta, "list_warehouses", lambda city_ref, query="", limit=50: [Warehouse("w1", evil)])
    html = client.get("/delivery/warehouses/?city_ref=c1").content.decode()
    assert "<img" not in html


def test_warehouses_view_is_get_only(client):
    assert client.post("/delivery/warehouses/?city_ref=c1").status_code == 405
