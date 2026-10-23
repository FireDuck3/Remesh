import io
import re
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from catalog import seed_data
from catalog.management.commands import seed_remesh
from catalog.models import Category, Product, ProductImage, Variant

SMALL = dict(
    CATEGORIES=[{"slug": "c1", "name": "Кат", "position": 1}],
    PRODUCTS=[
        {
            "slug": "p1",
            "category": "c1",
            "name": "Товар",
            "description": "",
            "images": ["missing.jpg"],
            "variants": [
                {"sku": "S1", "name": "A", "price": Decimal("100.00"), "stock": 10},
                {"sku": "S2", "name": "B", "price": None, "stock": 10},
            ],
        }
    ],
)


def run(monkeypatch):
    for k, v in SMALL.items():
        monkeypatch.setattr(seed_data, k, v)
    out = io.StringIO()
    call_command("seed_remesh", stdout=out)
    return out.getvalue()


def test_seed_creates_and_reports(monkeypatch):
    out = run(monkeypatch)
    assert Variant.objects.get(sku="S1").price == Decimal("100.00")
    assert not Variant.objects.filter(sku="S2").exists()
    assert "Ціну не задано: S2 — пропущено" in out and "Фото не знайдено: missing.jpg — пропущено" in out
    assert out.strip().splitlines()[-1] == "Створено: категорій 1, товарів 1, варіантів 1"


def test_rerun_keeps_manager_edits_and_no_duplicates(monkeypatch):
    run(monkeypatch)
    Variant.objects.filter(sku="S1").update(price=Decimal("150.00"), stock=2)
    out = run(monkeypatch)
    v = Variant.objects.get(sku="S1")
    assert (v.price, v.stock) == (Decimal("150.00"), 2) and Product.objects.count() == 1
    assert out.strip().splitlines()[-1] == "Створено: категорій 0, товарів 0, варіантів 0"


def test_rerun_does_not_touch_existing_category_and_product(monkeypatch):
    run(monkeypatch)
    Category.objects.filter(slug="c1").update(name="Перейменовано", position=9)
    Product.objects.filter(slug="p1").update(name="Нова назва", description="Опис менеджера", is_active=False)
    run(monkeypatch)
    cat = Category.objects.get(slug="c1")
    product = Product.objects.get(slug="p1")
    assert (cat.name, cat.position) == ("Перейменовано", 9)
    assert (product.name, product.description, product.is_active) == ("Нова назва", "Опис менеджера", False)


def test_rerun_adds_variant_once_price_is_filled(monkeypatch):
    run(monkeypatch)
    priced = {**SMALL["PRODUCTS"][0], "variants": [
        {"sku": "S1", "name": "A", "price": Decimal("100.00"), "stock": 10},
        {"sku": "S2", "name": "B", "price": Decimal("200.00"), "stock": 7},
    ]}
    monkeypatch.setattr(seed_data, "PRODUCTS", [priced])
    out = io.StringIO()
    call_command("seed_remesh", stdout=out)
    assert Variant.objects.get(sku="S2").price == Decimal("200.00")
    assert Variant.objects.filter(product__slug="p1").count() == 2
    assert out.getvalue().strip().splitlines()[-1] == "Створено: категорій 0, товарів 0, варіантів 1"


def test_product_with_all_variants_skipped_is_still_created(monkeypatch):
    monkeypatch.setattr(seed_data, "CATEGORIES", SMALL["CATEGORIES"])
    monkeypatch.setattr(seed_data, "PRODUCTS", [{**SMALL["PRODUCTS"][0], "images": [], "variants": [
        {"sku": "N1", "name": "A", "price": None, "stock": 10},
    ]}])
    out = io.StringIO()
    call_command("seed_remesh", stdout=out)
    assert Product.objects.filter(slug="p1").exists() and Variant.objects.count() == 0
    assert not Product.objects.visible().exists()
    assert out.getvalue().strip().splitlines()[-1] == "Створено: категорій 1, товарів 1, варіантів 0"


