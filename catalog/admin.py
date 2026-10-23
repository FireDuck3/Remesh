from django.contrib import admin
from django.utils.html import format_html

from .forms import VariantForm, refresh_stock
from .models import Category, Product, ProductImage, Variant
from .templatetags.money import format_uah

admin.site.site_header = "REMESH — адмінка"


class VariantInline(admin.TabularInline):
    model = Variant
    form = VariantForm
    fields = ("name", "sku", "price", "stock", "is_active")
    extra = 1


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    fields = ("image", "position")
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "position")
    list_editable = ("position",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [VariantInline, ProductImageInline]
    list_display = ("thumbnail", "name", "category", "is_active", "price_from")
    list_filter = ("category", "is_active")
    list_select_related = ("category",)
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Фото")
    def thumbnail(self, obj):
        image = obj.main_image()
        if image is None:
            return "—"
        return format_html('<img src="{}" alt="" style="height: 40px; border-radius: 4px;">', image.image.url)

    @admin.display(description="Ціна від")
    def price_from(self, obj):
        price = obj.min_price()
        return "—" if price is None else format_uah(price)


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    form = VariantForm
    list_display = ("product", "name", "sku", "price", "stock", "is_active")
    list_editable = ("price", "stock", "is_active")
    list_select_related = ("product",)
    search_fields = ("sku", "name", "product__name")

    def get_changelist_form(self, request, **kwargs):
        kwargs.setdefault("form", VariantForm)
        return super().get_changelist_form(request, **kwargs)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        refresh_stock(obj)  # the list/change pages save with commit=False, so the form could not do it
