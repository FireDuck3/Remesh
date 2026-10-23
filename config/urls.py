from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.static import serve


def healthz(request):
    return HttpResponse("ok")


urlpatterns = [
    path("healthz/", healthz),
    path("admin/", admin.site.urls),
    path("cart/", include("cart.urls")),
]

if settings.DEBUG or settings.SERVE_MEDIA:
    # Uploaded product photos: served by Django itself (small shop, files live on the app's disk).
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]
