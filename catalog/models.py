from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Min


class Category(models.Model):
    name = models.CharField("Назва", max_length=100)
    slug = models.SlugField("Адреса (slug)", unique=True)
    position = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["position", "name"]
        verbose_name = "Категорія"
        verbose_name_plural = "Категорії"

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def visible(self):
        """Products shown in the storefront: active, with at least one active variant."""
        return self.filter(is_active=True, variants__is_active=True).distinct()


class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products", verbose_name="Категорія"
    )
    name = models.CharField("Назва", max_length=200)
    slug = models.SlugField("Адреса (slug)", max_length=200, unique=True)
    description = models.TextField("Опис", blank=True)
    is_active = models.BooleanField("Активний", default=True)
    created_at = models.DateTimeField("Створено", auto_now_add=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товари"

    def __str__(self):
        return self.name

    def active_variants(self):
        return self.variants.filter(is_active=True).order_by("id")

    def min_price(self):
        """Lowest price among active variants, or None when there are none."""
        return self.active_variants().aggregate(lowest=Min("price"))["lowest"]

    def main_image(self):
        return self.images.order_by("position", "id").first()


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images", verbose_name="Товар"
    )
    image = models.ImageField("Фото", upload_to="products/")
    position = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = "Фото товару"
        verbose_name_plural = "Фото товарів"

    def __str__(self):
        return f"{self.product.name} — фото {self.position}"


class Variant(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants", verbose_name="Товар"
    )
    name = models.CharField("Назва варіанта", max_length=100)
    sku = models.CharField("Артикул", max_length=50, unique=True)
    price = models.DecimalField(
        "Ціна, грн", max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    stock = models.PositiveIntegerField("Залишок", default=0)
    is_active = models.BooleanField("Активний", default=True)

    class Meta:
        verbose_name = "Варіант"
        verbose_name_plural = "Варіанти"

    def __str__(self):
        return f"{self.product.name} — {self.name}"

    @property
    def in_stock(self):
        return self.is_active and self.product.is_active and self.stock > 0
