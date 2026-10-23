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

    def handle(self, *args, **options):
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

        self.stdout.write(
            f"Створено: категорій {created['categories']}, "
            f"товарів {created['products']}, варіантів {created['variants']}"
        )

    def _add_images(self, product, files):
        position = 0
        for file in files:
            path = SEED_IMAGES_DIR / file
            if not path.is_file():
                self.stdout.write(f"Фото не знайдено: {file} — пропущено")
                continue
            with path.open("rb") as handle:
                name = default_storage.save(f"products/{file}", File(handle))
            ProductImage.objects.create(product=product, image=name, position=position)
            position += 1

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
