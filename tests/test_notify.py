import json
import logging
from decimal import Decimal

import pytest
import requests
import responses

from cart.cart import Cart
from notify import telegram
from notify.telegram import format_order_message, notify_new_order
from orders.services import OutOfStockError, place_order
from tests.data import CUSTOMER

SEND_URL = "https://api.telegram.org/botT/sendMessage"


def make_order(session, make_variant, **kw):
    v = make_variant(name="Стандарт", price=Decimal("780.00"), stock=5)
    cart = Cart(session)
    cart.add(v, 1)
    return place_order(cart, {**CUSTOMER, **kw}), v


# --- format_order_message -----------------------------------------------------------------------------------


def test_format_message(session, make_variant, settings):
    settings.SITE_URL = "https://shop.example"
    order, v = make_order(session, make_variant)
    assert format_order_message(order) == (
        f"🎣 Нове замовлення {order.number}\nСума: 780 грн\n\n"
        f"• {v.product.name} — Стандарт × 1 = 780 грн\n\n"
        "Клієнт: Іван Петренко\nТелефон: +380985936815\nНП: Вінниця, Відділення №1\nКоментар: —\n"
        f"Адмінка: https://shop.example/admin/orders/order/{order.pk}/change/"
    )


def test_format_message_lists_every_item_in_order_and_shows_comment(session, make_variant, settings):
    settings.SITE_URL = "https://shop.example"
    first = make_variant(name="Червоний", price=Decimal("120.00"), stock=5)
    second = make_variant(name="Синій", price=Decimal("1250.50"), stock=5)
    cart = Cart(session)
    cart.add(first, 3)
    cart.add(second, 1)
    order = place_order(cart, {**CUSTOMER, "comment": "Подзвоніть перед відправкою"})
    assert format_order_message(order) == (
        f"🎣 Нове замовлення {order.number}\nСума: 1 610,50 грн\n\n"
        f"• {first.product.name} — Червоний × 3 = 360 грн\n"
        f"• {second.product.name} — Синій × 1 = 1 250,50 грн\n\n"
        "Клієнт: Іван Петренко\nТелефон: +380985936815\nНП: Вінниця, Відділення №1\n"
        "Коментар: Подзвоніть перед відправкою\n"
        f"Адмінка: https://shop.example/admin/orders/order/{order.pk}/change/"
    )


# --- notify_new_order ---------------------------------------------------------------------------------------


@responses.activate
def test_not_configured_returns_false_without_http(session, make_variant):
    order, _ = make_order(session, make_variant)
    assert notify_new_order(order) is False and len(responses.calls) == 0


@responses.activate
@pytest.mark.parametrize("token, chat_id", [("T", ""), ("", "42")])
def test_half_configured_returns_false_without_http(session, make_variant, settings, token, chat_id):
    settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID = token, chat_id
    order, _ = make_order(session, make_variant)
    assert notify_new_order(order) is False and len(responses.calls) == 0


@responses.activate
def test_success(session, make_variant, settings):
    settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID = "T", "42"
    responses.post(SEND_URL, json={"ok": True})
    order, _ = make_order(session, make_variant)
    assert notify_new_order(order) is True
    assert json.loads(responses.calls[0].request.body) == {
        "chat_id": "42",
        "text": format_order_message(order),
        "disable_web_page_preview": True,
    }


@responses.activate
@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": 500, "json": {"ok": False}},
        {"status": 400, "json": {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}},
        {"status": 200, "json": {"ok": False}},
        {"status": 200, "body": "<html>not json</html>"},
        {"status": 200, "json": ["ok"]},
        {"body": requests.ConnectionError("x")},
        {"body": requests.Timeout("x")},
    ],
)
def test_failure_returns_false(session, make_variant, settings, kwargs):
    settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID = "T", "42"
    responses.post(SEND_URL, **kwargs)
    order, _ = make_order(session, make_variant)
    assert notify_new_order(order) is False


@responses.activate
def test_failure_is_logged_as_warning(session, make_variant, settings, caplog):
    settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID = "T", "42"
    responses.post(SEND_URL, status=400, json={"ok": False, "description": "Bad Request: chat not found"})
    order, _ = make_order(session, make_variant)
    with caplog.at_level(logging.WARNING, logger="notify"):
        assert notify_new_order(order) is False
    assert [(r.name, r.levelno) for r in caplog.records] == [("notify", logging.WARNING)]
    assert "400" in caplog.text and "chat not found" in caplog.text


@responses.activate
@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": 500, "json": {"ok": False}},
        {"status": 200, "body": "<html>not json</html>"},
        # requests puts the full URL (and so the bot token) in the text of its exceptions
        {"body": requests.ConnectionError("Max retries exceeded with url: /botSECRET-TOKEN/sendMessage")},
        # ...and a non-requests exception can carry it too: still swallowed, still not logged
        {"body": ValueError("https://api.telegram.org/botSECRET-TOKEN/sendMessage")},
    ],
)
def test_token_never_reaches_the_logs(session, make_variant, settings, caplog, kwargs):
    settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID = "SECRET-TOKEN", "42"
    responses.post("https://api.telegram.org/botSECRET-TOKEN/sendMessage", **kwargs)
    order, _ = make_order(session, make_variant)
    with caplog.at_level(logging.DEBUG):
        assert notify_new_order(order) is False
    assert caplog.records  # the failure was logged...
    for record in caplog.records:  # ...without the token anywhere: message, args, traceback
        assert "SECRET-TOKEN" not in record.getMessage()
        assert "SECRET-TOKEN" not in repr(record.args)
        assert record.exc_info is None
    assert "SECRET-TOKEN" not in caplog.text


@responses.activate
def test_formatting_failure_does_not_raise(session, make_variant, settings, monkeypatch, caplog):
    settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID = "T", "42"
    responses.post(SEND_URL, json={"ok": True})
    order, _ = make_order(session, make_variant)

    def broken(_order):
        raise RuntimeError("boom")

    monkeypatch.setattr(telegram, "format_order_message", broken)
    with caplog.at_level(logging.WARNING, logger="notify"):
        assert notify_new_order(order) is False
    assert len(responses.calls) == 0
    assert [r.levelno for r in caplog.records] == [logging.WARNING]


# --- place_order wiring -------------------------------------------------------------------------------------


def test_place_order_notifies_on_commit(session, make_variant, monkeypatch, django_capture_on_commit_callbacks):
    sent = []
    monkeypatch.setattr(telegram, "notify_new_order", lambda o: sent.append(o.pk) or True)
    with django_capture_on_commit_callbacks(execute=True):
        order, _ = make_order(session, make_variant)
    assert sent == [order.pk]


def test_place_order_defers_notification_until_commit(
    session, make_variant, monkeypatch, django_capture_on_commit_callbacks
):
    sent = []
    monkeypatch.setattr(telegram, "notify_new_order", lambda o: sent.append(o.pk) or True)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        make_order(session, make_variant)
    assert sent == [] and len(callbacks) == 1


def test_failed_order_sends_no_notification(session, make_variant, monkeypatch, django_capture_on_commit_callbacks):
    sent = []
    monkeypatch.setattr(telegram, "notify_new_order", lambda o: sent.append(o.pk) or True)
    v = make_variant(stock=1)
    cart = Cart(session)
    cart.add(v, 1)
    v.stock = 0
    v.save()
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        with pytest.raises(OutOfStockError):
            place_order(cart, CUSTOMER)
    assert sent == [] and callbacks == []
