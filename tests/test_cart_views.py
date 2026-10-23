import re
from decimal import Decimal

import pytest
from django.contrib.staticfiles import finders
from django.db import connection
from django.test.utils import CaptureQueriesContext

from cart.cart import Cart
from cart.context_processors import cart_count

HTMX = {"HTTP_HX_REQUEST": "true"}


def add_to_cart(client, variant, quantity=1):
    return client.post("/cart/add/", {"variant_id": variant.pk, "quantity": quantity})


# --- add ---------------------------------------------------------------------------------------------------


def test_htmx_add_returns_counter(client, make_variant):
    v = make_variant(stock=5)
    r = client.post("/cart/add/", {"variant_id": v.pk, "quantity": 2}, HTTP_HX_REQUEST="true")
    assert r.status_code == 200 and 'data-count="2"' in r.content.decode()


def test_htmx_add_returns_only_the_counter(client, variant):
    html = client.post("/cart/add/", {"variant_id": variant.pk}, **HTMX).content.decode()
    assert 'id="cart-counter"' in html and "<html" not in html and "hx-swap-oob" not in html


def test_plain_add_redirects_to_cart(client, variant):
    r = client.post("/cart/add/", {"variant_id": variant.pk, "quantity": 1})
    assert r.status_code == 302 and r["Location"] == "/cart/"


def test_add_without_quantity_adds_one(client, variant):
    assert client.post("/cart/add/", {"variant_id": variant.pk}).status_code == 302
    assert Cart(client.session).count() == 1


def test_add_caps_quantity_at_stock(client, make_variant):
    add_to_cart(client, make_variant(stock=3), quantity=50)
    assert Cart(client.session).count() == 3


def test_add_requires_post(client, variant):
    assert client.get("/cart/add/", {"variant_id": variant.pk}).status_code == 405
    assert Cart(client.session).is_empty()


@pytest.mark.parametrize(
    "payload",
    [
        {"variant_id": "abc", "quantity": 1},
        {"variant_id": 999999, "quantity": 1},
        {"quantity": 1},
        {"variant_id": "PK", "quantity": 0},
        {"variant_id": "PK", "quantity": -3},
        {"variant_id": "PK", "quantity": "x"},
        {"variant_id": "PK", "quantity": ""},
        {"variant_id": "PK", "quantity": "2.5"},
        {"variant_id": "PK", "quantity": "9" * 40},
        {"variant_id": "9" * 40, "quantity": 1},
        {"variant_id": "-1", "quantity": 1},
        {"variant_id": "", "quantity": 1},
    ],
)
def test_add_rejects_bad_input(client, variant, payload):
    payload = {k: variant.pk if v == "PK" else v for k, v in payload.items()}
    assert client.post("/cart/add/", payload).status_code == 400
    assert Cart(client.session).is_empty()
    variant.refresh_from_db()
    assert variant.stock == 5


def test_add_out_of_stock_is_409(client, make_variant):
    assert client.post("/cart/add/", {"variant_id": make_variant(stock=0).pk, "quantity": 1}).status_code == 409


def test_add_unavailable_variants_are_409_with_message(client, make_variant, make_product):
    inactive_variant = make_variant(stock=5, is_active=False)
    inactive_product = make_variant(product=make_product(is_active=False), stock=5)
    for v in (make_variant(stock=0), inactive_variant, inactive_product):
        for extra in ({}, HTMX):
            r = client.post("/cart/add/", {"variant_id": v.pk, "quantity": 1}, **extra)
            assert r.status_code == 409 and "Немає в наявності" in r.content.decode()
    assert Cart(client.session).is_empty()


# --- update ------------------------------------------------------------------------------------------------


def test_htmx_update_returns_body_and_oob_counter(client, make_variant):
    v = make_variant(stock=5)
    client.post("/cart/add/", {"variant_id": v.pk, "quantity": 1})
    html = client.post("/cart/update/", {"variant_id": v.pk, "quantity": 3}, HTTP_HX_REQUEST="true").content.decode()
    assert 'id="cart-body"' in html and 'data-count="3"' in html and 'hx-swap-oob="true"' in html


