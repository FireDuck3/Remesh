from django.utils.functional import SimpleLazyObject

from .cart import Cart


def cart_count(request):
    """Expose ``cart_count`` (items in the cart) to every template, for the header counter.

    Lazy, so a page that never prints it costs no query, and it is evaluated at render time, after the view
    has changed the cart.
    """
    return {"cart_count": SimpleLazyObject(lambda: Cart(request.session).count())}