def test_images_copied_only_when_product_is_created(monkeypatch, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / "media"
    images_dir = tmp_path / "seed_images"
    images_dir.mkdir()
    (images_dir / "a.jpg").write_bytes(b"fake-a")
    (images_dir / "b.jpg").write_bytes(b"fake-b")
    monkeypatch.setattr(seed_remesh, "SEED_IMAGES_DIR", images_dir)
    monkeypatch.setattr(seed_data, "CATEGORIES", SMALL["CATEGORIES"])
    monkeypatch.setattr(seed_data, "PRODUCTS", [{**SMALL["PRODUCTS"][0], "images": ["a.jpg", "b.jpg", "gone.jpg"]}])

    out = io.StringIO()
    call_command("seed_remesh", stdout=out)
    images = list(ProductImage.objects.filter(product__slug="p1").order_by("position"))
    assert [i.position for i in images] == [0, 1]
    assert all((settings.MEDIA_ROOT / i.image.name).read_bytes() in (b"fake-a", b"fake-b") for i in images)
    assert "Фото не знайдено: gone.jpg — пропущено" in out.getvalue()

    call_command("seed_remesh", stdout=io.StringIO())
    assert ProductImage.objects.filter(product__slug="p1").count() == 2


def test_run_is_atomic_on_unknown_category(monkeypatch):
    monkeypatch.setattr(seed_data, "CATEGORIES", SMALL["CATEGORIES"])
    bad = {**SMALL["PRODUCTS"][0], "slug": "p2", "category": "nope"}
    monkeypatch.setattr(seed_data, "PRODUCTS", [SMALL["PRODUCTS"][0], bad])
    with pytest.raises(CommandError):
        call_command("seed_remesh", stdout=io.StringIO())
    assert not Category.objects.exists() and not Product.objects.exists()


def test_real_seed_data_is_consistent():
    cats = {c["slug"] for c in seed_data.CATEGORIES}
    skus = [v["sku"] for p in seed_data.PRODUCTS for v in p["variants"]]
    assert len(skus) == len(set(skus))
    for p in seed_data.PRODUCTS:
        assert p["category"] in cats and re.fullmatch(r"[a-z0-9-]+", p["slug"])
        for v in p["variants"]:
            assert re.fullmatch(r"[A-Z0-9-]+", v["sku"])


def test_real_seed_runs_and_only_priced_variants_are_created():
    out = io.StringIO()
    call_command("seed_remesh", stdout=out)
    priced = [v for p in seed_data.PRODUCTS for v in p["variants"] if v["price"] is not None]
    unpriced = [v for p in seed_data.PRODUCTS for v in p["variants"] if v["price"] is None]
    assert Product.objects.count() == len(seed_data.PRODUCTS)
    assert Variant.objects.count() == len(priced)
    for v in unpriced:
        assert f"Ціну не задано: {v['sku']} — пропущено" in out.getvalue()


def test_if_empty_seeds_normally_on_empty_catalog(monkeypatch):
    for k, v in SMALL.items():
        monkeypatch.setattr(seed_data, k, v)
    out = io.StringIO()
    call_command("seed_remesh", "--if-empty", stdout=out)
    assert Product.objects.count() == 1 and Variant.objects.filter(sku="S1").exists()
    assert out.getvalue().strip().splitlines()[-1] == "Створено: категорій 1, товарів 1, варіантів 1"
    assert "Каталог не порожній — пропущено" not in out.getvalue()


def test_if_empty_does_nothing_when_a_product_exists(monkeypatch, make_product):
    make_product(slug="manager-product")
    counts = (Category.objects.count(), Product.objects.count(), Variant.objects.count())
    for k, v in SMALL.items():
        monkeypatch.setattr(seed_data, k, v)
    out = io.StringIO()
    call_command("seed_remesh", "--if-empty", stdout=out)
    assert out.getvalue().strip() == "Каталог не порожній — пропущено"
    assert (Category.objects.count(), Product.objects.count(), Variant.objects.count()) == counts
    assert not Product.objects.filter(slug="p1").exists()


def test_without_if_empty_existing_catalog_is_still_seeded(monkeypatch, make_product):
    make_product(slug="manager-product")
    out = run(monkeypatch)
    assert Product.objects.filter(slug="p1").exists()
    assert "Каталог не порожній" not in out
