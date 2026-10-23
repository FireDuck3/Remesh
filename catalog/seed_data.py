"""Початковий каталог REMESH для команди `manage.py seed_remesh`.

Команда лише створює записи: існуючі категорії (за slug), товари (за slug) і варіанти
(за sku) не змінюються, тож правки менеджера в адмінці не перезаписуються.

`price=None` означає «ціну ще не підтверджено»: такий варіант команда пропускає,
і товар, у якого всі варіанти без ціни, не показується в магазині.
`images` — імена файлів у `catalog/seed_images/` (поки порожньо).
"""

from decimal import Decimal

CATEGORIES = [
    {"slug": "prymanky", "name": "Силіконові приманки", "position": 1},
    {"slug": "orhanaizery-meiho", "name": "Органайзери MEIHO", "position": 2},
]

PRODUCTS = [
    {
        "slug": "chuchundra-2-2",
        "category": "prymanky",
        "name": "CHUCHUNDRA 2.2″",
        "description": (
            "Силіконова приманка CHUCHUNDRA 2.2″ (55 мм), у пакованні 6 штук. "
            "UV-активні кольори. "
            "Зроблено в Україні й перевірено українськими спортсменами-рибалками."
        ),
        "images": [],
        "variants": [
            {"sku": "RM-CHU22-LOX", "name": "LOX UV", "price": None, "stock": 10},
            {"sku": "RM-CHU22-JUNEBUG", "name": "JUNE BUG UV", "price": None, "stock": 10},
            {"sku": "RM-CHU22-ACIDGREEN", "name": "ACID GREEN UV", "price": None, "stock": 10},
            {"sku": "RM-CHU22-WHITE", "name": "WHITE UV", "price": None, "stock": 10},
            {"sku": "RM-CHU22-PATRIOT", "name": "PATRIOT UV", "price": None, "stock": 10},
        ],
    },
    {
        "slug": "korobka-voblery-6",
        "category": "orhanaizery-meiho",
        "name": "Коробка для воблерів на 6 відділів (MEIHO 7070/7070N)",
        "description": (
            "Коробка на 6 відділів для воблерів, яка підходить до скриньки MEIHO 7070 / 7070N. "
            "Розмір 190 × 116 × 30 мм. "
            "Надрукована на 3D-принтері, чорна, у фірмовому стилі REMESH."
        ),
        "images": [],
        "variants": [
            {"sku": "RM-BOX6-BLK", "name": "Чорна", "price": Decimal("780.00"), "stock": 10},
        ],
    },
    {
        "slug": "korobka-voblery-3",
        "category": "orhanaizery-meiho",
        "name": "Коробка для воблерів на 3 відділи (MEIHO 7070/7070N)",
        "description": (
            "Коробка на 3 просторі відділи для великих воблерів, підходить до MEIHO 7070 / 7070N. "
            "Розмір 190 × 116 × 30 мм. "
            "Надрукована на 3D-принтері, чорного кольору."
        ),
        "images": [],
        "variants": [
            {"sku": "RM-BOX3-BLK", "name": "Чорна", "price": None, "stock": 10},
        ],
    },
    {
        "slug": "vkladky-blesni-vs7070",
        "category": "orhanaizery-meiho",
        "name": "Вкладки для блешень MEIHO VS-7070 (3 шт.)",
        "description": (
            "Вкладки зі слотами для підвішування блешень у коробці MEIHO VS-7070. "
            "У наборі 3 штуки, розмір 120 × 190 мм. "
            "Зручні для ловлі форелі на платниках."
        ),
        "images": [],
        "variants": [
            {"sku": "RM-TAB3-VS7070", "name": "Стандарт", "price": None, "stock": 10},
        ],
    },
]
