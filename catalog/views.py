"""Storefront pages: the product list (optionally one category) and the product page."""

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_safe

from .models import Category, Product, Variant


def _active_variants():
    # Same rows and order as Product.active_variants(), but prefetchable: one query for the whole page.
    return Prefetch("variants", queryset=Variant.objects.filter(is_active=True).order_by("id"), to_attr="active_list")


def _storefront_products():
    """Visible products with everything the pages read prefetched (reverse-FK prefetch also sets variant.product)."""
    return (
        Product.objects.visible()
        .select_related("category")
        .prefetch_related(_active_variants(), "images")  # images come back ordered by position, id (model Meta)
    )


def _with_card_data(product):
    """Attach what a product card shows: the cover photo and the price range of the active variants."""
    prices = [variant.price for variant in product.active_list]
    product.cover = next(iter(product.images.all()), None)
    product.price_min = min(prices, default=None)
    product.price_max = max(prices, default=None)
    return product


@require_safe
def product_list(request):
    products = _storefront_products().order_by("category__position", "category__name", "name")
    category = None
    slug = request.GET.get("category")
    if slug:
        category = get_object_or_404(Category, slug=slug)
        products = products.filter(category=category)
    return render(
        request,
        "catalog/product_list.html",
        {"category": category, "products": [_with_card_data(product) for product in products]},
    )


@require_safe
def product_detail(request, slug):
    product = get_object_or_404(_storefront_products(), slug=slug)
    variants = product.active_list
    # Preselect the first variant that can be bought; None when everything is sold out.
    default = next((variant for variant in variants if variant.in_stock), None)
    return render(
        request,
        "catalog/product_detail.html",
        {
            "product": product,
            "variants": variants,
            "default_variant_id": default.pk if default else None,
            "images": list(product.images.all()),
        },
    )
