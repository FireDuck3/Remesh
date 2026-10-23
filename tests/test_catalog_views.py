import re
from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext

from catalog.models import Category, ProductImage

# --- product list ------------------------------------------------------------------------------------------


def test_list_shows_only_visible(client, make_product, make_variant):
    a = make_product(name="Коробка А")
    make_variant(product=a)
    b = make_product(name="Схована Б", is_active=False)
    make_variant(product=b)
    html = client.get("/").content.decode()
    assert "Коробка А" in html and "Схована Б" not in html


def test_category_filter_and_unknown_category(client, make_product, make_variant):
    p = make_product(name="Чучундра")
    make_variant(product=p)
    other = make_product(name="Коробка")
    make_variant(product=other)
    html = client.get(f"/?category={p.category.slug}").content.decode()
    assert "Чучундра" in html and "Коробка" not in html
    assert client.get("/?category=nope").status_code == 404


def test_list_is_ordered_by_category_position_then_name(client, make_product, make_variant):
    late = Category.objects.create(name="Пізня", slug="late", position=2)
    early = Category.objects.create(name="Рання", slug="early", position=1)
    for name, category in [("Б", late), ("Я", early), ("А", early)]:
        make_variant(product=make_product(name=f"Товар {name}", category=category))
    html = client.get("/").content.decode()
    assert html.index("Товар А") < html.index("Товар Я") < html.index("Товар Б")


def test_card_price_from_when_prices_differ(client, make_product, make_variant):
    p = make_product()
    make_variant(product=p, price=Decimal("90.00"))
    make_variant(product=p, price=Decimal("120.00"))
    assert "від 90 грн" in client.get("/").content.decode()


def test_card_price_plain_when_prices_equal(client, make_product, make_variant):
    p = make_product()
    make_variant(product=p, price=Decimal("90.00"))
    make_variant(product=p, price=Decimal("90.00"))
    make_variant(product=p, price=Decimal("10.00"), is_active=False)  # inactive prices do not count
    html = client.get("/").content.decode()
    assert "90 грн" in html and "від" not in html


def test_card_links_to_detail(client, variant):
    html = client.get("/").content.decode()
    assert f'href="/p/{variant.product.slug}/"' in html


def test_placeholder_when_no_images(client, variant):
    assert "img/placeholder.svg" in client.get("/").content.decode()


def test_card_uses_main_image(client, variant):
    ProductImage.objects.create(product=variant.product, image="products/second.jpg", position=2)
    ProductImage.objects.create(product=variant.product, image="products/first.jpg", position=1)
    html = client.get("/").content.decode()
    assert "/media/products/first.jpg" in html and "second.jpg" not in html
    assert "placeholder.svg" not in html


def test_empty_catalog_says_so(client):
    assert "Поки що немає товарів" in client.get("/").content.decode()


# --- navigation ---------------------------------------------------------------------------------------------


def test_nav_lists_only_categories_with_visible_products(client, make_product, make_variant):
    shown = Category.objects.create(name="Силікон", slug="silicone")
    make_variant(product=make_product(category=shown))
    hidden_product = Category.objects.create(name="Знятий з продажу", slug="gone")
    make_variant(product=make_product(category=hidden_product, is_active=False))
    no_variants = Category.objects.create(name="Без варіантів", slug="empty")
    make_variant(product=make_product(category=no_variants), is_active=False)
    Category.objects.create(name="Порожня", slug="nothing")
    html = client.get("/cart/").content.decode()  # the menu is part of the base layout
    assert 'href="/?category=silicone"' in html and "Силікон" in html
    for name in ("Знятий з продажу", "Без варіантів", "Порожня"):
        assert name not in html
    assert "aria-current" not in html
    assert 'aria-current="page"' in client.get("/?category=silicone").content.decode()  # the open category is marked


def test_nav_is_absent_without_categories(client):
    assert "site-header__nav" not in client.get("/cart/").content.decode()


# --- product page -------------------------------------------------------------------------------------------


def test_detail_variants(client, make_product, make_variant):
    p = make_product(slug="chuchundra")
    out = make_variant(product=p, name="LOX UV", stock=0)
    ok = make_variant(product=p, name="WHITE UV", stock=4)
    make_variant(product=p, name="OFF", is_active=False)
    html = client.get("/p/chuchundra/").content.decode()
    assert "OFF" not in html and 'hx-post="/cart/add/"' in html
    assert re.search(rf'value="{out.pk}"[^>]*disabled', html)
    assert re.search(rf'value="{ok.pk}"[^>]*checked', html)
    assert not re.search(rf'value="{out.pk}"[^>]*checked', html)  # the sold-out one never preselected
    assert not re.search(rf'value="{ok.pk}"[^>]*disabled', html)


