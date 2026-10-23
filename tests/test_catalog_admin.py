"""Admin saves must not overwrite stock that changed (a sale) after the manager's page was loaded.

The tests drive the real pages: GET the form, change the database behind the manager's back, POST back
what a browser would send (including the hidden ``initial-…`` inputs).
"""

from html.parser import HTMLParser

import pytest
from django.db.models import F

from cart.cart import Cart
from catalog.models import Variant
from orders.services import place_order
from tests.data import CUSTOMER


class _FormCollector(HTMLParser):
    """Collects what a browser would submit for the <form id=…>: inputs, selects, textareas."""

    def __init__(self, form_id):
        super().__init__()
        self.form_id = form_id
        self.data = {}
        self._in_form = False
        self._select = None
        self._textarea = None
        self._text = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form" and a.get("id") == self.form_id:
            self._in_form = True
        if not self._in_form:
            return
        name = a.get("name")
        if tag == "input" and name:
            kind = a.get("type", "text")
            if kind in ("file", "submit", "button", "image"):
                return
            if kind in ("checkbox", "radio"):
                if "checked" in a:
                    self.data[name] = a.get("value") or "on"
            else:
                self.data[name] = a.get("value") or ""
        elif tag == "select" and name:
            self._select = name
            self.data.setdefault(name, "")
            self._first_option = True
        elif tag == "option" and self._select:
            if "selected" in a or self._first_option and not self.data[self._select]:
                self.data[self._select] = a.get("value", "")
            self._first_option = False
        elif tag == "textarea" and name:
            self._textarea, self._text = name, ""

    def handle_data(self, data):
        if self._textarea:
            self._text += data

    def handle_endtag(self, tag):
        if tag == "form":
            self._in_form = False
        elif tag == "select":
            self._select = None
        elif tag == "textarea" and self._textarea:
            self.data[self._textarea] = self._text.removeprefix("\n")
            self._textarea = None


def page_form(client, url, form_id):
    response = client.get(url)
    assert response.status_code == 200
    collector = _FormCollector(form_id)
    collector.feed(response.content.decode())
    assert collector.data, f"form #{form_id} not found at {url}"
    return collector.data


def product_url(product):
    return f"/admin/catalog/product/{product.pk}/change/"


def post_product_form(client, product, data):
    response = client.post(product_url(product), {**data, "_save": "Зберегти"})
    assert response.status_code == 302, response.context["errors"] if response.context else response.content
    return response


def stock_of(variant):
    return Variant.objects.values_list("stock", flat=True).get(pk=variant.pk)


def sell(variant, quantity):
    """What place_order does to the row, while the manager's page is open."""
    Variant.objects.filter(pk=variant.pk).update(stock=F("stock") - quantity)


@pytest.fixture
def product_with_stock_10(make_variant):
    return make_variant(stock=10).product


# --- the product page (VariantInline) -------------------------------------------------------------------


def test_inline_save_of_another_field_keeps_stock_sold_meanwhile(admin_client, product_with_stock_10):
    product = product_with_stock_10
    variant = product.variants.get()
    data = page_form(admin_client, product_url(product), "product_form")
    assert data["variants-0-stock"] == "10"  # the manager's page shows 10 ...
    sell(variant, 3)  # ... then a buyer takes 3
    data["description"] = "Новий опис"
    post_product_form(admin_client, product, data)
    product.refresh_from_db()
    assert product.description == "Новий опис"
    assert stock_of(variant) == 7


def test_inline_save_of_another_variant_field_keeps_stock(admin_client, product_with_stock_10):
    product = product_with_stock_10
    variant = product.variants.get()
    data = page_form(admin_client, product_url(product), "product_form")
    sell(variant, 3)
    data["variants-0-name"] = "Нова назва"
    post_product_form(admin_client, product, data)
    variant.refresh_from_db()
    assert (variant.name, variant.stock) == ("Нова назва", 7)


def test_inline_stock_change_is_applied_as_a_difference(admin_client, product_with_stock_10):
    product = product_with_stock_10
    variant = product.variants.get()
    data = page_form(admin_client, product_url(product), "product_form")
    sell(variant, 3)  # DB: 7
    data["variants-0-stock"] = "15"  # manager: 10 -> 15 (+5)
    post_product_form(admin_client, product, data)
    assert stock_of(variant) == 12


