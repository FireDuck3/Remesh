from django.contrib import admin, messages

from catalog.templatetags.money import format_uah

from .models import Order, OrderItem
from .services import cancel_order


class OrderItemInline(admin.TabularInline):
    """What was bought, as a snapshot: never added to, edited or deleted from the admin."""

    model = OrderItem
    fields = ("product_name", "variant_name", "sku", "unit_price_uah", "quantity", "line_total")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Ціна")
    def unit_price_uah(self, obj):
        return format_uah(obj.unit_price)

    @admin.display(description="Сума")
    def line_total(self, obj):
        return format_uah(obj.line_total)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ("number", "created_at", "customer_name", "phone", "total_uah", "status")
    list_filter = ("status", "created_at")
    search_fields = ("number", "phone", "customer_name")
    actions = ["confirm_orders", "mark_shipped", "cancel_orders"]

    fields = (
        "number",
        "created_at",
        "status",
        "ttn",
        "customer_name",
        "phone",
        "np_city_name",
        "np_warehouse_name",
        "comment",
        "payment_method",
        "total_uah",
        "np_city_ref",
        "np_warehouse_ref",
    )
    # Only status and ttn are editable; everything else comes from the customer and stays as placed.
    readonly_fields = (
        "number",
        "created_at",
        "customer_name",
        "phone",
        "np_city_name",
        "np_warehouse_name",
        "comment",
        "payment_method",
        "total_uah",
        "np_city_ref",
        "np_warehouse_ref",
    )

    @admin.display(description="Сума", ordering="total")
    def total_uah(self, obj):
        return format_uah(obj.total)

    def has_add_permission(self, request):
        return False  # orders only come from the storefront checkout

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and obj.status == Order.Status.CANCELLED:
            return (*self.readonly_fields, "status")  # a cancelled order is never reopened
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data and obj.status == Order.Status.CANCELLED:
            # Cancelling must restock, so it goes through cancel_order and never straight into the column.
            # Whatever else was edited (ttn) is saved first, without touching the stored status.
            obj.save(update_fields=[name for name in form.changed_data if name != "status"])
            cancel_order(obj)
        else:
            super().save_model(request, obj, form, change)

    @admin.action(description="Підтвердити", permissions=["change"])
    def confirm_orders(self, request, queryset):
        count = queryset.filter(status=Order.Status.NEW).update(status=Order.Status.CONFIRMED)
        self.message_user(request, f"Підтверджено замовлень: {count}", messages.SUCCESS)

    @admin.action(description="Позначити відправленими", permissions=["change"])
    def mark_shipped(self, request, queryset):
        count = queryset.exclude(status=Order.Status.CANCELLED).update(status=Order.Status.SHIPPED)
        self.message_user(request, f"Позначено відправленими: {count}", messages.SUCCESS)

    @admin.action(description="Скасувати", permissions=["change"])
    def cancel_orders(self, request, queryset):
        count = sum(cancel_order(order) for order in queryset)  # already-cancelled ones return False
        self.message_user(request, f"Скасовано замовлень: {count}", messages.SUCCESS)