def test_detail_labels_show_name_and_price(client, make_product, make_variant):
    p = make_product(slug="box", description="Органайзер MEIHO, друк 3D")
    make_variant(product=p, name="Малий", price=Decimal("1250.50"), stock=2)
    make_variant(product=p, name="Великий", stock=0)
    html = client.get("/p/box/").content.decode()
    assert "Малий — 1 250,50 грн" in html and "Органайзер MEIHO, друк 3D" in html
    assert html.count("немає в наявності") == 1  # only the sold-out variant says so


def test_detail_preselects_first_variant_in_stock(client, make_product, make_variant):
    p = make_product(slug="lure")
    make_variant(product=p, stock=0)
    first = make_variant(product=p, stock=3)
    make_variant(product=p, stock=9)
    html = client.get("/p/lure/").content.decode()
    assert html.count("checked") == 1 and re.search(rf'value="{first.pk}"[^>]*checked', html)


def test_detail_all_sold_out_disables_buying(client, make_product, make_variant):
    p = make_product(slug="sold-out")
    make_variant(product=p, stock=0)
    html = client.get("/p/sold-out/").content.decode()
    assert "checked" not in html
    assert re.search(r'<button type="submit"[^>]*disabled', html)


def test_detail_form_works_without_js_and_surfaces_errors(client, variant):
    html = client.get(f"/p/{variant.product.slug}/").content.decode()
    form = re.search(r"<form[^>]*>", html).group(0)
    assert 'method="post"' in form and 'action="/cart/add/"' in form
    assert 'hx-target="#cart-counter"' in form and 'hx-swap="outerHTML"' in form
    assert "csrfmiddlewaretoken" in html
    assert re.search(r'name="quantity"[^>]*min="1"', html)
    # htmx 2 does not swap 4xx: the handler writes the server's message (409 "Немає в наявності") next to the button
    assert "hx-on::after-request=" in form and "responseText" in form and "409" in form
    assert 'role="status"' in html


def test_detail_shows_images_or_placeholder(client, variant):
    url = f"/p/{variant.product.slug}/"
    assert "img/placeholder.svg" in client.get(url).content.decode()
    ProductImage.objects.create(product=variant.product, image="products/a.jpg")
    html = client.get(url).content.decode()
    assert "/media/products/a.jpg" in html and "placeholder.svg" not in html


def test_detail_404_for_inactive(client, make_product, make_variant):
    p = make_product(slug="off", is_active=False)
    make_variant(product=p)
    assert client.get("/p/off/").status_code == 404


def test_detail_404_without_active_variants_and_unknown(client, make_product, make_variant):
    p = make_product(slug="bare")
    make_variant(product=p, is_active=False)
    assert client.get("/p/bare/").status_code == 404
    assert client.get("/p/nope/").status_code == 404


# --- queries ------------------------------------------------------------------------------------------------


def _query_count(client, url):
    with CaptureQueriesContext(connection) as queries:
        assert client.get(url).status_code == 200
    return len(queries)


def _stocked_product(make_product, make_variant, variants=3, **kw):
    p = make_product(**kw)
    for i in range(variants):
        make_variant(product=p, stock=i)  # stock 0 is sold out: exercises Variant.in_stock
    for i in range(2):
        ProductImage.objects.create(product=p, image=f"products/{p.slug}-{i}.jpg", position=i)
    return p


def test_list_query_count_does_not_grow_with_products(client, make_product, make_variant):
    _stocked_product(make_product, make_variant)
    client.get("/")  # warm-up
    few = _query_count(client, "/")
    for _ in range(5):
        _stocked_product(make_product, make_variant)
    assert _query_count(client, "/") == few


def test_detail_query_count_does_not_grow_with_variants(client, make_product, make_variant):
    p = _stocked_product(make_product, make_variant, variants=1, slug="grow")
    url = "/p/grow/"
    client.get(url)  # warm-up
    few = _query_count(client, url)
    for i in range(6):
        make_variant(product=p, stock=i)
    ProductImage.objects.create(product=p, image="products/extra.jpg", position=9)
    assert _query_count(client, url) == few
