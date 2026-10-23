from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError

from catalog.models import Category, Product, ProductImage, Variant


def test_min_price_ignores_inactive_variants(make_variant):
    v = make_variant(price=Decimal("120.00"))
    make_variant(product=v.product, price=Decimal("90.00"), is_active=False)
    make_variant(product=v.product, price=Decimal("150.00"))
    assert v.product.min_price() == Decimal("120.00")


def test_min_price_is_none_without_active_variants(make_product, make_variant):
    product = make_product()
    assert product.min_price() is None
    make_variant(product=product, is_active=False)
    assert product.min_price() is None


def test_visible_excludes_inactive_and_variantless(make_product, make_variant):
    shown = make_product(name="A"); make_variant(product=shown)
    hidden = make_product(name="B", is_active=False); make_variant(product=hidden)
    no_active = make_product(name="C"); make_variant(product=no_active, is_active=False)
    assert list(Product.objects.visible()) == [shown]


def test_visible_lists_product_once_despite_many_variants(make_product, make_variant):
    product = make_product()
    make_variant(product=product)
    make_variant(product=product)
    assert list(Product.objects.visible()) == [product]


def test_active_variants_are_active_only_ordered_by_id(make_product, make_variant):
    product = make_product()
    first = make_variant(product=product)
    make_variant(product=product, is_active=False)
    third = make_variant(product=product)
    assert list(product.active_variants()) == [first, third]


def test_main_image_is_the_one_with_smallest_position(make_product):
    product = make_product()
    assert product.main_image() is None
    ProductImage.objects.create(product=product, image="products/b.jpg", position=2)
    first = ProductImage.objects.create(product=product, image="products/a.jpg", position=1)
    assert product.main_image() == first


def test_in_stock(make_variant, make_product):
    assert make_variant(stock=1).in_stock
    assert not make_variant(stock=0).in_stock
    assert not make_variant(stock=3, is_active=False).in_stock
    assert not make_variant(product=make_product(is_active=False), stock=3).in_stock


def test_variant_str(make_product, make_variant):
    v = make_variant(product=make_product(name="Воблер Щука"), name="Червоний")
    assert str(v) == "Воблер Щука — Червоний"


def test_categories_ordered_by_position_then_name():
    last = Category.objects.create(name="Б", slug="b", position=2)
    second = Category.objects.create(name="Я", slug="ya", position=1)
    first = Category.objects.create(name="А", slug="a", position=1)
    assert list(Category.objects.all()) == [first, second, last]


def test_category_with_products_cannot_be_deleted(make_product):
    product = make_product()
    with pytest.raises(ProtectedError):
        product.category.delete()


def test_catalog_admin_pages_load(admin_client, variant):
    for url in ["/admin/catalog/product/", f"/admin/catalog/product/{variant.product.pk}/change/",
                "/admin/catalog/variant/", "/admin/catalog/category/"]:
        assert admin_client.get(url).status_code == 200


def test_catalog_admin_add_pages_load(admin_client):
    for url in ["/admin/catalog/product/add/", "/admin/catalog/variant/add/", "/admin/catalog/category/add/"]:
        assert admin_client.get(url).status_code == 200


def test_product_admin_list_handles_missing_price_and_shows_thumbnail(admin_client, make_product, variant):
    ProductImage.objects.create(product=variant.product, image="products/a.jpg", position=1)
    make_product(name="Без варіантів")
    r = admin_client.get("/admin/catalog/product/")
    assert r.status_code == 200
    html = r.content.decode()
    assert "780 грн" in html
    assert "/media/products/a.jpg" in html
    assert "Без варіантів" in html


@pytest.mark.parametrize("price", [Decimal("0"), Decimal("0.00"), Decimal("-5.00")])
def test_variant_price_must_be_positive(make_product, price):
    variant = Variant(product=make_product(), name="Тест", sku="PRICE-1", price=price, stock=1)
    with pytest.raises(ValidationError) as error:
        variant.full_clean()
    assert "price" in error.value.message_dict


def test_variant_price_of_one_kopeck_is_valid(make_product):
    Variant(product=make_product(), name="Тест", sku="PRICE-2", price=Decimal("0.01"), stock=1).full_clean()
