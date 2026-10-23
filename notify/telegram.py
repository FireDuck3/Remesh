"""Telegram notification about a new order, sent through the Bot API.

``notify_new_order`` is fire-and-forget and must never break the checkout: whatever goes wrong it logs a
WARNING on the ``notify`` logger and returns ``False``. The bot token is part of the request URL, so neither
the URL nor the text of an exception (``requests`` puts the URL in it) is ever logged -- only the exception
class name and the HTTP status.
"""

import logging
from typing import TYPE_CHECKING

import requests
from django.conf import settings

from catalog.templatetags.money import format_uah

if TYPE_CHECKING:
    from orders.models import Order

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT = 5
MAX_DESCRIPTION = 200  # how much of Telegram's own error description ends up in the log

logger = logging.getLogger("notify")


def format_order_message(order: "Order") -> str:
    """The plain-text (no parse_mode) message the manager gets for a new order."""
    lines = [f"🎣 Нове замовлення {order.number}", f"Сума: {format_uah(order.total)}", ""]
    for item in order.items.order_by("pk"):
        lines.append(
            f"• {item.product_name} — {item.variant_name} × {item.quantity} = {format_uah(item.line_total)}"
        )
    lines += [
        "",
        f"Клієнт: {order.customer_name}",
        f"Телефон: {order.phone}",
        f"НП: {order.np_city_name}, {order.np_warehouse_name}",
        f"Коментар: {order.comment.strip() or '—'}",
        f"Адмінка: {settings.SITE_URL}/admin/orders/order/{order.pk}/change/",
    ]
    return "\n".join(lines)


def _failure_reason(response: requests.Response) -> str | None:
    """Why Telegram's answer is not a success, or ``None`` for ``200`` with ``"ok": true``."""
    try:
        body = response.json()
    except ValueError:
        body = None
    if response.status_code != 200:
        reason = f"HTTP {response.status_code}"
        description = body.get("description") if isinstance(body, dict) else None
        if isinstance(description, str) and description:
            reason += f": {description[:MAX_DESCRIPTION]}"
        return reason
    if body is None:
        return "response is not valid JSON"
    if not isinstance(body, dict) or body.get("ok") is not True:
        return "API did not report ok"
    return None


def _send(order: "Order") -> bool:
    token, chat_id = settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return False
    payload = {"chat_id": chat_id, "text": format_order_message(order), "disable_web_page_preview": True}
    try:
        response = requests.post(API_URL.format(token=token), json=payload, timeout=TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("Telegram notification for order %s failed: %s", order.pk, type(exc).__name__)
        return False
    reason = _failure_reason(response)
    if reason is not None:
        logger.warning("Telegram notification for order %s failed: %s", order.pk, reason)
        return False
    return True


def notify_new_order(order: "Order") -> bool:
    """Send the new-order message. ``True`` only if Telegram accepted it; never raises."""
    try:
        return _send(order)
    except Exception as exc:  # noqa: BLE001 - a notification must never take the checkout down with it
        # Class name only, no traceback: the message of an exception raised while sending may hold the URL.
        order_pk = getattr(order, "pk", None)
        logger.warning("Telegram notification for order %s failed unexpectedly: %s", order_pk, type(exc).__name__)
        return False
