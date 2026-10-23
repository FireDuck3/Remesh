from decimal import Decimal

import pytest
from django.template import Context, Template

from catalog.templatetags.money import format_uah


@pytest.mark.parametrize("value,expected", [
    (Decimal("780.00"), "780 грн"),
    (Decimal("1250.50"), "1 250,50 грн"),
    (Decimal("0.5"), "0,50 грн"),
    (Decimal("12000"), "12 000 грн"),
])
def test_format_uah(value, expected):
    assert format_uah(value) == expected


def test_uah_template_filter():
    html = Template("{% load money %}{{ price|uah }}").render(Context({"price": Decimal("1250.50")}))
    assert html == "1 250,50 грн"
