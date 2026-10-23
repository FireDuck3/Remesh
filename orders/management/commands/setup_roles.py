from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

GROUP_NAME = "Менеджер"

CATALOG_MODELS = ("category", "product", "productimage", "variant")
PERMISSIONS = [
    *(("catalog", f"{action}_{model}") for model in CATALOG_MODELS for action in ("add", "change", "delete", "view")),
    ("orders", "view_order"),
    ("orders", "change_order"),
    ("orders", "view_orderitem"),
]


class Command(BaseCommand):
    help = f"Створює (або вирівнює) групу «{GROUP_NAME}»: каталог повністю, замовлення — перегляд і зміна."

    def handle(self, *args, **options):
        permissions = []
        for app_label, codename in PERMISSIONS:
            try:
                permissions.append(Permission.objects.get(content_type__app_label=app_label, codename=codename))
            except Permission.DoesNotExist:
                raise CommandError(f"Немає права {app_label}.{codename} — спершу виконайте migrate.")

        with transaction.atomic():
            group, created = Group.objects.get_or_create(name=GROUP_NAME)
            group.permissions.set(permissions)  # exactly this set: stray extra rights are removed

        action = "створено" if created else "оновлено"
        self.stdout.write(self.style.SUCCESS(f"Група «{GROUP_NAME}» {action}: {len(permissions)} прав."))
