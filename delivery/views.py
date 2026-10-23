"""HTMX autocomplete fragments for the checkout's Nova Poshta city and warehouse pickers."""

from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import novaposhta


@require_GET
def cities(request):
    try:
        found = novaposhta.search_cities(request.GET.get("q", ""))
    except novaposhta.NovaPoshtaError:
        return render(request, "delivery/_cities.html", {"error": True})
    return render(request, "delivery/_cities.html", {"cities": found})


@require_GET
def warehouses(request):
    try:
        found = novaposhta.list_warehouses(request.GET.get("city_ref", ""), request.GET.get("q", ""))
    except novaposhta.NovaPoshtaError:
        return render(request, "delivery/_warehouses.html", {"error": True})
    return render(request, "delivery/_warehouses.html", {"warehouses": found})
