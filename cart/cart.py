"""Session-backed shopping cart.

The session holds ``{"<variant_id>": quantity}`` under ``Cart.SESSION_KEY``. Keys are strings because the
session is JSON-serialised; dict insertion order is the order lines were first added.
"""

from dataclasses import dataclass
from decimal import Decimal

from catalog.models import Variant


@dataclass(frozen=True)
class CartLine:
    variant: Variant
    quantity: int
    line_total: Decimal  # variant.price * quantity


class Cart:
    SESSION_KEY = "cart"

    def __init__(self, session) -> None:
        self.session = session

    def _items(self) -> dict[str, int]:
        """The live session dict (never creates the key; use ``_writable_items`` to mutate)."""
        return self.session.get(self.SESSION_KEY, {})

    def _writable_items(self) -> dict[str, int]:
        return self.session.setdefault(self.SESSION_KEY, {})

    def add(self, variant: Variant, quantity: int = 1) -> int:
        """Add ``quantity`` of ``variant``, capped at its stock. Returns the new quantity in the cart.

        An unavailable variant is not stored and yields 0. ``quantity`` below 1 raises ``ValueError``.
        """
        if quantity < 1:
            raise ValueError("quantity must be at least 1")
        if not variant.in_stock:
            return 0
        items = self._writable_items()
        key = str(variant.pk)
        new_quantity = min(items.get(key, 0) + quantity, variant.stock)
        items[key] = new_quantity
        self.session.modified = True
        return new_quantity

    def set(self, variant_id: int, quantity: int) -> int:
        """Set the exact quantity, capped at stock. Zero/negative or a missing variant removes the line (returns 0)."""
        if quantity <= 0:
            self.remove(variant_id)
            return 0
        variant = Variant.objects.filter(pk=variant_id).first()
        new_quantity = min(quantity, variant.stock) if variant else 0
        if new_quantity <= 0:
            self.remove(variant_id)
            return 0
        self._writable_items()[str(variant_id)] = new_quantity
        self.session.modified = True
        return new_quantity

    def remove(self, variant_id: int) -> None:
        self._items().pop(str(variant_id), None)
        self.session.modified = True

    def clear(self) -> None:
        self.session.pop(self.SESSION_KEY, None)
        self.session.modified = True

    def lines(self) -> list[CartLine]:
        """Cart lines in the order they were added, from a single query.

        Ids of variants that no longer exist are dropped from the session.
        """
        items = self._items()
        if not items:
            return []
        variants = Variant.objects.select_related("product").in_bulk([int(key) for key in items])
        lines = []
        for key in list(items):
            variant = variants.get(int(key))
            if variant is None:
                del items[key]
                self.session.modified = True
                continue
            quantity = items[key]
            lines.append(CartLine(variant=variant, quantity=quantity, line_total=variant.price * quantity))
        return lines

    def total(self) -> Decimal:
        return sum((line.line_total for line in self.lines()), Decimal("0.00"))

    def count(self) -> int:
        return sum(line.quantity for line in self.lines())

    def is_empty(self) -> bool:
        return not self.lines()
