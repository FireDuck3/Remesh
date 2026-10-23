"""Placing and cancelling orders. Stock is only ever changed here, inside a transaction."""

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from cart.cart import Cart, CartLine
from catalog.models import Variant

from .models import Order, OrderItem


@dataclass(frozen=True)
class StockProblem:
    variant_id: int
    name: str  # str(variant)
    requested: int
    available: int  # variant.stock, or 0 when the variant/product is inactive or gone


class EmptyCartError(Exception):
    """The cart has nothing to order."""


class OutOfStockError(Exception):
    """At least one cart line can't be fulfilled; nothing was written and the cart was adjusted."""

    def __init__(self, problems: list[StockProblem]) -> None:
        super().__init__("Деяких товарів немає в потрібній кількості")
        self.problems = problems


def _find_problems(lines: list[CartLine], locked: dict[int, Variant]) -> list[StockProblem]:
    """Compare every cart line with the locked rows; problems come out in cart-line order."""
    problems = []
    for line in lines:
        variant = locked.get(line.variant.pk)
        if variant is not None and variant.is_active and variant.product.is_active:
            available = variant.stock
        else:  # deactivated (or deleted since the cart was read): can't be sold at all
            available = 0
        if line.quantity > available:
            name = str(variant if variant is not None else line.variant)
            problems.append(StockProblem(line.variant.pk, name, line.quantity, available))
    return problems


def _create_order(lines: list[CartLine], locked: dict[int, Variant], data: dict[str, str]) -> Order:
    """Write the order, its snapshot items and the stock decrement. Prices come from the locked rows."""
    rows = [(locked[line.variant.pk], line.quantity) for line in lines]
    order = Order.objects.create(
        customer_name=data["customer_name"],
        phone=data["phone"],
        np_city_ref=data["np_city_ref"],
        np_city_name=data["np_city_name"],
        np_warehouse_ref=data["np_warehouse_ref"],
        np_warehouse_name=data["np_warehouse_name"],
        comment=data["comment"],
        total=sum((variant.price * quantity for variant, quantity in rows), Decimal("0.00")),
    )
    OrderItem.objects.bulk_create(
        OrderItem(
            order=order,
            variant=variant,
            product_name=variant.product.name,
            variant_name=variant.name,
            sku=variant.sku,
            unit_price=variant.price,
            quantity=quantity,
        )
        for variant, quantity in rows
    )
    for variant, quantity in rows:
        Variant.objects.filter(pk=variant.pk).update(stock=F("stock") - quantity)
    return order


def place_order(cart: Cart, data: dict[str, str]) -> Order:
    """Turn the cart into an order in one transaction.

    ``data`` needs ``customer_name, phone, np_city_ref, np_city_name, np_warehouse_ref, np_warehouse_name,
    comment`` (the phone already normalised). Raises ``EmptyCartError`` for an empty cart, or
    ``OutOfStockError`` (after rolling back, with the cart lowered to what is available) when any line
    can't be fulfilled.
    """
    lines = cart.lines()
    if not lines:
        raise EmptyCartError

    problems: list[StockProblem] = []
    order = None
    with transaction.atomic():
        # Locked in pk order so concurrent checkouts never wait on each other in a cycle. Only the variant
        # rows are locked; the product is joined just to read its is_active.
        locked = {
            variant.pk: variant
            for variant in Variant.objects.select_for_update(of=("self",))
            .select_related("product")
            .filter(pk__in=[line.variant.pk for line in lines])
            .order_by("pk")
        }
        problems = _find_problems(lines, locked)
        if not problems:
            order = _create_order(lines, locked, data)

    if problems:  # raised outside the atomic block, so nothing above was written
        for problem in problems:
            cart.set(problem.variant_id, problem.available)
        raise OutOfStockError(problems)

    cart.clear()
    return order


def cancel_order(order: Order) -> bool:
    """Cancel the order and return its items to stock, exactly once.

    Returns ``False`` (changing nothing) if it was already cancelled. Items whose variant has since been
    deleted have nothing to restock. The passed-in ``order`` gets its ``status`` refreshed.
    """
    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        if locked.status == Order.Status.CANCELLED:
            order.status = locked.status
            return False
        items = locked.items.filter(variant__isnull=False).order_by("variant_id")
        for item in items:
            Variant.objects.filter(pk=item.variant_id).update(stock=F("stock") + item.quantity)
        locked.status = Order.Status.CANCELLED
        locked.save(update_fields=["status"])
    order.status = locked.status
    return True