def test_update_sets_exact_quantity_and_caps_at_stock(client, make_variant):
    v = make_variant(stock=5)
    add_to_cart(client, v, 4)
    client.post("/cart/update/", {"variant_id": v.pk, "quantity": 2})
    assert Cart(client.session).count() == 2
    client.post("/cart/update/", {"variant_id": v.pk, "quantity": 99})
    assert Cart(client.session).count() == 5


def test_plain_update_redirects_to_cart(client, variant):
    add_to_cart(client, variant)
    r = client.post("/cart/update/", {"variant_id": variant.pk, "quantity": 2})
    assert r.status_code == 302 and r["Location"] == "/cart/"


def test_update_to_zero_removes_the_line(client, variant):
    add_to_cart(client, variant, 2)
    r = client.post("/cart/update/", {"variant_id": variant.pk, "quantity": 0}, **HTMX)
    html = r.content.decode()
    assert r.status_code == 200 and Cart(client.session).is_empty()
    assert "Кошик порожній" in html and 'data-count="0"' in html


@pytest.mark.parametrize(
    "payload",
    [
        {"variant_id": "PK", "quantity": -1},
        {"variant_id": "PK", "quantity": "x"},
        {"variant_id": "PK", "quantity": ""},
        {"variant_id": "PK"},
        {"variant_id": "abc", "quantity": 1},
        {"quantity": 1},
    ],
)
def test_update_rejects_bad_input_and_keeps_cart(client, variant, payload):
    add_to_cart(client, variant, 2)
    payload = {k: variant.pk if v == "PK" else v for k, v in payload.items()}
    assert client.post("/cart/update/", payload).status_code == 400
    assert Cart(client.session).count() == 2


def test_update_requires_post(client, variant):
    assert client.get("/cart/update/", {"variant_id": variant.pk, "quantity": 1}).status_code == 405


def test_update_cannot_store_an_unavailable_variant(client, make_variant):
    v = make_variant(stock=0)
    r = client.post("/cart/update/", {"variant_id": v.pk, "quantity": 2})
    assert r.status_code == 302 and Cart(client.session).is_empty()


# --- remove ------------------------------------------------------------------------------------------------


def test_htmx_remove_returns_body_and_oob_counter(client, make_variant):
    keep, drop = make_variant(name="Оранжевий", stock=5), make_variant(name="Зелений", stock=5)
    add_to_cart(client, keep, 2)
    add_to_cart(client, drop, 1)
    r = client.post("/cart/remove/", {"variant_id": drop.pk}, **HTMX)
    html = r.content.decode()
    assert r.status_code == 200
    assert 'id="cart-body"' in html and 'data-count="2"' in html and 'hx-swap-oob="true"' in html
    assert keep.name in html and drop.name not in html


def test_plain_remove_redirects_to_cart(client, variant):
    add_to_cart(client, variant)
    r = client.post("/cart/remove/", {"variant_id": variant.pk})
    assert r.status_code == 302 and r["Location"] == "/cart/"
    assert Cart(client.session).is_empty()


@pytest.mark.parametrize("payload", [{}, {"variant_id": ""}, {"variant_id": "abc"}, {"variant_id": "9" * 40}])
def test_remove_rejects_bad_input(client, variant, payload):
    add_to_cart(client, variant)
    assert client.post("/cart/remove/", payload).status_code == 400
    assert Cart(client.session).count() == 1


def test_remove_of_an_already_gone_line_just_shows_the_cart(client, variant, make_variant):
    """A stale page (line removed in another tab, variant deleted) must not dead-end on a 400."""
    other = make_variant(stock=5)
    add_to_cart(client, other)
    r = client.post("/cart/remove/", {"variant_id": variant.pk + 1000}, **HTMX)
    assert r.status_code == 200 and Cart(client.session).count() == 1


def test_remove_requires_post(client, variant):
    assert client.get("/cart/remove/", {"variant_id": variant.pk}).status_code == 405


# --- cart page ---------------------------------------------------------------------------------------------


def test_cart_page_shows_total(client, make_variant):
    v = make_variant(price=Decimal("780.00"), stock=5)
    client.post("/cart/add/", {"variant_id": v.pk, "quantity": 2})
    assert "1 560 грн" in client.get("/cart/").content.decode()


