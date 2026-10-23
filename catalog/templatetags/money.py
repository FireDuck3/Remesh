from decimal import ROUND_HALF_UP, Decimal

from django import template

register = template.Library()

NBSP = " "


@register.filter(name="uah")
def format_uah(value):
    """Decimal -> '780 грн' / '1 250,50 грн' (non-breaking spaces, comma decimal separator)."""
    amount = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = f"{amount:,.2f}"  # '1,250.50'
    if text.endswith(".00"):
        text = text[:-3]
    text = text.replace(",", NBSP).replace(".", ",")
    return f"{text}{NBSP}грн"
