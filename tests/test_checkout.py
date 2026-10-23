from decimal import Decimal

import pytest
from django.contrib.staticfiles import finders
from django.test import Client

from catalog.templatetags.money import format_uah
from orders.models import Order
from tests.data import FORM


def add(client, v, qty=1):
    client.post("/cart/add/", {"variant_id": v.pk, "quantity": qty})


# --- the empty cart -------------------------------------------------------------------------------------


def test_empty_cart_redirects(client):
    r = client.get("/checkout/")
    assert r.status_code == 302 and r["Location"] == "/cart/"


def test_empty_cart_post_redirects_without_order(client):
    r = client.post("/checkout/", FORM)
    assert r.status_code == 302 and r["Location"] == "/cart/" and Order.objects.count() == 0


def test_empty_cart_message_is_shown_once_on_the_cart_page(client):
    html = client.get("/checkout/", follow=True).content.decode()
    assert 'class="messages"' in html and "Кошик порожній" in html
    assert 'class="messages"' not in client.get("/cart/").content.decode()  # shown, then consumed


# --- placing the order ----------------------------------------------------------------------------------


def test_valid_post_creates_order(client, variant):
    add(client, variant)
    r = client.post("/checkout/", FORM)
    order = Order.objects.get()
    assert r["Location"] == f"/order/{order.number}/thanks/" and order.phone == "+380985936815"
    assert order.number in client.get(r["Location"]).content.decode()


def test_success_empties_the_cart_and_takes_stock(client, variant):
    add(client, variant, 2)
    client.post("/checkout/", FORM)
    variant.refresh_from_db()
    assert variant.stock == 3 and client.get("/checkout/")["Location"] == "/cart/"


def test_invalid_phone_keeps_values(client, variant):
    add(client, variant)
    html = client.post("/checkout/", {**FORM, "phone": "123"}).content.decode()
    assert "+380XXXXXXXXX" in html and 'value="Іван Петренко"' in html and Order.objects.count() == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("customer_name", ""),
        ("customer_name", "І" * 101),
        ("phone", ""),
        ("np_city_name", ""),
        ("np_city_name", "М" * 121),
        ("np_warehouse_name", ""),
        ("np_warehouse_name", "В" * 201),
        ("comment", "к" * 501),
        ("np_city_ref", "r" * 101),
    ],
    ids=[
        "name-empty",
        "name-too-long",
        "phone-empty",
        "city-empty",
        "city-too-long",
        "warehouse-empty",
        "warehouse-too-long",
        "comment-too-long",
        "city-ref-too-long",
    ],
)
def test_invalid_field_is_rejected(client, variant, field, value):
    add(client, variant)
    r = client.post("/checkout/", {**FORM, field: value})
    assert r.status_code == 200 and Order.objects.count() == 0


def test_comment_is_optional_and_refs_are_stored(client, variant):
    add(client, variant)
    data = {k: v for k, v in FORM.items() if k != "comment"}
    client.post("/checkout/", {**data, "np_city_ref": "c-ref", "np_warehouse_ref": "w-ref"})
    order = Order.objects.get()
    assert (order.comment, order.np_city_ref, order.np_warehouse_ref) == ("", "c-ref", "w-ref")


def test_invalid_form_keeps_the_hidden_refs(client, variant):
    add(client, variant)
    html = client.post("/checkout/", {**FORM, "phone": "1", "np_city_ref": "c-ref"}).content.decode()
    assert 'value="c-ref"' in html


# --- stock problems -------------------------------------------------------------------------------------


def test_out_of_stock_message(client, make_variant):
    v = make_variant(stock=5)
    add(client, v, 3)
    v.stock = 1
    v.save()
    r = client.post("/checkout/", FORM)
    assert r.status_code == 200 and "залишилось 1 шт." in r.content.decode() and Order.objects.count() == 0


def test_sold_out_line_says_not_available_and_the_cart_is_adjusted(client, make_variant):
    gone, left = make_variant(name="Зник", stock=5), make_variant(name="Лишився", stock=5)
    add(client, gone)
    add(client, left, 2)
    gone.stock = 0
    gone.save()
    r = client.post("/checkout/", FORM)
    html = r.content.decode()
    assert r.status_code == 200 and "Зник: немає в наявності" in html and "залишилось" not in html
    assert 'value="Іван Петренко"' in html  # the form is still there, filled in
    assert Order.objects.count() == 0 and "Лишився" in html  # the summary shows the adjusted cart


def test_everything_sold_out_shows_no_form(client, variant):
    add(client, variant)
    variant.stock = 0
    variant.save()
    html = client.post("/checkout/", FORM).content.decode()
    assert "немає в наявності" in html and "<form" not in html and "Кошик порожній" in html


# --- double submit --------------------------------------------------------------------------------------


def test_double_submit_single_order(client, variant):
    add(client, variant)
    client.post("/checkout/", FORM)
    r = client.post("/checkout/", FORM)
    assert Order.objects.count() == 1 and r["Location"] == "/cart/"


def test_form_disables_the_submit_button_while_sending(client, variant):
    add(client, variant)
    html = client.get("/checkout/").content.decode()
    assert "onsubmit=" in html and "disabled = true" in html and 'type="submit"' in html


# --- the thank-you page ---------------------------------------------------------------------------------


def test_thanks_hidden_from_other_sessions(client, variant):
    add(client, variant)
    url = client.post("/checkout/", FORM)["Location"]
    assert Client().get(url).status_code == 404


def test_thanks_404_for_a_number_that_is_not_the_last_order(client, variant):
    assert client.get("/order/RM-0001/thanks/").status_code == 404  # no order in this session
    add(client, variant)
    client.post("/checkout/", FORM)
    assert client.get("/order/RM-9999/thanks/").status_code == 404


def test_thanks_shows_the_order(client, make_variant):
    v = make_variant(name="LOX UV", price=Decimal("120.00"), stock=10)
    add(client, v, 3)
    html = client.get(client.post("/checkout/", FORM)["Location"]).content.decode()
    assert v.product.name in html and "LOX UV" in html and "3" in html
    assert format_uah(Decimal("360.00")) in html
    assert "Вінниця" in html and "Відділення №1" in html and "Накладений платіж" in html
    assert "Ми зателефонуємо для підтвердження замовлення" in html


# --- the page itself ------------------------------------------------------------------------------------


def test_checkout_page_summarises_the_cart(client, make_variant):
    v = make_variant(name="LOX UV", price=Decimal("120.00"), stock=10)
    add(client, v, 2)
    html = client.get("/checkout/").content.decode()
    assert "LOX UV" in html and format_uah(Decimal("240.00")) in html and "Накладений платіж" in html


def test_plain_inputs_without_np_key(client, variant):
    add(client, variant)
    html = client.get("/checkout/").content.decode()
    assert 'name="np_city_name"' in html and 'hx-get="/delivery/cities/"' not in html
    assert "checkout.js" not in html and "np-city-results" not in html


def test_autocomplete_with_np_key(client, variant, settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    add(client, variant)
    html = client.get("/checkout/").content.decode()
    assert 'hx-get="/delivery/cities/"' in html and 'hx-trigger="input changed delay:300ms"' in html
    assert 'hx-target="#np-city-results"' in html and 'id="np-city-results"' in html
    assert 'hx-get="/delivery/warehouses/"' in html and 'id="np-warehouse-results"' in html
    assert 'name="np_city_ref"' in html and 'hx-include="#id_np_city_ref"' in html  # warehouses of the picked city
    assert "js/checkout.js" in html


def test_checkout_script_is_a_static_file():
    assert finders.find("js/checkout.js")
