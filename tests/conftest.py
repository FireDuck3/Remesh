import itertools
from decimal import Decimal

import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.core.cache import cache

from catalog.models import Category, Product, Variant

_counter = itertools.count(1)


@pytest.fixture(autouse=True)
def _isolated(db, settings):
    """DB access for every test, a clean cache, and no real network credentials."""
    cache.clear()
    settings.NOVA_POSHTA_API_KEY = ""
    settings.TELEGRAM_BOT_TOKEN = ""
    settings.TELEGRAM_CHAT_ID = ""


@pytest.fixture
def make_product():
    def factory(**kw):
        n = next(_counter)
        if "category" not in kw:
            kw["category"] = Category.objects.create(name=f"Категорія {n}", slug=f"category-{n}")
        kw.setdefault("name", f"Воблер {n}")
        kw.setdefault("slug", f"product-{n}")
        return Product.objects.create(**kw)

    return factory


@pytest.fixture
def make_variant(make_product):
    def factory(product=None, **kw):
        n = next(_counter)
        if product is None:
            product = make_product()
        kw.setdefault("name", f"Варіант {n}")
        kw.setdefault("sku", f"SKU-{n}")
        kw.setdefault("price", Decimal("100.00"))
        kw.setdefault("stock", 10)
        return Variant.objects.create(product=product, **kw)

    return factory


@pytest.fixture
def variant(make_variant):
    return make_variant(price=Decimal("780.00"), stock=5)


@pytest.fixture
def session():
    return SessionStore()
