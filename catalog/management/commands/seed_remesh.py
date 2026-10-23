from pathlib import Path

from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog import seed_data
from catalog.models import Category, Product, ProductImage, Variant

SEED_IMAGES_DIR = Path(__file__).resolve().parents[2] / "seed_images"


class Command(BaseCommand):
    help = "Створює початкові категорії, товари й варіанти REMESH. Існуючі записи не змінює."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Нічого не створювати, якщо в каталозі вже є хоч один товар (для запуску при кожному деплої).",
        )

    def handle(self, *args, **options):
        if options["if_empty"] and Product.objects.exists():
            self._restore_images()  # the disk may have been wiped by the deploy, the catalog was not
            self.stdout.write("Каталог не порожній — пропущено")
            return

        # Read at call time so tests can monkeypatch seed_data.
        categories, products = seed_data.CATEGORIES, seed_data.PRODUCTS
        created = {"categories": 0, "products": 0, "variants": 0}

        with transaction.atomic():
            by_slug = {}
            for data in categories:
                category, was_created = Category.objects.get_or_create(
                    slug=data["slug"],
                    defaults={"name": data["name"], "position": data["position"]},
                )
                by_slug[data["slug"]] = category
                created["categories"] += was_created

            for data in products:
                category = by_slug.get(data["category"]) or Category.objects.filter(slug=data["category"]).first()
                if category is None:
                    raise CommandError(f"Невідома категорія «{data['category']}» у товарі {data['slug']}")
                product, was_created = Product.objects.get_or_create(
                    slug=data["slug"],
                    defaults={
                        "category": category,
                        "name": data["name"],
                        "description": data.get("description", ""),
                    },
                )
                if was_created:
                    created["products"] += 1
                    self._add_images(product, data.get("images", []))
                for variant in data["variants"]:
                    created["variants"] += self._add_variant(product, variant)

        self._restore_images()  # photos of products that already existed
        self.stdout.write(
            f"Створено: категорій {created['categories']}, "
            f"товарів {created['products']}, варіантів {created['variants']}"
        )

    def _add_images(self, product, files):
        position = 0
        for file in files:
            if not (SEED_IMAGES_DIR / file).is_file():
                self.stdout.write(f"Фото не знайдено: {file} — пропущено")
                continue
            self._ensure_image(file)
            ProductImage.objects.create(product=product, image=f"products/{file}", position=position)
            position += 1

    def _restore_images(self):
        """Put back every seed photo that is missing from the media storage (never touches the database)."""
        restored = 0
        for data in seed_data.PRODUCTS:
            for file in data.get("images", []):
                if (SEED_IMAGES_DIR / file).is_file():
                    restored += self._ensure_image(file)
        if restored:
            self.stdout.write(f"Відновлено фото: {restored}")

    def _ensure_image(self, file):
        """Copy a repo photo to `products/<file>` unless that file is already there. Returns 1 if copied."""
        name = f"products/{file}"
        if default_storage.exists(name):
            return 0
        with (SEED_IMAGES_DIR / file).open("rb") as handle:
            default_storage.save(name, File(handle))
        return 1

    def _add_variant(self, product, data):
        if Variant.objects.filter(sku=data["sku"]).exists():
            return 0
        if data["price"] is None:
            self.stdout.write(f"Ціну не задано: {data['sku']} — пропущено")
            return 0
        Variant.objects.create(
            product=product,
            sku=data["sku"],
            name=data["name"],
            price=data["price"],
            stock=data["stock"],
        )
        return 1