def test_inline_stock_decrease_below_zero_clamps_at_zero(admin_client, product_with_stock_10):
    product = product_with_stock_10
    variant = product.variants.get()
    data = page_form(admin_client, product_url(product), "product_form")
    sell(variant, 8)  # DB: 2
    data["variants-0-stock"] = "5"  # manager: 10 -> 5 (-5): 2 - 5 would be negative
    post_product_form(admin_client, product, data)
    assert stock_of(variant) == 0


def test_inline_without_a_sale_in_between_sets_the_typed_value(admin_client, product_with_stock_10):
    product = product_with_stock_10
    variant = product.variants.get()
    data = page_form(admin_client, product_url(product), "product_form")
    data["variants-0-stock"] = "4"
    post_product_form(admin_client, product, data)
    assert stock_of(variant) == 4


def test_inline_new_variant_gets_the_typed_stock(admin_client, product_with_stock_10):
    product = product_with_stock_10
    data = page_form(admin_client, product_url(product), "product_form")
    data.update({"variants-1-name": "Новий", "variants-1-sku": "NEW-1", "variants-1-price": "99.00",
                 "variants-1-stock": "6"})
    post_product_form(admin_client, product, data)
    assert Variant.objects.get(sku="NEW-1").stock == 6


def test_inline_save_without_hidden_initial_still_sets_typed_value(admin_client, product_with_stock_10):
    """A POST that lacks the hidden initial (not from our page) keeps the plain 'set' behaviour."""
    product = product_with_stock_10
    variant = product.variants.get()
    data = page_form(admin_client, product_url(product), "product_form")
    del data["initial-variants-0-stock"]
    data["variants-0-stock"] = "3"
    post_product_form(admin_client, product, data)
    assert stock_of(variant) == 3


# --- the variants list (list_editable) -------------------------------------------------------------------


def post_changelist(client, data):
    return client.post("/admin/catalog/variant/", {**data, "_save": "Зберегти"})


def test_changelist_save_of_price_keeps_stock_sold_meanwhile(admin_client, make_variant):
    variant = make_variant(stock=10)
    data = page_form(admin_client, "/admin/catalog/variant/", "changelist-form")
    assert data["form-0-stock"] == "10"
    sell(variant, 3)
    data["form-0-price"] = "250.00"
    assert post_changelist(admin_client, data).status_code == 302
    variant.refresh_from_db()
    assert (str(variant.price), variant.stock) == ("250.00", 7)


def test_changelist_stock_change_is_applied_as_a_difference(admin_client, make_variant):
    variant = make_variant(stock=10)
    data = page_form(admin_client, "/admin/catalog/variant/", "changelist-form")
    sell(variant, 3)
    data["form-0-stock"] = "15"
    assert post_changelist(admin_client, data).status_code == 302
    assert stock_of(variant) == 12


def test_changelist_stock_decrease_below_zero_clamps_at_zero(admin_client, make_variant):
    variant = make_variant(stock=10)
    data = page_form(admin_client, "/admin/catalog/variant/", "changelist-form")
    sell(variant, 8)  # DB: 2
    data["form-0-stock"] = "5"  # manager: 10 -> 5 (-5): 2 - 5 would be negative
    assert post_changelist(admin_client, data).status_code == 302
    assert stock_of(variant) == 0


def test_changelist_untouched_row_is_not_written(admin_client, make_variant):
    variant = make_variant(stock=10)
    data = page_form(admin_client, "/admin/catalog/variant/", "changelist-form")
    sell(variant, 3)
    assert post_changelist(admin_client, data).status_code == 302  # nothing changed in the form
    assert stock_of(variant) == 7


# --- the single-variant page ----------------------------------------------------------------------------


def test_variant_change_page_keeps_stock_sold_meanwhile(admin_client, make_variant):
    variant = make_variant(stock=10)
    url = f"/admin/catalog/variant/{variant.pk}/change/"
    data = page_form(admin_client, url, "variant_form")
    sell(variant, 3)
    data["name"] = "Перейменовано"
    response = admin_client.post(url, {**data, "_save": "Зберегти"})
    assert response.status_code == 302
    variant.refresh_from_db()
    assert (variant.name, variant.stock) == ("Перейменовано", 7)


# --- place_order still decrements atomically ------------------------------------------------------------


def test_place_order_decrement_still_works_after_admin_edit(admin_client, product_with_stock_10, session):
    product = product_with_stock_10
    variant = product.variants.get()
    data = page_form(admin_client, product_url(product), "product_form")
    data["description"] = "Опис"
    post_product_form(admin_client, product, data)
    cart = Cart(session)
    cart.add(variant, 4)
    place_order(cart, CUSTOMER)
    assert stock_of(variant) == 6
