"""One full customer journey through the real views: catalog -> product -> cart -> checkout -> thanks."""

from decimal import Decimal

from notify import telegram
from orders.models import Order
from tests.data import FORM


def test_full_purchase_flow(client, make_product, make_variant, monkeypatch, django_capture_on_commit_callbacks):
    p = make_product(name="CHUCHUNDRA 2.2″", slug="chuchundra-2-2")
    v = make_variant(product=p, name="LOX UV", price=Decimal("120.00"), stock=5)
    sent = []
    monkeypatch.setattr(telegram, "notify_new_order", lambda o: sent.append(o.number) or True)

    assert "/p/chuchundra-2-2/" in client.get("/").content.decode()
    assert "LOX UV" in client.get("/p/chuchundra-2-2/").content.decode()
    client.post("/cart/add/", {"variant_id": v.pk, "quantity": 2}, HTTP_HX_REQUEST="true")
    assert "240 грн" in client.get("/cart/").content.decode()
    assert client.get("/checkout/").status_code == 200
    with django_capture_on_commit_callbacks(execute=True):
        r = client.post("/checkout/", FORM)
    order = Order.objects.get()
    assert "Дякуємо" in client.get(r["Location"]).content.decode()
    assert sent == [order.number]
    v.refresh_from_db()
    assert v.stock == 3
