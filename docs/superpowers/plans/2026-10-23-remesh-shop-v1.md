# Remesh Shop v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Робочий інтернет-магазин бренду REMESH (каталог → кошик → оформлення з НП → Telegram + адмінка) як демо для пітчу Remesh Fishing Team.

**Architecture:** Один Django-проєкт `config` з п'ятьма застосунками (`catalog`, `cart`, `orders`, `delivery`, `notify`), серверний рендер шаблонів, HTMX для кошика й автокомпліту НП. Бізнес-логіка — у сервісах (`cart/cart.py`, `orders/services.py`), зовнішні API — у тонких клієнтах (`delivery/novaposhta.py`, `notify/telegram.py`), які підміняються в тестах.

**Tech Stack:** Python 3.14, Django 5.2 LTS, HTMX 2.0.4, SQLite (dev) / PostgreSQL (prod), requests, whitenoise, gunicorn, pytest + pytest-django + responses.

**Spec:** `docs/superpowers/specs/2026-10-23-remesh-shop-design.md`

## Global Constraints

- Python 3.14 (встановлений на машині; спека казала 3.12 — 3.14 сумісний з Django ≥ 5.2.8). `Django>=5.2.8,<6.0`.
- Runtime-залежності (`requirements.txt`): `Django>=5.2.8,<6.0`, `dj-database-url`, `whitenoise`, `gunicorn`, `psycopg[binary]`, `requests`, `python-dotenv`, `Pillow`. Dev (`requirements-dev.txt`): `-r requirements.txt`, `pytest`, `pytest-django`, `responses`. Інших не додавати.
- `LANGUAGE_CODE = "uk"`, `TIME_ZONE = "Europe/Kyiv"`, `USE_TZ = True`. Весь текст для покупця й менеджера — українською; `verbose_name` моделей і полів — українською.
- Гроші — `DecimalField(max_digits=10, decimal_places=2)`, гривня. Відображення — лише через `format_uah` / фільтр `uah` (Task 2): `780 грн`, `1 250,50 грн` (роздільники — нерозривний пробіл `\u00a0`).
- Змінні середовища: `SECRET_KEY`, `DEBUG` (`"1"`/`"0"`, за замовчуванням `"0"`), `HTTPS` (`"1"` вмикає безпечні cookie/редирект, за замовчуванням `"0"`), `DATABASE_URL` (за замовчуванням `sqlite:///db.sqlite3`), `ALLOWED_HOSTS` і `CSRF_TRUSTED_ORIGINS` (через кому), `SITE_URL` (за замовчуванням `http://127.0.0.1:8000`), `NOVA_POSHTA_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SERVE_MEDIA` (`"1"` за замовчуванням). `.env` читається через python-dotenv, якщо існує; `.env` — у `.gitignore`.
- Номер замовлення — `f"RM-{pk:04d}"`.
- Статуси замовлення: `new` «Нове», `confirmed` «Підтверджене», `shipped` «Відправлене», `completed` «Виконане», `cancelled` «Скасоване». Оплата: лише `cod` «Накладений платіж».
- Зовнішні HTTP-виклики — `requests` з `timeout=5`. Жодна помилка НП чи Telegram не повертає покупцю 500 і не скасовує замовлення.
- HTMX: `<script src="https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js"></script>`; CSRF для HTMX — `hx-headers` на `<body>`.
- Static: whitenoise з `whitenoise.storage.CompressedStaticFilesStorage` (без manifest — тести рендерять `{% static %}` без collectstatic).
- Команди виконуються з `C:\dev\remesh-shop` у Git Bash: Python — `.venv/Scripts/python`, тести — `.venv/Scripts/python -m pytest`.
- Кожен коміт закінчується рядком `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; префікси `feat:` / `test:` / `chore:`.

## Review Focus

1. **Чужа сторінка «Дякуємо».** Номери `RM-0001, RM-0002…` послідовні — хтось підставить чужий номер і побачить ім'я й телефон. Очікується 404 для будь-якої сесії, крім тієї, що оформила. → тест у Task 9.
2. **Підроблені POST у кошик.** `quantity` = `0`, `-3`, `"x"`, неіснуючий `variant_id` — очікується 400 і порожній кошик, ніколи не від'ємний залишок. → тест у Task 4.
3. **Повторний запуск seed при кожному деплої.** `build.sh` запускає `seed_remesh` щоразу — очікується, що ціни й залишки, змінені менеджером, не перезаписуються і дублікати не з'являються. → тест у Task 11.
4. **Скасування через форму редагування в адмінці** (а не масовою дією) — очікується повернення залишків рівно один раз, а статус скасованого замовлення більше не змінюється. → тест у Task 10.
5. **Видалений менеджером варіант лишився в сесійному кошику покупця** — очікується, що кошик, лічильник у шапці й оформлення не падають 500, а позиція тихо зникає. → тести в Task 3 і Task 4.

---

## Структура файлів

```
remesh-shop/
  manage.py  requirements.txt  requirements-dev.txt  pytest.ini  .gitignore  .env.example
  build.sh  render.yaml  README.md
  config/            settings.py  urls.py  wsgi.py
  templates/base.html
  static/css/site.css  static/img/logo.svg  static/img/placeholder.svg  static/js/checkout.js
  catalog/           models.py admin.py views.py urls.py context_processors.py seed_data.py
                     templatetags/money.py  management/commands/seed_remesh.py  seed_images/
                     templates/catalog/{product_list,product_detail,_product_card}.html
  cart/              cart.py views.py urls.py context_processors.py
                     templates/cart/{cart_detail,_cart_body,_counter}.html
  orders/            models.py services.py phone.py forms.py views.py urls.py admin.py
                     management/commands/setup_roles.py  templates/orders/{checkout,thanks}.html
  delivery/          novaposhta.py views.py urls.py templates/delivery/{_cities,_warehouses}.html
  notify/            telegram.py
  tests/             conftest.py  fixtures/*.json  test_*.py
```

---

### Task 1: Каркас проєкту, налаштування з env, healthcheck

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `.gitignore`, `.env.example`, `manage.py`, `config/{__init__,settings,urls,wsgi}.py`, `tests/test_health.py`

**Interfaces:**
- Produces: `GET /healthz/` → 200, тіло `ok`. `settings.NOVA_POSHTA_API_KEY`, `settings.TELEGRAM_BOT_TOKEN`, `settings.TELEGRAM_CHAT_ID`, `settings.SITE_URL` (str, без кінцевого `/`).

- [ ] **Step 1: Створити venv і встановити залежності**

Run: `py -3.14 -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt`
Expected: `Successfully installed Django-5.2.…`

- [ ] **Step 2: Згенерувати проєкт**

Run: `.venv/Scripts/django-admin startproject config .`
`pytest.ini`: `DJANGO_SETTINGS_MODULE = config.settings`, `testpaths = tests`, `python_files = test_*.py`, `pythonpath = .`. Порожній `tests/__init__.py`.
`.gitignore`: `.venv/`, `db.sqlite3`, `.env`, `media/`, `staticfiles/`, `__pycache__/`.

- [ ] **Step 3: Написати падаючий тест**

```python
# tests/test_health.py
def test_healthz_returns_ok(client):
    r = client.get("/healthz/")
    assert r.status_code == 200
    assert r.content == b"ok"
```

- [ ] **Step 4: Переконатися, що падає**

Run: `.venv/Scripts/python -m pytest tests/test_health.py -v` → FAIL (404)

- [ ] **Step 5: Переписати `config/settings.py` під env, додати `/healthz/`**

Усі змінні з Global Constraints; `DATABASES = {"default": dj_database_url.parse(DATABASE_URL)}`; `CACHES` — LocMem; whitenoise-middleware одразу після `SecurityMiddleware`; `STATIC_ROOT = BASE_DIR / "staticfiles"`, `STATICFILES_DIRS = [BASE_DIR / "static"]`; `TEMPLATES[0]["DIRS"] = [BASE_DIR / "templates"]`; `LOGGING` — console-handler рівня WARNING для логерів `delivery` і `notify`. `.env.example` перелічує всі змінні з `DEBUG=1`. View `healthz` повертає `HttpResponse("ok")`.

- [ ] **Step 6: Перевірити**

Run: `.venv/Scripts/python -m pytest -v && .venv/Scripts/python manage.py check`
Expected: 1 passed; `System check identified no issues (0 silenced).`

- [ ] **Step 7: Commit** — `chore: scaffold Django project with env settings and healthcheck`

---

### Task 2: Моделі каталогу, адмінка каталогу, фільтр грошей

**Files:**
- Create: `catalog/{__init__,apps,models,admin}.py`, `catalog/templatetags/{__init__,money}.py`, `catalog/migrations/`, `tests/conftest.py`, `tests/data.py`, `tests/test_catalog_models.py`, `tests/test_money.py`
- Modify: `config/settings.py` (INSTALLED_APPS, `MEDIA_URL="/media/"`, `MEDIA_ROOT=BASE_DIR/"media"`), `config/urls.py` (віддача media, коли `DEBUG` або `SERVE_MEDIA`: `re_path(r"^media/(?P<path>.*)$", django.views.static.serve, {"document_root": MEDIA_ROOT})`)

**Interfaces:**
- Produces:
  - `Category(name, slug unique, position int)`; `Meta.ordering = ["position", "name"]`.
  - `Product(category FK PROTECT related_name="products", name, slug unique, description TextField blank, is_active=True, created_at auto)`; `Product.objects.visible() -> QuerySet` (активні, з ≥1 активним варіантом, `distinct`); `product.active_variants() -> QuerySet` (за `id`); `product.min_price() -> Decimal | None`; `product.main_image() -> ProductImage | None` (найменша `position`).
  - `ProductImage(product FK CASCADE related_name="images", image ImageField(upload_to="products/"), position int)`.
  - `Variant(product FK CASCADE related_name="variants", name, sku unique, price Decimal(10,2), stock PositiveIntegerField default 0, is_active=True)`; `variant.in_stock -> bool` (`is_active and product.is_active and stock > 0`); `str(variant) == f"{product.name} — {name}"`.
  - `catalog.templatetags.money.format_uah(value: Decimal) -> str`; шаблонний фільтр `uah` (`{% load money %}`).
  - Фікстури в `tests/conftest.py`: `make_product(**kw) -> Product` (створює категорію за потреби), `make_variant(product=None, **kw) -> Variant` (унікальний `sku` автоматично, за замовчуванням `price=Decimal("100.00")`, `stock=10`), `variant` (`price=Decimal("780.00")`, `stock=5`), `session` (`django.contrib.sessions.backends.db.SessionStore()`), autouse-фікстура: доступ до БД для всіх тестів, `cache.clear()`, `settings.NOVA_POSHTA_API_KEY = settings.TELEGRAM_BOT_TOKEN = settings.TELEGRAM_CHAT_ID = ""` (тести ніколи не ходять у мережу).

  - Константи тестів — у `tests/data.py` (імпорт `from tests.data import CUSTOMER, FORM`):

```python
CUSTOMER = dict(customer_name="Іван Петренко", phone="+380985936815", np_city_ref="",
                np_city_name="Вінниця", np_warehouse_ref="", np_warehouse_name="Відділення №1", comment="")
FORM = {**CUSTOMER, "phone": "098 593 68 15"}   # сирі дані форми оформлення (Task 9, 12)
```

- [ ] **Step 1: Написати падаючі тести**

```python
# tests/test_catalog_models.py
def test_min_price_ignores_inactive_variants(make_variant):
    v = make_variant(price=Decimal("120.00"))
    make_variant(product=v.product, price=Decimal("90.00"), is_active=False)
    make_variant(product=v.product, price=Decimal("150.00"))
    assert v.product.min_price() == Decimal("120.00")

def test_visible_excludes_inactive_and_variantless(make_product, make_variant):
    shown = make_product(name="A"); make_variant(product=shown)
    hidden = make_product(name="B", is_active=False); make_variant(product=hidden)
    no_active = make_product(name="C"); make_variant(product=no_active, is_active=False)
    assert list(Product.objects.visible()) == [shown]

def test_in_stock(make_variant, make_product):
    assert make_variant(stock=1).in_stock
    assert not make_variant(stock=0).in_stock
    assert not make_variant(stock=3, is_active=False).in_stock
    assert not make_variant(product=make_product(is_active=False), stock=3).in_stock

def test_catalog_admin_pages_load(admin_client, variant):
    for url in ["/admin/catalog/product/", f"/admin/catalog/product/{variant.product.pk}/change/",
                "/admin/catalog/variant/", "/admin/catalog/category/"]:
        assert admin_client.get(url).status_code == 200

# tests/test_money.py
@pytest.mark.parametrize("value,expected", [
    (Decimal("780.00"), "780\u00a0грн"),
    (Decimal("1250.50"), "1\u00a0250,50\u00a0грн"),
    (Decimal("0.5"), "0,50\u00a0грн"),
    (Decimal("12000"), "12\u00a0000\u00a0грн"),
])
def test_format_uah(value, expected):
    assert format_uah(value) == expected
```

- [ ] **Step 2: Переконатися, що падають** — `.venv/Scripts/python -m pytest tests/test_catalog_models.py tests/test_money.py -v` → FAIL (ImportError)

- [ ] **Step 3: Реалізувати моделі, менеджер `visible()`, `format_uah`, міграцію** (`manage.py makemigrations catalog`)

- [ ] **Step 4: Реалізувати адмінку каталогу**

`admin.site.site_header = "REMESH — адмінка"`. `ProductAdmin`: inlines `VariantInline` (Tabular: name, sku, price, stock, is_active) і `ProductImageInline`; `list_display` — мініатюра, name, category, is_active, мін. ціна через `format_uah`; `list_filter` (category, is_active); `search_fields = ["name"]`; `prepopulated_fields = {"slug": ("name",)}`. `VariantAdmin`: `list_display` (product, name, sku, price, stock, is_active), `list_editable = ("price", "stock", "is_active")`, `search_fields` (sku, name, product__name). `CategoryAdmin`: `list_editable = ("position",)`, prepopulated slug.

- [ ] **Step 5: Перевірити** — `.venv/Scripts/python -m pytest -v` → усі PASS

- [ ] **Step 6: Commit** — `feat: catalog models, admin and UAH money filter`

---

### Task 3: Сервіс кошика (сесія)

**Files:**
- Create: `cart/{__init__,apps,cart}.py`, `tests/test_cart.py`
- Modify: `config/settings.py` (INSTALLED_APPS)

**Interfaces:**
- Consumes: `Variant`, `variant.in_stock` (Task 2).
- Produces:

```python
@dataclass(frozen=True)
class CartLine:
    variant: Variant
    quantity: int
    line_total: Decimal          # variant.price * quantity

class Cart:
    SESSION_KEY = "cart"         # session["cart"] = {"<variant_id>": qty}
    def __init__(self, session) -> None
    def add(self, variant: Variant, quantity: int = 1) -> int        # нова к-сть; cap = variant.stock; не in_stock → 0, нічого не зберігає; quantity < 1 → ValueError
    def set(self, variant_id: int, quantity: int) -> int             # <= 0 або варіанта нема → видаляє, 0; cap = stock
    def remove(self, variant_id: int) -> None
    def clear(self) -> None
    def lines(self) -> list[CartLine]   # у порядку додавання; id видалених варіантів прибирає з сесії
    def total(self) -> Decimal          # Decimal("0.00") для порожнього
    def count(self) -> int              # сума кількостей, лише існуючі варіанти
    def is_empty(self) -> bool
```

Кожна зміна ставить `session.modified = True`.

- [ ] **Step 1: Написати падаючі тести**

```python
def test_add_merges_same_variant(session, make_variant):
    v = make_variant(stock=10, price=Decimal("120.00"))
    cart = Cart(session); cart.add(v, 2); cart.add(v, 3)
    assert cart.count() == 5 and cart.total() == Decimal("600.00")

def test_add_caps_at_stock(session, make_variant):
    assert Cart(session).add(make_variant(stock=3), 5) == 3

def test_add_unavailable_variant_stores_nothing(session, make_variant):
    cart = Cart(session)
    assert cart.add(make_variant(stock=0)) == 0
    assert cart.add(make_variant(is_active=False)) == 0
    assert cart.is_empty()

@pytest.mark.parametrize("qty", [0, -1])
def test_add_rejects_non_positive_quantity(session, variant, qty):
    with pytest.raises(ValueError):
        Cart(session).add(variant, qty)

def test_set_zero_removes_and_set_caps(session, make_variant):
    v = make_variant(stock=4); cart = Cart(session); cart.add(v, 1)
    assert cart.set(v.pk, 9) == 4
    assert cart.set(v.pk, 0) == 0 and cart.is_empty()

def test_deleted_variant_disappears_without_error(session, make_variant):
    keep, gone = make_variant(), make_variant()
    cart = Cart(session); cart.add(keep); cart.add(gone); gone.delete()
    assert cart.count() == 1
    assert [line.variant for line in cart.lines()] == [keep]

def test_state_survives_new_instance(session, variant):
    Cart(session).add(variant, 2)
    assert Cart(session).count() == 2
```

- [ ] **Step 2: Переконатися, що падають** — `.venv/Scripts/python -m pytest tests/test_cart.py -v` → FAIL

- [ ] **Step 3: Реалізувати `cart/cart.py`** (один запит `Variant.objects.select_related("product").in_bulk(ids)` на `lines()`)

- [ ] **Step 4: Перевірити** — `tests/test_cart.py` → PASS

- [ ] **Step 5: Commit** — `feat: session cart service`

---

### Task 4: Базовий шаблон і сторінки кошика (HTMX)

**Files:**
- Create: `templates/base.html`, `static/css/site.css`, `static/img/logo.svg`, `cart/{views,urls,context_processors}.py`, `cart/templates/cart/{cart_detail,_cart_body,_counter}.html`, `tests/test_cart_views.py`
- Modify: `config/urls.py` (`path("cart/", include("cart.urls"))`), `config/settings.py` (context processor `cart.context_processors.cart_count`)

**Interfaces:**
- Consumes: `Cart` (Task 3), фільтр `uah` (Task 2).
- Produces:
  - URL-и (namespace `cart`): `detail` GET `/cart/`; `add` POST `/cart/add/`; `update` POST `/cart/update/`; `remove` POST `/cart/remove/`. POST-поля: `variant_id`, `quantity` (для `remove` лише `variant_id`).
  - `_counter.html`: `<a id="cart-counter" href="/cart/" data-count="{{ cart_count }}">Кошик · {{ cart_count }}</a>`.
  - `_cart_body.html`: обгортка `id="cart-body"`; позиції (назва варіанта, ціна, поле кількості з `hx-post` на `update`, кнопка видалення з `hx-post` на `remove`), сума через `uah`; для порожнього — «Кошик порожній» і посилання на `/`; кнопка «Оформити замовлення» → `/checkout/` (URL з'явиться в Task 9 — тут літерал).
  - Відповіді: не-HTMX → 302 на `/cart/`. HTMX `add` → `_counter.html`; HTMX `update`/`remove` → `_cart_body.html` + лічильник з `hx-swap-oob="true"`. Відсутній `quantity` у `add` = 1. Невалідні дані (`variant_id` відсутній/не число/неіснуючий; `quantity` не число, або < 1 для `add`, або < 0 для `update`) → 400. `update` з `quantity=0` видаляє позицію. Існуючий, але не `in_stock` варіант у `add` → 409 з текстом «Немає в наявності».
  - `templates/base.html`: блоки `title`, `content`; `<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>`; шапка — логотип (посилання на `/`), `{% include "cart/_counter.html" %}`; підвал — точний текст зі спеки: «м. Вінниця, вул. Костянтина Василенка 9», «Пн–Сб 9:00–20:00, Нд 9:00–17:00», «+380 98 593 68 15», посилання на `https://www.instagram.com/remesh.fishing_team/`.
  - `site.css`: mobile-first, чорно-біла палітра, без фреймворків.

- [ ] **Step 1: Написати падаючі тести**

```python
def test_htmx_add_returns_counter(client, make_variant):
    v = make_variant(stock=5)
    r = client.post("/cart/add/", {"variant_id": v.pk, "quantity": 2}, HTTP_HX_REQUEST="true")
    assert r.status_code == 200 and 'data-count="2"' in r.content.decode()

def test_plain_add_redirects_to_cart(client, variant):
    r = client.post("/cart/add/", {"variant_id": variant.pk, "quantity": 1})
    assert r.status_code == 302 and r["Location"] == "/cart/"

@pytest.mark.parametrize("payload", [
    {"variant_id": "abc", "quantity": 1}, {"variant_id": 999999, "quantity": 1}, {"quantity": 1},
    {"variant_id": "PK", "quantity": 0}, {"variant_id": "PK", "quantity": -3}, {"variant_id": "PK", "quantity": "x"},
])
def test_add_rejects_bad_input(client, variant, payload):
    payload = {k: variant.pk if v == "PK" else v for k, v in payload.items()}
    assert client.post("/cart/add/", payload).status_code == 400
    assert Cart(client.session).is_empty()
    variant.refresh_from_db(); assert variant.stock == 5

def test_add_out_of_stock_is_409(client, make_variant):
    assert client.post("/cart/add/", {"variant_id": make_variant(stock=0).pk, "quantity": 1}).status_code == 409

def test_htmx_update_returns_body_and_oob_counter(client, make_variant):
    v = make_variant(stock=5); client.post("/cart/add/", {"variant_id": v.pk, "quantity": 1})
    html = client.post("/cart/update/", {"variant_id": v.pk, "quantity": 3}, HTTP_HX_REQUEST="true").content.decode()
    assert 'id="cart-body"' in html and 'data-count="3"' in html and 'hx-swap-oob="true"' in html

def test_cart_page_shows_total(client, make_variant):
    v = make_variant(price=Decimal("780.00"), stock=5); client.post("/cart/add/", {"variant_id": v.pk, "quantity": 2})
    assert "1\u00a0560\u00a0грн" in client.get("/cart/").content.decode()

def test_cart_page_survives_deleted_variant(client, make_variant):
    v = make_variant(); client.post("/cart/add/", {"variant_id": v.pk, "quantity": 1}); v.delete()
    r = client.get("/cart/")
    assert r.status_code == 200 and "Кошик порожній" in r.content.decode() and 'data-count="0"' in r.content.decode()
```

- [ ] **Step 2: Переконатися, що падають** — `tests/test_cart_views.py` → FAIL (404)

- [ ] **Step 3: Реалізувати views, urls, context processor, шаблони, CSS, logo.svg** (logo — текст «REMESH» білим на чорному колі, як в Instagram)

- [ ] **Step 4: Перевірити** — `.venv/Scripts/python -m pytest -v` → усі PASS

- [ ] **Step 5: Commit** — `feat: base layout and HTMX cart pages`

---

### Task 5: Сторінки каталогу і товару

**Files:**
- Create: `catalog/{views,urls,context_processors}.py`, `catalog/templates/catalog/{product_list,product_detail,_product_card}.html`, `static/img/placeholder.svg`, `tests/test_catalog_views.py`
- Modify: `config/urls.py` (`path("", include("catalog.urls"))` — останнім), `config/settings.py` (context processor `catalog.context_processors.nav_categories`), `templates/base.html` (меню категорій у шапці)

**Interfaces:**
- Consumes: `Product.objects.visible()`, `min_price()`, `main_image()`, `active_variants()`, `in_stock` (Task 2); URL `cart:add` (Task 4).
- Produces: URL-и (namespace `catalog`): `list` GET `/` (параметр `?category=<slug>`; невідомий slug → 404), `detail` GET `/p/<slug>/` (неактивний або невидимий товар → 404). Контекст `nav_categories` — категорії, що мають видимі товари.
  - Картка товару: фото або `static/img/placeholder.svg`, назва, ціна — `від {min}` якщо ціни активних варіантів різні, інакше `{min}`.
  - Сторінка товару: опис; радіокнопки `name="variant_id"` для активних варіантів з підписом `{name} — {price|uah}`; варіант зі `stock == 0` має `disabled` і «немає в наявності»; перший `in_stock` — `checked`; поле `quantity` (min 1); форма `hx-post="/cart/add/"` `hx-target="#cart-counter"` `hx-swap="outerHTML"`; без JS форма теж працює (`method="post" action="/cart/add/"`).

- [ ] **Step 1: Написати падаючі тести**

```python
def test_list_shows_only_visible(client, make_product, make_variant):
    a = make_product(name="Коробка А"); make_variant(product=a)
    b = make_product(name="Схована Б", is_active=False); make_variant(product=b)
    html = client.get("/").content.decode()
    assert "Коробка А" in html and "Схована Б" not in html

def test_category_filter_and_unknown_category(client, make_product, make_variant):
    p = make_product(name="Чучундра"); make_variant(product=p)
    assert "Чучундра" in client.get(f"/?category={p.category.slug}").content.decode()
    assert client.get("/?category=nope").status_code == 404

def test_card_price_from_when_prices_differ(client, make_product, make_variant):
    p = make_product(); make_variant(product=p, price=Decimal("90.00")); make_variant(product=p, price=Decimal("120.00"))
    assert "від 90\u00a0грн" in client.get("/").content.decode()

def test_detail_variants(client, make_product, make_variant):
    p = make_product(slug="chuchundra")
    out = make_variant(product=p, name="LOX UV", stock=0)
    ok = make_variant(product=p, name="WHITE UV", stock=4)
    make_variant(product=p, name="OFF", is_active=False)
    html = client.get("/p/chuchundra/").content.decode()
    assert "OFF" not in html and 'hx-post="/cart/add/"' in html
    assert re.search(rf'value="{out.pk}"[^>]*disabled', html)
    assert re.search(rf'value="{ok.pk}"[^>]*checked', html)

def test_detail_404_for_inactive(client, make_product, make_variant):
    p = make_product(slug="off", is_active=False); make_variant(product=p)
    assert client.get("/p/off/").status_code == 404

def test_placeholder_when_no_images(client, variant):
    assert "img/placeholder.svg" in client.get("/").content.decode()
```

- [ ] **Step 2: Переконатися, що падають** → FAIL
- [ ] **Step 3: Реалізувати views, urls, context processor, шаблони, placeholder.svg; меню категорій у `base.html`**
- [ ] **Step 4: Перевірити** — `.venv/Scripts/python -m pytest -v` → усі PASS
- [ ] **Step 5: Commit** — `feat: catalog and product pages`

---

### Task 6: Моделі замовлень і сервіси оформлення/скасування

**Files:**
- Create: `orders/{__init__,apps,models,services,phone}.py`, `orders/migrations/`, `tests/test_phone.py`, `tests/test_order_services.py`
- Modify: `config/settings.py` (INSTALLED_APPS)

**Interfaces:**
- Consumes: `Cart`, `CartLine` (Task 3); `Variant` (Task 2).
- Produces:
  - `Order`: поля зі спеки §4; `Order.Status` (TextChoices з Global Constraints), `Order.Payment` (`COD = "cod", "Накладений платіж"`); `number` (CharField 20, `unique=True, null=True, blank=True` — NULL, а не `""`, щоб паралельні insert-и не конфліктували) виставляється в `save()` після першого insert як `f"RM-{pk:04d}"`; `ordering = ["-created_at"]`.
  - `OrderItem(order FK CASCADE related_name="items", variant FK SET_NULL null, product_name, variant_name, sku, unit_price Decimal(10,2), quantity PositiveInteger)`; властивість `line_total`.
  - `orders.phone.normalize_phone(raw: str) -> str` — лишає цифри; 12 цифр з `380…` або 10 з `0…` → `"+380XXXXXXXXX"`; інакше `ValueError`.
  - `orders.services`:

```python
@dataclass(frozen=True)
class StockProblem:
    variant_id: int
    name: str            # str(variant)
    requested: int
    available: int       # variant.stock, або 0 якщо варіант/товар неактивні

class EmptyCartError(Exception): ...
class OutOfStockError(Exception):
    problems: list[StockProblem]

def place_order(cart: Cart, data: dict[str, str]) -> Order
def cancel_order(order: Order) -> bool
```

  - `place_order`: `data` має ключі `customer_name, phone, np_city_ref, np_city_name, np_warehouse_ref, np_warehouse_name, comment`. Порожній кошик → `EmptyCartError`. У `transaction.atomic()`: `select_for_update` варіантів кошика (за `id`), збір усіх проблем; якщо є — відкат, потім `cart.set(problem.variant_id, problem.available)` для кожної, `raise OutOfStockError(problems)`. Інакше — `Order` + `OrderItem` зі знімками, `stock -= quantity` (`F()`), `total`, `cart.clear()`.
  - `cancel_order`: у `atomic()` з `select_for_update` замовлення; якщо вже `cancelled` → `False`; інакше повертає `quantity` у `stock` для позицій з `variant is not None`, ставить `cancelled`, `True`.

- [ ] **Step 1: Написати падаючі тести**

```python
# tests/test_phone.py
@pytest.mark.parametrize("raw", ["0985936815", "+380985936815", "380985936815", "+38 (098) 593-68-15", "098 593 68 15"])
def test_normalize_valid(raw):
    assert normalize_phone(raw) == "+380985936815"

@pytest.mark.parametrize("raw", ["", "12345", "+44985936815", "09859368150", "abc"])
def test_normalize_invalid(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)

# tests/test_order_services.py
def test_place_order_snapshots_and_stock(session, make_variant):
    v = make_variant(name="LOX UV", price=Decimal("120.00"), stock=10)
    cart = Cart(session); cart.add(v, 3)
    order = place_order(cart, CUSTOMER)
    assert order.number == f"RM-{order.pk:04d}"
    assert (order.total, order.status, order.payment_method) == (Decimal("360.00"), "new", "cod")
    item = order.items.get()
    assert (item.product_name, item.variant_name, item.sku, item.unit_price, item.quantity) == \
           (v.product.name, "LOX UV", v.sku, Decimal("120.00"), 3)
    v.refresh_from_db(); assert v.stock == 7
    assert cart.is_empty()

def test_snapshot_survives_price_change(session, variant):
    cart = Cart(session); cart.add(variant, 1); order = place_order(cart, CUSTOMER)
    variant.price = Decimal("999.00"); variant.save()
    assert order.items.get().unit_price == Decimal("780.00")

def test_out_of_stock_creates_nothing_and_adjusts_cart(session, make_variant):
    a, b = make_variant(stock=5), make_variant(stock=5)
    cart = Cart(session); cart.add(a, 2); cart.add(b, 4)
    b.stock = 1; b.save()
    with pytest.raises(OutOfStockError) as exc:
        place_order(cart, CUSTOMER)
    assert exc.value.problems == [StockProblem(b.pk, str(b), 4, 1)]
    assert Order.objects.count() == 0
    a.refresh_from_db(); assert a.stock == 5
    assert {l.variant.pk: l.quantity for l in cart.lines()} == {a.pk: 2, b.pk: 1}

def test_deactivated_variant_is_problem_with_zero(session, make_variant):
    v = make_variant(stock=5); cart = Cart(session); cart.add(v, 1)
    v.is_active = False; v.save()
    with pytest.raises(OutOfStockError) as exc:
        place_order(cart, CUSTOMER)
    assert exc.value.problems[0].available == 0 and cart.is_empty()

def test_empty_cart_raises(session):
    with pytest.raises(EmptyCartError):
        place_order(Cart(session), CUSTOMER)

def test_cancel_restores_stock_once(session, make_variant):
    v = make_variant(stock=10); cart = Cart(session); cart.add(v, 3); order = place_order(cart, CUSTOMER)
    assert cancel_order(order) is True
    assert cancel_order(order) is False
    v.refresh_from_db(); assert v.stock == 10
    order.refresh_from_db(); assert order.status == "cancelled"

def test_cancel_with_deleted_variant(session, make_variant):
    v = make_variant(stock=10); cart = Cart(session); cart.add(v, 1); order = place_order(cart, CUSTOMER)
    v.delete()
    assert cancel_order(order) is True
```

- [ ] **Step 2: Переконатися, що падають** → FAIL
- [ ] **Step 3: Реалізувати моделі (+ `makemigrations orders`), `phone.py`, `services.py`**
- [ ] **Step 4: Перевірити** — `.venv/Scripts/python -m pytest -v` → усі PASS
- [ ] **Step 5: Commit** — `feat: orders models with place/cancel services`

---

### Task 7: Клієнт Нової Пошти й HTMX-підказки

**Files:**
- Create: `delivery/{__init__,apps,novaposhta,views,urls}.py`, `delivery/templates/delivery/{_cities,_warehouses}.html`, `tests/fixtures/np_search_settlements.json`, `tests/fixtures/np_get_warehouses.json`, `tests/test_novaposhta.py`, `tests/test_delivery_views.py`
- Modify: `config/settings.py` (INSTALLED_APPS), `config/urls.py` (`path("delivery/", include("delivery.urls"))`)

**Interfaces:**
- Produces:

```python
API_URL = "https://api.novaposhta.ua/v2.0/json/"

@dataclass(frozen=True)
class City: ref: str; name: str
@dataclass(frozen=True)
class Warehouse: ref: str; name: str
class NovaPoshtaError(Exception): ...

def is_enabled() -> bool                                                    # bool(settings.NOVA_POSHTA_API_KEY)
def search_cities(query: str, limit: int = 10) -> list[City]
def list_warehouses(city_ref: str, query: str = "", limit: int = 50) -> list[Warehouse]
```

  - Запити — `POST API_URL` з JSON `{"apiKey", "modelName": "Address", "calledMethod", "methodProperties"}`, `timeout=5`.
    `search_cities`: `calledMethod="searchSettlements"`, `methodProperties={"CityName": query, "Limit": str(limit), "Page": "1"}`; результат — `data[0]["Addresses"]` → `City(ref=a["DeliveryCity"], name=a["Present"])`.
    `list_warehouses`: `calledMethod="getWarehouses"`, `methodProperties={"CityRef": city_ref, "FindByString": query, "Limit": str(limit), "Page": "1"}`; результат — `data` → `Warehouse(ref=w["Ref"], name=w["Description"])`.
  - `query.strip()` коротший за 2 символи (для міст) → `[]` без HTTP. Без ключа → `NovaPoshtaError`. Мережева помилка, статус ≠ 200, `"success": false` → `NovaPoshtaError`.
  - Кеш: ключі `"np:c:" + sha1(query.lower())` і `"np:w:" + sha1(f"{city_ref}|{query.lower()}")`, `timeout=86400`; помилки не кешуються.
  - Views викликають функції через модуль (`from delivery import novaposhta`; `novaposhta.search_cities(...)`), щоб їх можна було підміняти. URL-и (namespace `delivery`): `cities` GET `/delivery/cities/?q=`, `warehouses` GET `/delivery/warehouses/?city_ref=&q=`.
  - Фрагмент: кожен варіант — `<button type="button" class="np-option" data-ref="{ref}" data-name="{name}">{name}</button>`; при `NovaPoshtaError` — 200 і текст «Не вдалося завантажити — введіть вручну».
  - Фікстури JSON — мінімальні відповіді у форматі API (2 міста з фейковими ref `city-ref-1`, `city-ref-2`; 2 відділення `wh-ref-1`, `wh-ref-2`), обгорнуті в `{"success": true, "data": …, "errors": []}`.

- [ ] **Step 1: Написати падаючі тести**

```python
# tests/test_novaposhta.py
@responses.activate
def test_search_cities_parses_and_sends_method(settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    responses.post(API_URL, json=load_fixture("np_search_settlements.json"))
    cities = search_cities("Вінн")
    assert cities[0] == City("city-ref-1", "м. Вінниця, Вінницька обл.")
    body = json.loads(responses.calls[0].request.body)
    assert body["calledMethod"] == "searchSettlements" and body["methodProperties"]["CityName"] == "Вінн"

@responses.activate
def test_results_cached(settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    responses.post(API_URL, json=load_fixture("np_search_settlements.json"))
    search_cities("Біла Церква"); search_cities("біла церква")
    assert len(responses.calls) == 1

@responses.activate
def test_short_query_no_request(settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    assert search_cities(" В ") == [] and len(responses.calls) == 0

@responses.activate
@pytest.mark.parametrize("kwargs", [
    {"json": {"success": False, "data": [], "errors": ["API key expired"]}},
    {"status": 500, "body": "oops"},
    {"body": requests.ConnectionError("down")},
])
def test_api_failure_raises(settings, kwargs):
    settings.NOVA_POSHTA_API_KEY = "k"
    responses.post(API_URL, **kwargs)
    with pytest.raises(NovaPoshtaError):
        search_cities("Вінниця")

def test_disabled_without_key():
    with pytest.raises(NovaPoshtaError):
        search_cities("Вінниця")

@responses.activate
def test_list_warehouses(settings):
    settings.NOVA_POSHTA_API_KEY = "k"
    responses.post(API_URL, json=load_fixture("np_get_warehouses.json"))
    assert list_warehouses("city-ref-1")[0].ref == "wh-ref-1"
    assert json.loads(responses.calls[0].request.body)["methodProperties"]["CityRef"] == "city-ref-1"

# tests/test_delivery_views.py
def test_cities_view_renders_options(client, monkeypatch):
    monkeypatch.setattr(novaposhta, "search_cities", lambda q, limit=10: [City("r1", "м. Вінниця")])
    html = client.get("/delivery/cities/?q=Він").content.decode()
    assert 'data-ref="r1"' in html and 'data-name="м. Вінниця"' in html

def test_cities_view_error_shows_manual_hint(client, monkeypatch):
    def boom(*a, **k): raise NovaPoshtaError("down")
    monkeypatch.setattr(novaposhta, "search_cities", boom)
    r = client.get("/delivery/cities/?q=Він")
    assert r.status_code == 200 and "введіть вручну" in r.content.decode()
```

- [ ] **Step 2: Переконатися, що падають** → FAIL
- [ ] **Step 3: Реалізувати `novaposhta.py`, views, urls, фрагменти, JSON-фікстури**
- [ ] **Step 4: Перевірити** — `.venv/Scripts/python -m pytest -v` → усі PASS
- [ ] **Step 5: Commit** — `feat: Nova Poshta client and autocomplete endpoints`

---

### Task 8: Telegram-сповіщення і підключення до оформлення

**Files:**
- Create: `notify/{__init__,apps,telegram}.py`, `tests/test_notify.py`
- Modify: `orders/services.py` (у `place_order` всередині `atomic()`: `transaction.on_commit(lambda: telegram.notify_new_order(order))`, імпорт `from notify import telegram`), `config/settings.py` (INSTALLED_APPS)

**Interfaces:**
- Consumes: `Order`, `OrderItem` (Task 6), `format_uah` (Task 2), `settings.SITE_URL` (Task 1).
- Produces: `format_order_message(order: Order) -> str`; `notify_new_order(order: Order) -> bool` (ніколи не кидає винятків).
  - Точний текст (рядок позиції повторюється для кожного `OrderItem`; порожній коментар → `—`):

```
🎣 Нове замовлення {number}
Сума: {total|uah}

• {product_name} — {variant_name} × {quantity} = {line_total|uah}

Клієнт: {customer_name}
Телефон: {phone}
НП: {np_city_name}, {np_warehouse_name}
Коментар: {comment}
Адмінка: {SITE_URL}/admin/orders/order/{pk}/change/
```

  - Відправка: `POST https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage`, JSON `{"chat_id": TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": True}`, `timeout=5`, без `parse_mode`. Немає токена або chat_id → `False` без HTTP. Виняток `requests`, статус ≠ 200 або `"ok": false` → `logger.warning(...)`, `False`. Успіх → `True`.

- [ ] **Step 1: Написати падаючі тести**

```python
def make_order(session, make_variant, **kw):
    v = make_variant(name="Стандарт", price=Decimal("780.00"), stock=5)
    cart = Cart(session); cart.add(v, 1)
    return place_order(cart, {**CUSTOMER, **kw}), v

def test_format_message(session, make_variant, settings):
    settings.SITE_URL = "https://shop.example"
    order, v = make_order(session, make_variant)
    assert format_order_message(order) == (
        f"🎣 Нове замовлення {order.number}\nСума: 780\u00a0грн\n\n"
        f"• {v.product.name} — Стандарт × 1 = 780\u00a0грн\n\n"
        "Клієнт: Іван Петренко\nТелефон: +380985936815\nНП: Вінниця, Відділення №1\nКоментар: —\n"
        f"Адмінка: https://shop.example/admin/orders/order/{order.pk}/change/"
    )

@responses.activate
def test_not_configured_returns_false_without_http(session, make_variant):
    order, _ = make_order(session, make_variant)
    assert notify_new_order(order) is False and len(responses.calls) == 0

@responses.activate
def test_success(session, make_variant, settings):
    settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID = "T", "42"
    responses.post("https://api.telegram.org/botT/sendMessage", json={"ok": True})
    order, _ = make_order(session, make_variant)
    assert notify_new_order(order) is True
    assert json.loads(responses.calls[0].request.body)["chat_id"] == "42"

@responses.activate
@pytest.mark.parametrize("kwargs", [{"status": 500, "json": {"ok": False}}, {"body": requests.ConnectionError("x")}])
def test_failure_returns_false(session, make_variant, settings, kwargs):
    settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID = "T", "42"
    responses.post("https://api.telegram.org/botT/sendMessage", **kwargs)
    order, _ = make_order(session, make_variant)
    assert notify_new_order(order) is False

def test_place_order_notifies_on_commit(session, make_variant, monkeypatch, django_capture_on_commit_callbacks):
    sent = []
    monkeypatch.setattr(telegram, "notify_new_order", lambda o: sent.append(o.pk) or True)
    with django_capture_on_commit_callbacks(execute=True):
        order, _ = make_order(session, make_variant)
    assert sent == [order.pk]
```

- [ ] **Step 2: Переконатися, що падають** → FAIL
- [ ] **Step 3: Реалізувати `notify/telegram.py`, підключити `on_commit` у `place_order`**
- [ ] **Step 4: Перевірити** — `.venv/Scripts/python -m pytest -v` → усі PASS
- [ ] **Step 5: Commit** — `feat: Telegram order notifications`

---

### Task 9: Оформлення замовлення і сторінка «Дякуємо»

**Files:**
- Create: `orders/{forms,views,urls}.py`, `orders/templates/orders/{checkout,thanks}.html`, `static/js/checkout.js`, `tests/test_checkout.py`
- Modify: `config/urls.py` (`path("", include("orders.urls"))` перед `catalog`)

**Interfaces:**
- Consumes: `place_order`, `EmptyCartError`, `OutOfStockError`, `normalize_phone` (Task 6); `novaposhta.is_enabled()` (Task 7); `Cart` (Task 3).
- Produces:
  - `CheckoutForm(forms.Form)`: `customer_name` (≤100, обов'язкове), `phone` (обов'язкове; `clean_phone` → `normalize_phone`, помилка «Введіть номер у форматі +380XXXXXXXXX»), `np_city_name` (≤120, обов'язкове), `np_city_ref` (hidden, необов'язкове), `np_warehouse_name` (≤200, обов'язкове), `np_warehouse_ref` (hidden, необов'язкове), `comment` (Textarea, ≤500, необов'язкове). Оплата — лише текст «Накладений платіж», не поле.
  - URL-и (namespace `orders`): `checkout` GET/POST `/checkout/`; `thanks` GET `/order/<number>/thanks/`. Ключ сесії `"last_order_number"`.
  - Поведінка: GET/POST з порожнім кошиком → 302 `/cart/` + `messages.info("Кошик порожній")` (так само обробляється `EmptyCartError`). Невалідна форма → 200 з помилками, значення збережені. Успіх → `session["last_order_number"] = order.number`, 302 на `thanks`. `OutOfStockError` → 200, над формою по рядку на проблему: `«{name}: залишилось {available} шт.»` або `«{name}: немає в наявності»` (коли 0). `thanks` рендериться, лише якщо `number == session["last_order_number"]`, інакше 404; показує номер, позиції, суму, НП і «Ми зателефонуємо для підтвердження замовлення».
  - Шаблон: якщо `is_enabled()` — поле міста з `hx-get="/delivery/cities/"` `hx-trigger="input changed delay:300ms"` `hx-target="#np-city-results"`, поле відділення з `hx-get="/delivery/warehouses/"` (`hx-include` прихованого `np_city_ref`) у `#np-warehouse-results`; інакше — звичайні текстові поля без `hx-get`. `checkout.js` (підключається лише з автокомплітом): клік на `.np-option` у `#np-city-results` заповнює `np_city_name`/`np_city_ref`, очищує відділення і підтягує список відділень (`htmx.ajax`); клік у `#np-warehouse-results` заповнює `np_warehouse_name`/`np_warehouse_ref`.
  - Кнопка «Оформити замовлення» в `_cart_body.html` (Task 4) вже веде на `/checkout/`.

- [ ] **Step 1: Написати падаючі тести**

```python
from tests.data import FORM

def add(client, v, qty=1):
    client.post("/cart/add/", {"variant_id": v.pk, "quantity": qty})

def test_empty_cart_redirects(client):
    r = client.get("/checkout/")
    assert r.status_code == 302 and r["Location"] == "/cart/"

def test_valid_post_creates_order(client, variant):
    add(client, variant)
    r = client.post("/checkout/", FORM)
    order = Order.objects.get()
    assert r["Location"] == f"/order/{order.number}/thanks/" and order.phone == "+380985936815"
    assert order.number in client.get(r["Location"]).content.decode()

def test_invalid_phone_keeps_values(client, variant):
    add(client, variant)
    html = client.post("/checkout/", {**FORM, "phone": "123"}).content.decode()
    assert "+380XXXXXXXXX" in html and 'value="Іван Петренко"' in html and Order.objects.count() == 0

def test_out_of_stock_message(client, make_variant):
    v = make_variant(stock=5); add(client, v, 3); v.stock = 1; v.save()
    r = client.post("/checkout/", FORM)
    assert r.status_code == 200 and "залишилось 1 шт." in r.content.decode() and Order.objects.count() == 0

def test_double_submit_single_order(client, variant):
    add(client, variant)
    client.post("/checkout/", FORM)
    r = client.post("/checkout/", FORM)
    assert Order.objects.count() == 1 and r["Location"] == "/cart/"

def test_thanks_hidden_from_other_sessions(client, variant):
    add(client, variant); url = client.post("/checkout/", FORM)["Location"]
    assert Client().get(url).status_code == 404

def test_plain_inputs_without_np_key(client, variant):
    add(client, variant)
    html = client.get("/checkout/").content.decode()
    assert 'name="np_city_name"' in html and 'hx-get="/delivery/cities/"' not in html

def test_autocomplete_with_np_key(client, variant, settings):
    settings.NOVA_POSHTA_API_KEY = "k"; add(client, variant)
    assert 'hx-get="/delivery/cities/"' in client.get("/checkout/").content.decode()
```

- [ ] **Step 2: Переконатися, що падають** → FAIL
- [ ] **Step 3: Реалізувати форму, views, urls, шаблони, `checkout.js`**
- [ ] **Step 4: Перевірити** — `.venv/Scripts/python -m pytest -v` → усі PASS
- [ ] **Step 5: Commit** — `feat: checkout flow and thank-you page`

---

### Task 10: Адмінка замовлень і роль «Менеджер»

**Files:**
- Create: `orders/admin.py`, `orders/management/__init__.py`, `orders/management/commands/{__init__,setup_roles}.py`, `tests/test_orders_admin.py`

**Interfaces:**
- Consumes: `Order`, `OrderItem`, `cancel_order` (Task 6).
- Produces:
  - `OrderAdmin`: `list_display` (number, created_at, customer_name, phone, сума через `uah`, status), `list_filter` (status, created_at), `search_fields` (number, phone, customer_name); редагуються лише `status` і `ttn`, решта — readonly; `has_add_permission → False`; `OrderItemInline` — readonly, `extra=0`, без додавання й видалення.
  - Дії: «Підтвердити» (лише `new` → `confirmed`), «Позначити відправленими» (усі, крім `cancelled`, → `shipped`), «Скасувати» (`cancel_order` для кожного).
  - `save_model`: якщо `status` змінено на `cancelled` — зберегти решту полів зі старим статусом, потім `cancel_order(obj)`. `get_readonly_fields`: для скасованого замовлення `status` теж readonly.
  - `manage.py setup_roles` — ідемпотентно створює групу «Менеджер» з правами рівно: `catalog.{add,change,delete,view}_{category,product,productimage,variant}`, `orders.view_order`, `orders.change_order`, `orders.view_orderitem`.

- [ ] **Step 1: Написати падаючі тести**

```python
def placed(session, make_variant, stock=10, qty=3):
    v = make_variant(stock=stock); cart = Cart(session); cart.add(v, qty)
    return place_order(cart, CUSTOMER), v

def test_admin_pages_load(admin_client, session, make_variant):
    order, _ = placed(session, make_variant)
    assert admin_client.get("/admin/orders/order/").status_code == 200
    assert admin_client.get(f"/admin/orders/order/{order.pk}/change/").status_code == 200

def test_confirm_action_only_new(admin_client, session, make_variant):
    a, _ = placed(session, make_variant); b, _ = placed(session, make_variant)
    Order.objects.filter(pk=b.pk).update(status="shipped")
    admin_client.post("/admin/orders/order/", {"action": "confirm_orders", "_selected_action": [a.pk, b.pk]})
    assert Order.objects.get(pk=a.pk).status == "confirmed" and Order.objects.get(pk=b.pk).status == "shipped"

def test_cancel_via_change_form_restores_stock_once(admin_client, session, make_variant):
    order, v = placed(session, make_variant)
    url = f"/admin/orders/order/{order.pk}/change/"
    post = {"status": "cancelled", "ttn": "", "items-TOTAL_FORMS": 1, "items-INITIAL_FORMS": 1,
            "items-MIN_NUM_FORMS": 0, "items-MAX_NUM_FORMS": 1000,
            "items-0-id": order.items.get().pk, "items-0-order": order.pk}
    admin_client.post(url, post); admin_client.post(url, {**post, "status": "new"})
    v.refresh_from_db(); order.refresh_from_db()
    assert v.stock == 10 and order.status == "cancelled"

def test_setup_roles_idempotent():
    call_command("setup_roles"); call_command("setup_roles")
    g = Group.objects.get(name="Менеджер")
    assert {p.codename for p in g.permissions.all()} == {
        *(f"{a}_{m}" for a in ("add", "change", "delete", "view") for m in ("category", "product", "productimage", "variant")),
        "view_order", "change_order", "view_orderitem"}

def test_manager_can_see_orders_not_users(client, django_user_model):
    call_command("setup_roles")
    u = django_user_model.objects.create_user("m", password="pw-test-123", is_staff=True)
    u.groups.add(Group.objects.get(name="Менеджер")); client.force_login(u)
    assert client.get("/admin/orders/order/").status_code == 200
    assert client.get("/admin/auth/user/").status_code == 403
```

(Назва дії `confirm_orders` — ім'я методу в `OrderAdmin`; інші: `mark_shipped`, `cancel_orders`.)

- [ ] **Step 2: Переконатися, що падають** → FAIL
- [ ] **Step 3: Реалізувати `orders/admin.py` і `setup_roles`**
- [ ] **Step 4: Перевірити** — `.venv/Scripts/python -m pytest -v` → усі PASS
- [ ] **Step 5: Commit** — `feat: orders admin and manager role`

---

### Task 11: Початкові дані REMESH (seed)

**Files:**
- Create: `catalog/seed_data.py`, `catalog/management/__init__.py`, `catalog/management/commands/{__init__,seed_remesh}.py`, `catalog/seed_images/.gitkeep`, `tests/test_seed.py`

**Interfaces:**
- Consumes: моделі каталогу (Task 2).
- Produces:
  - `catalog.seed_data.CATEGORIES: list[dict]` (`slug`, `name`, `position`) і `PRODUCTS: list[dict]` (`slug`, `category` (slug), `name`, `description`, `images: list[str]` — імена файлів у `catalog/seed_images/`, `variants: list[dict]` з `sku`, `name`, `price: Decimal | None`, `stock`).
  - Команда читає дані як `seed_data.CATEGORIES` / `seed_data.PRODUCTS` у момент виклику (`from catalog import seed_data`), щоб тести могли їх підміняти.
  - `manage.py seed_remesh` — **лише створює**: категорія за `slug`, товар за `slug`, варіант за `sku`, фото — лише разом зі створенням товару; існуючі записи не змінює. Варіант з `price=None` не створюється, у stdout: `Ціну не задано: {sku} — пропущено`. Відсутній файл фото → `Фото не знайдено: {file} — пропущено`. Підсумок: `Створено: категорій {n}, товарів {n}, варіантів {n}`.

- [ ] **Step 1: Зібрати дані (лише читання, Chrome «Browser 2»)**

Прочитати підписи постів @remesh_lures: `DeweoGvIpDF`, `DeweRHio58t`, `DdqgJ-TCPeL`, `Dds3iVViH9k`, `DeOgR2LIHq1`, reels `Deq1peGIiDw`, `DewdfCAoZU1`, а також повні (не обрізані) підписи `DewfkC7ouwP` і `DewfQgPobyQ` — шукати ціну. Заповнити `seed_data.py` (стартові 4 товари — таблиця §10 спеки; категорії `prymanky` «Силіконові приманки», `orhanaizery-meiho` «Органайзери MEIHO»; slug-и й sku — лише `[a-z0-9-]` / `[A-Z0-9-]`; `stock=10` для демо). Невідомі ціни — `None`.

- [ ] **Step 2: Показати користувачу таблицю товарів і цін; отримати підтвердження/ціни.** Фото з Instagram завантажувати лише після явного дозволу користувача; без дозволу `images=[]`.

- [ ] **Step 3: Написати падаючі тести**

```python
SMALL = dict(
    CATEGORIES=[{"slug": "c1", "name": "Кат", "position": 1}],
    PRODUCTS=[{"slug": "p1", "category": "c1", "name": "Товар", "description": "", "images": ["missing.jpg"],
               "variants": [{"sku": "S1", "name": "A", "price": Decimal("100.00"), "stock": 10},
                            {"sku": "S2", "name": "B", "price": None, "stock": 10}]}],
)

def run(monkeypatch):
    for k, v in SMALL.items(): monkeypatch.setattr(seed_data, k, v)
    out = io.StringIO(); call_command("seed_remesh", stdout=out); return out.getvalue()

def test_seed_creates_and_reports(monkeypatch):
    out = run(monkeypatch)
    assert Variant.objects.get(sku="S1").price == Decimal("100.00")
    assert not Variant.objects.filter(sku="S2").exists()
    assert "Ціну не задано: S2 — пропущено" in out and "Фото не знайдено: missing.jpg — пропущено" in out

def test_rerun_keeps_manager_edits_and_no_duplicates(monkeypatch):
    run(monkeypatch)
    Variant.objects.filter(sku="S1").update(price=Decimal("150.00"), stock=2)
    run(monkeypatch)
    v = Variant.objects.get(sku="S1")
    assert (v.price, v.stock) == (Decimal("150.00"), 2) and Product.objects.count() == 1

def test_real_seed_data_is_consistent():
    cats = {c["slug"] for c in seed_data.CATEGORIES}
    skus = [v["sku"] for p in seed_data.PRODUCTS for v in p["variants"]]
    assert len(skus) == len(set(skus))
    for p in seed_data.PRODUCTS:
        assert p["category"] in cats and re.fullmatch(r"[a-z0-9-]+", p["slug"])
```

- [ ] **Step 4: Переконатися, що падають** → FAIL
- [ ] **Step 5: Реалізувати `seed_remesh`** (фото копіюються через `default_storage.save(f"products/{file}", File(...))`)
- [ ] **Step 6: Перевірити** — `.venv/Scripts/python -m pytest -v` → усі PASS; `.venv/Scripts/python manage.py migrate && .venv/Scripts/python manage.py seed_remesh` → підсумок без помилок
- [ ] **Step 7: Commit** — `feat: REMESH seed data command`

---

### Task 12: Наскрізний тест, готовність до деплою, README

**Files:**
- Create: `tests/test_e2e.py`, `build.sh`, `render.yaml`, `README.md`, `.claude/launch.json`
- Modify: `config/settings.py` (безпека при `HTTPS=1`)

**Interfaces:**
- Consumes: усе вище.
- Produces:
  - При `HTTPS == "1"`: `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`, `SECURE_SSL_REDIRECT = True`, `SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]`, `SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True`, `SECURE_HSTS_SECONDS = 3600`.
  - `build.sh`: `pip install -r requirements.txt` → `collectstatic --noinput` → `migrate --noinput` → `setup_roles` → `seed_remesh` (`set -o errexit`).
  - `render.yaml`: один web-сервіс, `runtime: python`, `buildCommand: ./build.sh`, `startCommand: gunicorn config.wsgi --log-file -`, `healthCheckPath: /healthz/`; env: `PYTHON_VERSION=3.14.5`, `SECRET_KEY` (`generateValue: true`), `DEBUG=0`, `HTTPS=1`, `SERVE_MEDIA=1`, `ALLOWED_HOSTS=.onrender.com`, `CSRF_TRUSTED_ORIGINS=https://*.onrender.com`; `DATABASE_URL`, `SITE_URL`, `NOVA_POSHTA_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — `sync: false`.
  - `README.md`: локальний запуск (venv, `.env` з `.env.example`, `migrate`, `setup_roles`, `seed_remesh`, `createsuperuser`, `runserver`), тести, деплой на Render + Neon (кроки, які робить користувач: акаунти, `DATABASE_URL` з Neon, токен бота через @BotFather і `chat_id`, ключ API НП з кабінету НП).
  - `.claude/launch.json`: конфігурація `remesh-shop` — `.venv/Scripts/python manage.py runserver 8000`, порт 8000.

- [ ] **Step 1: Написати падаючий наскрізний тест**

```python
def test_full_purchase_flow(client, make_product, make_variant, monkeypatch, django_capture_on_commit_callbacks):
    p = make_product(name="CHUCHUNDRA 2.2″", slug="chuchundra-2-2")
    v = make_variant(product=p, name="LOX UV", price=Decimal("120.00"), stock=5)
    sent = []
    monkeypatch.setattr(telegram, "notify_new_order", lambda o: sent.append(o.number) or True)

    assert "/p/chuchundra-2-2/" in client.get("/").content.decode()
    assert "LOX UV" in client.get("/p/chuchundra-2-2/").content.decode()
    client.post("/cart/add/", {"variant_id": v.pk, "quantity": 2}, HTTP_HX_REQUEST="true")
    assert "240\u00a0грн" in client.get("/cart/").content.decode()
    assert client.get("/checkout/").status_code == 200
    with django_capture_on_commit_callbacks(execute=True):
        r = client.post("/checkout/", FORM)
    order = Order.objects.get()
    assert "Дякуємо" in client.get(r["Location"]).content.decode()
    assert sent == [order.number]
    v.refresh_from_db(); assert v.stock == 3
```

(`FORM` — з `tests/data.py`.)

- [ ] **Step 2: Запустити** — `.venv/Scripts/python -m pytest tests/test_e2e.py -v`. Очікування: PASS (усі частини вже є); якщо FAIL — виправити відповідну частину, не тест.
- [ ] **Step 3: Додати налаштування безпеки, `build.sh`, `render.yaml`, `README.md`, `.claude/launch.json`**
- [ ] **Step 4: Перевірити деплой-конфіг**

Run: `DEBUG=0 HTTPS=1 ALLOWED_HOSTS=example.com SECRET_KEY=$(.venv/Scripts/python -c "import secrets;print(secrets.token_urlsafe(50))") .venv/Scripts/python manage.py check --deploy`
Expected: без помилок (`ERRORS`); допустиме лише попередження `security.W021` (HSTS preload).

- [ ] **Step 5: Повний прогін** — `.venv/Scripts/python -m pytest -v` → усі PASS
- [ ] **Step 6: Ручна перевірка у вбудованому браузері** — `preview_start {name: "remesh-shop"}`, ширина mobile (375×812): каталог → товар → «В кошик» (лічильник оновився без перезавантаження) → кошик → оформлення → «Дякуємо»; замовлення видно в `/admin/`. Скріншот для користувача.
- [ ] **Step 7: Commit** — `chore: e2e test, deploy config and README`

---

**Після плану (не код):** деплой робить користувач зі своїми акаунтами (README); пітч — спека §12: Claude готує текст для Direct @remesh.fishing_team зі скріншотами, надсилання — лише після явного підтвердження користувача.