def test_cart_page_survives_deleted_variant(client, make_variant):
    v = make_variant()
    client.post("/cart/add/", {"variant_id": v.pk, "quantity": 1})
    v.delete()
    r = client.get("/cart/")
    assert r.status_code == 200 and "Кошик порожній" in r.content.decode() and 'data-count="0"' in r.content.decode()


def test_cart_page_survives_variant_deactivated_after_adding(client, variant):
    add_to_cart(client, variant)
    variant.is_active = False
    variant.save()
    r = client.get("/cart/")
    assert r.status_code == 200 and variant.name in r.content.decode()


def test_empty_cart_page_links_back_to_the_shop(client):
    html = client.get("/cart/").content.decode()
    assert "Кошик порожній" in html and 'href="/"' in html
    assert "/checkout/" not in html


def test_cart_page_lists_lines_with_controls(client, make_variant):
    a = make_variant(name="Червоний", price=Decimal("1250.50"), stock=9)
    b = make_variant(name="Синій", price=Decimal("90.00"), stock=9)
    add_to_cart(client, a, 2)
    add_to_cart(client, b, 1)
    html = client.get("/cart/").content.decode()
    assert a.product.name in html and "Червоний" in html and "Синій" in html
    assert "1 250,50 грн" in html and "2 501 грн" in html  # unit price, line total
    assert "2 591 грн" in html  # cart total: 2501 + 90
    assert html.count('hx-post="/cart/update/"') == 2 and html.count('hx-post="/cart/remove/"') == 2
    assert re.search(r'name="quantity"[^>]*value="2"|value="2"[^>]*name="quantity"', html)
    assert 'href="/checkout/"' in html and "Оформити замовлення" in html
    assert html.count('id="cart-body"') == 1 and html.count('id="cart-counter"') == 1


def test_cart_page_runs_one_variant_query(client, variant):
    add_to_cart(client, variant, 2)
    with CaptureQueriesContext(connection) as queries:
        assert client.get("/cart/").status_code == 200
    assert sum('FROM "catalog_variant"' in q["sql"] for q in queries.captured_queries) == 1


# --- base layout and counter --------------------------------------------------------------------------------


def test_base_layout_header_footer_and_htmx(client):
    html = client.get("/cart/").content.decode()
    assert '<html lang="uk">' in html and "<title>" in html
    assert re.search(r'<a [^>]*href="/"[^>]*>\s*<img [^>]*logo\.svg', html)  # logo links home
    assert 'href="/cart/"' in html and 'id="cart-counter"' in html
    for text in ("м. Вінниця, вул. Костянтина Василенка 9", "Пн–Сб 9:00–20:00, Нд 9:00–17:00", "+380 98 593 68 15"):
        assert text in html
    assert 'href="https://www.instagram.com/remesh.fishing_team/"' in html
    assert '<script src="https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js"></script>' in html


def test_body_carries_the_csrf_token_for_htmx(client):
    html = client.get("/cart/").content.decode()
    token = re.search(r"<body[^>]*hx-headers='\{\"X-CSRFToken\": \"([A-Za-z0-9]+)\"\}'", html)
    assert token and len(token.group(1)) == 64  # a masked CSRF token


def test_layout_links_existing_static_files(client):
    html = client.get("/cart/").content.decode()
    for path in ("css/site.css", "img/logo.svg"):
        assert f"/static/{path}" in html and finders.find(path)


def test_logo_is_remesh_text_on_a_black_circle(settings):
    svg = (settings.BASE_DIR / "static" / "img" / "logo.svg").read_text(encoding="utf-8")
    assert "<circle" in svg and "REMESH" in svg and "http://www.w3.org/2000/svg" in svg


def test_context_processor_counts_lazily(rf, session, make_variant, django_assert_num_queries):
    v = make_variant(stock=5)
    Cart(session).add(v, 3)
    request = rf.get("/")
    request.session = session
    with django_assert_num_queries(0):
        ctx = cart_count(request)  # building the context costs nothing
    with django_assert_num_queries(1):
        assert str(ctx["cart_count"]) == "3" and ctx["cart_count"] == 3


def test_context_processor_empty_cart_is_zero(rf, session, django_assert_num_queries):
    request = rf.get("/")
    request.session = session
    with django_assert_num_queries(0):
        assert str(cart_count(request)["cart_count"]) == "0"
