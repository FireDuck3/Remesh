"""Cart pages. Plain POSTs redirect back to the cart; HTMX POSTs get HTML fragments to swap in."""

import re
from decimal import Decimal

from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST, require_safe

from catalog.models import Variant

from .cart import Cart

# Optional minus sign and at most 18 ASCII digits: always fits a database integer, never raises on int().
INTEGER = re.compile(r"-?[0-9]{1,18}")


def _is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def _integer(request, field, default=None):
    """The POSTed ``field`` as an int, or None when it is malformed (or missing and has no ``default``)."""
    raw = request.POST.get(field)
    if raw is None:
        return default
    raw = raw.strip()
    return int(raw) if INTEGER.fullmatch(raw) else None


def _bad_request():
    return HttpResponseBadRequest("Некоректні дані")


def _cart_context(cart):
    """Template context for the cart body; one ``lines()`` query, totals derived from it."""
    lines = cart.lines()
    return {
        "lines": lines,
        "total": sum((line.line_total for line in lines), Decimal("0.00")),
        "cart_count": sum(line.quantity for line in lines),
    }


def _cart_changed(request, cart):
    """Response after update/remove: the refreshed cart body plus an out-of-band header counter for HTMX."""
    if not _is_htmx(request):
        return redirect("cart:detail")
    context = _cart_context(cart)
    body = render_to_string("cart/_cart_body.html", context, request)
    counter = render_to_string("cart/_counter.html", {**context, "oob": True}, request)
    return HttpResponse(body + counter)


@require_safe
def detail(request):
    return render(request, "cart/cart_detail.html", _cart_context(Cart(request.session)))


@require_POST
def add(request):
    variant_id = _integer(request, "variant_id")
    quantity = _integer(request, "quantity", default=1)
    if variant_id is None or quantity is None or quantity < 1:
        return _bad_request()
    variant = Variant.objects.select_related("product").filter(pk=variant_id).first()
    if variant is None:
        return _bad_request()
    if not variant.in_stock:
        return HttpResponse("Немає в наявності", status=409)
    Cart(request.session).add(variant, quantity)
    if not _is_htmx(request):
        return redirect("cart:detail")
    return render(request, "cart/_counter.html")  # cart_count comes from the context processor


@require_POST
def update(request):
    variant_id = _integer(request, "variant_id")
    quantity = _integer(request, "quantity")
    if variant_id is None or quantity is None or quantity < 0:
        return _bad_request()
    cart = Cart(request.session)
    cart.set(variant_id, quantity)  # 0, an unknown variant or an unavailable one removes the line
    return _cart_changed(request, cart)


@require_POST
def remove(request):
    variant_id = _integer(request, "variant_id")
    if variant_id is None:
        return _bad_request()
    cart = Cart(request.session)
    cart.remove(variant_id)  # idempotent: a stale page removing an already-gone line is not an error
    return _cart_changed(request, cart)
