from decimal import Decimal

import pytest

from cart.cart import Cart
from catalog.models import Variant
from orders.models import Order
from orders.services import EmptyCartError, OutOfStockError, StockProblem, cancel_order, place_order
from tests.data import CUSTOMER


def test_place_order_snapshots_and_stock(session, make_variant):
    v = make_variant(name="LOX UV", price=Decimal("120.00"), stock=10)
    cart = Cart(session)
    cart.add(v, 3)
    order = place_order(cart, CUSTOMER)
    assert order.number == f"RM-{order.pk:04d}"
    assert (order.total, order.status, order.payment_method) == (Decimal("360.00"), "new", "cod")
    item = order.items.get()
    assert (item.product_name, item.variant_name, item.sku, item.unit_price, item.quantity) == (
        v.product.name,
        "LOX UV",
        v.sku,
        Decimal("120.00"),
        3,
    )
    assert item.line_total == Decimal("360.00")
    v.refresh_from_db()
    assert v.stock == 7
    assert cart.is_empty()


def test_place_order_copies_customer_data_and_sums_lines(session, make_variant):
    a = make_variant(price=Decimal("10.50"), stock=5)
    b = make_variant(price=Decimal("99.99"), stock=5)
    cart = Cart(session)
    cart.add(a, 2)
    cart.add(b, 1)
    order = place_order(cart, {**CUSTOMER, "comment": "Подзвоніть перед відправкою"})
    order.refresh_from_db()
    assert order.total == Decimal("120.99")
    assert (order.customer_name, order.phone) == (CUSTOMER["customer_name"], CUSTOMER["phone"])
    assert (order.np_city_name, order.np_warehouse_name) == ("Вінниця", "Відділення №1")
    assert order.comment == "Подзвоніть перед відправкою"
    assert order.items.count() == 2


def test_snapshot_survives_price_change(session, variant):
    cart = Cart(session)
    cart.add(variant, 1)
    order = place_order(cart, CUSTOMER)
    variant.price = Decimal("999.00")
    variant.save()
    assert order.items.get().unit_price == Decimal("780.00")


def test_out_of_stock_creates_nothing_and_adjusts_cart(session, make_variant):
    a, b = make_variant(stock=5), make_variant(stock=5)
    cart = Cart(session)
    cart.add(a, 2)
    cart.add(b, 4)
    b.stock = 1
    b.save()
    with pytest.raises(OutOfStockError) as exc:
        place_order(cart, CUSTOMER)
    assert exc.value.problems == [StockProblem(b.pk, str(b), 4, 1)]
    assert Order.objects.count() == 0
    a.refresh_from_db()
    assert a.stock == 5
    assert {line.variant.pk: line.quantity for line in cart.lines()} == {a.pk: 2, b.pk: 1}


def test_all_problems_are_listed_in_cart_order(session, make_variant):
    a, b, c = make_variant(stock=5), make_variant(stock=5), make_variant(stock=5)
    cart = Cart(session)
    cart.add(a, 3)
    cart.add(b, 2)
    cart.add(c, 4)
    a.stock = 0
    a.save()
    c.stock = 2
    c.save()
    with pytest.raises(OutOfStockError) as exc:
        place_order(cart, CUSTOMER)
    assert exc.value.problems == [StockProblem(a.pk, str(a), 3, 0), StockProblem(c.pk, str(c), 4, 2)]
    assert {line.variant.pk: line.quantity for line in cart.lines()} == {b.pk: 2, c.pk: 2}
    assert Order.objects.count() == 0


def test_deactivated_variant_is_problem_with_zero(session, make_variant):
    v = make_variant(stock=5)
    cart = Cart(session)
    cart.add(v, 1)
    v.is_active = False
    v.save()
    with pytest.raises(OutOfStockError) as exc:
        place_order(cart, CUSTOMER)
    assert exc.value.problems[0].available == 0 and cart.is_empty()


def test_inactive_product_is_problem_with_zero(session, make_variant):
    v = make_variant(stock=5)
    cart = Cart(session)
    cart.add(v, 2)
    v.product.is_active = False
    v.product.save()
    with pytest.raises(OutOfStockError) as exc:
        place_order(cart, CUSTOMER)
    assert exc.value.problems == [StockProblem(v.pk, str(v), 2, 0)]
    assert cart.is_empty()
    v.refresh_from_db()
    assert v.stock == 5 and Order.objects.count() == 0


def test_variant_deleted_after_lines_were_read_is_problem_with_zero(session, make_variant, monkeypatch):
    v = make_variant(stock=5)
    cart = Cart(session)
    cart.add(v, 1)
    name, pk = str(v), v.pk
    real_lines = cart.lines

    def lines_then_delete():
        lines = real_lines()
        Variant.objects.filter(pk=pk).delete()  # the variant disappears before place_order locks it
        return lines

    monkeypatch.setattr(cart, "lines", lines_then_delete)
    with pytest.raises(OutOfStockError) as exc:
        place_order(cart, CUSTOMER)
    assert exc.value.problems == [StockProblem(pk, name, 1, 0)]
    monkeypatch.undo()
    assert cart.is_empty() and Order.objects.count() == 0


def test_empty_cart_raises(session):
    with pytest.raises(EmptyCartError):
        place_order(Cart(session), CUSTOMER)


def test_cancel_restores_stock_once(session, make_variant):
    v = make_variant(stock=10)
    cart = Cart(session)
    cart.add(v, 3)
    order = place_order(cart, CUSTOMER)
    assert cancel_order(order) is True
    assert cancel_order(order) is False
    v.refresh_from_db()
    assert v.stock == 10
    order.refresh_from_db()
    assert order.status == "cancelled"


def test_cancel_updates_the_passed_instance(session, variant):
    cart = Cart(session)
    cart.add(variant, 1)
    order = place_order(cart, CUSTOMER)
    assert order.status == Order.Status.NEW
    cancel_order(order)
    assert order.status == Order.Status.CANCELLED  # no refresh_from_db needed


def test_cancel_with_deleted_variant(session, make_variant):
    v = make_variant(stock=10)
    cart = Cart(session)
    cart.add(v, 1)
    order = place_order(cart, CUSTOMER)
    v.delete()
    assert cancel_order(order) is True
