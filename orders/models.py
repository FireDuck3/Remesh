from django.db import models

from catalog.models import Variant


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Нове"
        CONFIRMED = "confirmed", "Підтверджене"
        SHIPPED = "shipped", "Відправлене"
        COMPLETED = "completed", "Виконане"
        CANCELLED = "cancelled", "Скасоване"

    class Payment(models.TextChoices):
        COD = "cod", "Накладений платіж"

    # NULL (not "") until the first save assigns it, so concurrent inserts never collide on the unique index.
    number = models.CharField("Номер", max_length=20, unique=True, null=True, blank=True)
    customer_name = models.CharField("Ім'я покупця", max_length=100)
    phone = models.CharField("Телефон", max_length=20)
    np_city_ref = models.CharField("Місто НП (ref)", max_length=100, blank=True)
    np_city_name = models.CharField("Місто", max_length=200)
    np_warehouse_ref = models.CharField("Відділення НП (ref)", max_length=100, blank=True)
    np_warehouse_name = models.CharField("Відділення / поштомат", max_length=255)
    comment = models.TextField("Коментар", blank=True)
    payment_method = models.CharField(
        "Оплата", max_length=10, choices=Payment.choices, default=Payment.COD
    )
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.NEW)
    ttn = models.CharField("ТТН", max_length=30, blank=True)
    total = models.DecimalField("Сума, грн", max_digits=10, decimal_places=2)
    created_at = models.DateTimeField("Створено", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Замовлення"
        verbose_name_plural = "Замовлення"

    def __str__(self):
        return self.number or "Нове замовлення"

    def save(self, *args, **kwargs):
        creating = self._state.adding
        super().save(*args, **kwargs)
        if creating and not self.number:
            self.number = f"RM-{self.pk:04d}"
            super().save(update_fields=["number"], using=kwargs.get("using"))


class OrderItem(models.Model):
    """A snapshot of what was bought: later price/name changes never touch old orders."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items", verbose_name="Замовлення"
    )
    variant = models.ForeignKey(
        Variant, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Варіант"
    )
    product_name = models.CharField("Товар", max_length=200)
    variant_name = models.CharField("Варіант", max_length=100)
    sku = models.CharField("Артикул", max_length=50)
    unit_price = models.DecimalField("Ціна, грн", max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField("Кількість")

    class Meta:
        verbose_name = "Позиція замовлення"
        verbose_name_plural = "Позиції замовлення"

    def __str__(self):
        return f"{self.product_name} — {self.variant_name} × {self.quantity}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity
