from decimal import Decimal

import pytest
from django.contrib.sessions.backends.db import SessionStore

from cart.cart import Cart, CartLine


def test_add_merges_same_variant(session, make_variant):
    v = make_variant(stock=10, price=Decimal("120.00"))
    cart = Cart(session); cart.add(v, 2); cart.add(v, 3)
    assert cart.count() == 5 and cart.total() == Decimal("600.00")


def test_add_caps_at_stock(session, make_variant):
    assert Cart(session).add(make_variant(stock=3), 5) == 3


def test_add_caps_merged_quantity_at_stock(session, make_variant):
    v = make_variant(stock=4)
    cart = Cart(session)
    assert cart.add(v, 3) == 3
    assert cart.add(v, 3) == 4
    assert cart.count() == 4


def test_add_returns_new_quantity(session, variant):
    cart = Cart(session)
    assert cart.add(variant) == 1
    assert cart.add(variant, 2) == 3


def test_add_unavailable_variant_stores_nothing(session, make_variant):
    cart = Cart(session)
    assert cart.add(make_variant(stock=0)) == 0
    assert cart.add(make_variant(is_active=False)) == 0
    assert cart.is_empty()


def test_add_variant_of_inactive_product_stores_nothing(session, make_variant, make_product):
    v = make_variant(product=make_product(is_active=False))
    cart = Cart(session)
    assert cart.add(v) == 0
    assert cart.is_empty()
    assert Cart.SESSION_KEY not in session


@pytest.mark.parametrize("qty", [0, -1])
def test_add_rejects_non_positive_quantity(session, variant, qty):
    with pytest.raises(ValueError):
        Cart(session).add(variant, qty)


def test_set_zero_removes_and_set_caps(session, make_variant):
    v = make_variant(stock=4); cart = Cart(session); cart.add(v, 1)
    assert cart.set(v.pk, 9) == 4
    assert cart.set(v.pk, 0) == 0 and cart.is_empty()


def test_set_replaces_quantity(session, variant):
    cart = Cart(session); cart.add(variant, 4)
    assert cart.set(variant.pk, 2) == 2
    assert cart.count() == 2


def test_set_negative_removes(session, variant):
    cart = Cart(session); cart.add(variant, 2)
    assert cart.set(variant.pk, -3) == 0
    assert cart.is_empty()


def test_set_unknown_variant_removes_and_returns_zero(session, variant):
    cart = Cart(session); cart.add(variant, 2)
    gone_pk = variant.pk
    variant.delete()
    assert cart.set(gone_pk, 3) == 0
    assert cart.is_empty()
    assert Cart(session).set(999999, 1) == 0


def test_set_out_of_stock_variant_removes(session, make_variant):
    v = make_variant(stock=3); cart = Cart(session); cart.add(v, 2)
    v.stock = 0; v.save()
    assert cart.set(v.pk, 2) == 0
    assert cart.is_empty()


def test_set_on_variant_not_in_cart_stores_it_capped_at_stock(session, make_variant):
    v = make_variant(stock=3)
    cart = Cart(session)
    assert cart.set(v.pk, 7) == 3
    assert cart.count() == 3
    assert session[Cart.SESSION_KEY] == {str(v.pk): 3}


def test_set_inactive_variant_not_in_cart_stores_nothing(session, make_variant):
    v = make_variant(is_active=False, stock=5)
    cart = Cart(session)
    assert cart.set(v.pk, 3) == 0
    assert cart.is_empty()
    assert session.get(Cart.SESSION_KEY, {}) == {}


def test_set_variant_of_inactive_product_not_in_cart_stores_nothing(session, make_variant, make_product):
    v = make_variant(product=make_product(is_active=False), stock=5)
    cart = Cart(session)
    assert cart.set(v.pk, 3) == 0
    assert cart.is_empty()
    assert session.get(Cart.SESSION_KEY, {}) == {}


def test_set_removes_line_when_variant_becomes_inactive(session, make_variant):
    v = make_variant(stock=5); cart = Cart(session); cart.add(v, 2)
    v.is_active = False; v.save()
    assert cart.set(v.pk, 2) == 0
    assert cart.is_empty()
    assert session[Cart.SESSION_KEY] == {}


def test_set_removes_line_when_product_becomes_inactive(session, make_variant):
    v = make_variant(stock=5); cart = Cart(session); cart.add(v, 2)
    v.product.is_active = False; v.product.save()
    assert cart.set(v.pk, 2) == 0
    assert cart.is_empty()
    assert session[Cart.SESSION_KEY] == {}


def test_remove_drops_only_that_variant(session, make_variant):
    a, b = make_variant(), make_variant()
    cart = Cart(session); cart.add(a); cart.add(b, 2)
    cart.remove(a.pk)
    assert [line.variant for line in cart.lines()] == [b]
    cart.remove(a.pk)  # removing a missing id is a no-op
    assert cart.count() == 2


