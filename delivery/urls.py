from django.urls import path

from . import views

app_name = "delivery"

urlpatterns = [
    path("cities/", views.cities, name="cities"),
    path("warehouses/", views.warehouses, name="warehouses"),
]
