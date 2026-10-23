from .models import Category


def nav_categories(request):
    """Expose ``nav_categories`` (categories that have visible products) to every template, for the header menu.

    A lazy queryset: pages that never print the menu cost no query, and the menu itself costs exactly one.
    """
    return {
        "nav_categories": Category.objects.filter(
            products__is_active=True, products__variants__is_active=True
        ).distinct()
    }