def test_clear_empties_cart(session, make_variant):
    cart = Cart(session); cart.add(make_variant()); cart.add(make_variant())
    cart.clear()
    assert cart.is_empty() and cart.count() == 0 and cart.lines() == []


def test_empty_cart_totals(session):
    cart = Cart(session)
    assert cart.total() == Decimal("0.00")
    assert cart.count() == 0
    assert cart.lines() == []
    assert cart.is_empty()


def test_lines_follow_insertion_order(session, make_variant):
    a, b, c = make_variant(), make_variant(), make_variant()
    cart = Cart(session); cart.add(c); cart.add(a); cart.add(b)
    cart.add(c)  # re-adding must not move it
    assert [line.variant for line in cart.lines()] == [c, a, b]


def test_lines_expose_quantity_and_line_total(session, make_variant):
    v = make_variant(price=Decimal("250.50"), stock=10)
    cart = Cart(session); cart.add(v, 3)
    (line,) = cart.lines()
    assert isinstance(line, CartLine)
    assert line.variant == v
    assert line.quantity == 3
    assert line.line_total == Decimal("751.50")


def test_cartline_is_frozen(session, variant):
    cart = Cart(session); cart.add(variant)
    (line,) = cart.lines()
    with pytest.raises(AttributeError):
        line.quantity = 99


def test_total_sums_all_lines(session, make_variant):
    a = make_variant(price=Decimal("100.00"))
    b = make_variant(price=Decimal("33.33"))
    cart = Cart(session); cart.add(a, 2); cart.add(b, 3)
    assert cart.total() == Decimal("299.99")


def test_lines_use_one_query_with_product(session, make_variant, django_assert_num_queries):
    cart = Cart(session)
    for _ in range(3):
        cart.add(make_variant())
    with django_assert_num_queries(1):
        lines = cart.lines()
        assert [line.variant.product.name for line in lines]  # no extra query for product


def test_lines_of_empty_cart_run_no_query(session, django_assert_num_queries):
    with django_assert_num_queries(0):
        assert Cart(session).lines() == []


def test_deleted_variant_disappears_without_error(session, make_variant):
    keep, gone = make_variant(), make_variant()
    cart = Cart(session); cart.add(keep); cart.add(gone); gone.delete()
    assert cart.count() == 1
    assert [line.variant for line in cart.lines()] == [keep]


def test_deleted_variant_is_pruned_from_session(session, make_variant):
    keep, gone = make_variant(), make_variant()
    cart = Cart(session); cart.add(keep); cart.add(gone, 2); gone.delete()
    session.modified = False
    cart.lines()
    assert session[Cart.SESSION_KEY] == {str(keep.pk): 1}
    assert session.modified


def test_deleted_variant_is_ignored_by_total_count_and_is_empty(session, make_variant):
    a = make_variant(price=Decimal("50.00")); b = make_variant(price=Decimal("70.00"))
    cart = Cart(session); cart.add(a, 2); cart.add(b, 3)
    b.delete()
    assert cart.count() == 2
    assert cart.total() == Decimal("100.00")
    a.delete()
    assert cart.is_empty()


def test_state_survives_new_instance(session, variant):
    Cart(session).add(variant, 2)
    assert Cart(session).count() == 2


def test_session_stores_string_keys_and_int_quantities(session, variant):
    Cart(session).add(variant, 2)
    assert session[Cart.SESSION_KEY] == {str(variant.pk): 2}


def test_state_survives_session_save_and_reload(session, variant):
    Cart(session).add(variant, 2)
    session.save()
    reloaded = SessionStore(session_key=session.session_key)
    assert Cart(reloaded).count() == 2


def test_carts_in_different_sessions_are_independent(variant):
    a, b = SessionStore(), SessionStore()
    Cart(a).add(variant, 2)
    assert Cart(b).is_empty()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda cart, v: cart.add(v, 1),
        lambda cart, v: cart.set(v.pk, 2),
        lambda cart, v: cart.remove(v.pk),
        lambda cart, v: cart.clear(),
    ],
    ids=["add", "set", "remove", "clear"],
)
def test_every_mutation_marks_session_modified(session, variant, mutate):
    cart = Cart(session); cart.add(variant, 1)
    session.modified = False
    mutate(cart, variant)
    assert session.modified is True


def test_reading_does_not_mark_session_modified(session, variant):
    cart = Cart(session); cart.add(variant, 1)
    session.modified = False
    cart.lines(); cart.count(); cart.total(); cart.is_empty()
    assert session.modified is False


def test_failed_add_does_not_mark_session_modified(session, make_variant):
    session.modified = False
    assert Cart(session).add(make_variant(stock=0)) == 0
    assert session.modified is False
