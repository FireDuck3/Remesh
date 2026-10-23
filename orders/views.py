"""Checkout and the thank-you page. Stock and the order itself are handled by ``orders.services``."""

from decimal import Decimal

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from cart.cart import Cart
from delivery import novaposhta

from .forms import CheckoutForm
from .models import Order
from .services import EmptyCartError, OutOfStockError, place_order

LAST_ORDER_KEY = "last_order_number"  # lets the buyer (and only the buyer's session) open the thanks page


def _empty_cart(request):
    messages.info(request, "Кошик порожній")
    return redirect("cart:detail")


def _page(request, form, lines, problems=()):
    return render(
        request,
        "orders/checkout.html",
        {
            "form": form,
            "lines": lines,
            "total": sum((line.line_total for line in lines), Decimal("0.00")),
            "cart_count": sum(line.quantity for line in lines),  # saves the header counter a second query
            "problems": problems,
            "np_enabled": novaposhta.is_enabled(),
        },
    )


@require_http_methods(["GET", "HEAD", "POST"])
def checkout(request):
    cart = Cart(request.session)
    lines = cart.lines()
    if not lines:
        return _empty_cart(request)

    if request.method != "POST":
        return _page(request, CheckoutForm(), lines)

    form = CheckoutForm(request.POST)
    if not form.is_valid():
        return _page(request, form, lines)
    try:
        order = place_order(cart, form.cleaned_data)
    except EmptyCartError:  # emptied in another tab since the lines were read
        return _empty_cart(request)
    except OutOfStockError as error:  # place_order has already lowered the cart to what is available
        return _page(request, form, cart.lines(), error.problems)
    request.session[LAST_ORDER_KEY] = order.number
    return redirect("orders:thanks", number=order.number)


@require_safe
def thanks(request, number):
    if request.session.get(LAST_ORDER_KEY) != number:
        raise Http404
    order = get_object_or_404(Order.objects.prefetch_related("items"), number=number)
    return render(request, "orders/thanks.html", {"order": order})
