from django.contrib.auth.models import Group, Permission
from django.core.management import call_command

from cart.cart import Cart
from orders.models import Order
from orders.services import cancel_order, place_order
from tests.data import CUSTOMER

LIST_URL = "/admin/orders/order/"


def placed(session, make_variant, stock=10, qty=3):
    v = make_variant(stock=stock)
    cart = Cart(session)
    cart.add(v, qty)
    return place_order(cart, CUSTOMER), v


def change_url(order):
    return f"{LIST_URL}{order.pk}/change/"


def change_post(order, **fields):
    """A valid change-form POST for ``order`` (the readonly inline still sends its management data)."""
    return {
        "status": order.status,
        "ttn": "",
        "items-TOTAL_FORMS": 1,
        "items-INITIAL_FORMS": 1,
        "items-MIN_NUM_FORMS": 0,
        "items-MAX_NUM_FORMS": 1000,
        "items-0-id": order.items.get().pk,
        "items-0-order": order.pk,
        **fields,
    }


def test_admin_pages_load(admin_client, session, make_variant):
    order, _ = placed(session, make_variant)
    assert admin_client.get("/admin/orders/order/").status_code == 200
    assert admin_client.get(f"/admin/orders/order/{order.pk}/change/").status_code == 200


def test_money_is_shown_in_uah(admin_client, session, make_variant):
    order, _ = placed(session, make_variant)  # 3 x 100.00
    assert "300 грн" in admin_client.get(LIST_URL).content.decode()
    page = admin_client.get(change_url(order)).content.decode()
    assert "100 грн" in page and "300 грн" in page


def test_confirm_action_only_new(admin_client, session, make_variant):
    a, _ = placed(session, make_variant)
    b, _ = placed(session, make_variant)
    Order.objects.filter(pk=b.pk).update(status="shipped")
    admin_client.post("/admin/orders/order/", {"action": "confirm_orders", "_selected_action": [a.pk, b.pk]})
    assert Order.objects.get(pk=a.pk).status == "confirmed" and Order.objects.get(pk=b.pk).status == "shipped"


def test_mark_shipped_skips_cancelled(admin_client, session, make_variant):
    a, _ = placed(session, make_variant)
    b, _ = placed(session, make_variant)
    cancel_order(b)
    admin_client.post(LIST_URL, {"action": "mark_shipped", "_selected_action": [a.pk, b.pk]})
    assert Order.objects.get(pk=a.pk).status == "shipped"
    assert Order.objects.get(pk=b.pk).status == "cancelled"


def test_cancel_action_restores_stock_once(admin_client, session, make_variant):
    order, v = placed(session, make_variant)
    data = {"action": "cancel_orders", "_selected_action": [order.pk]}
    response = admin_client.post(LIST_URL, data, follow=True)
    assert [str(m) for m in response.context["messages"]] == ["Скасовано замовлень: 1"]
    admin_client.post(LIST_URL, data)
    v.refresh_from_db()
    assert v.stock == 10 and Order.objects.get(pk=order.pk).status == "cancelled"


def test_cancel_via_change_form_restores_stock_once(admin_client, session, make_variant):
    order, v = placed(session, make_variant)
    url = f"/admin/orders/order/{order.pk}/change/"
    post = {"status": "cancelled", "ttn": "", "items-TOTAL_FORMS": 1, "items-INITIAL_FORMS": 1,
            "items-MIN_NUM_FORMS": 0, "items-MAX_NUM_FORMS": 1000,
            "items-0-id": order.items.get().pk, "items-0-order": order.pk}
    admin_client.post(url, post)
    admin_client.post(url, {**post, "status": "new"})
    v.refresh_from_db()
    order.refresh_from_db()
    assert v.stock == 10 and order.status == "cancelled"


def test_cancel_via_change_form_keeps_ttn(admin_client, session, make_variant):
    order, v = placed(session, make_variant)
    response = admin_client.post(change_url(order), change_post(order, status="cancelled", ttn="20450000000001"))
    assert response.status_code == 302
    v.refresh_from_db()
    order.refresh_from_db()
    assert (order.status, order.ttn, v.stock) == ("cancelled", "20450000000001", 10)


def test_change_form_saves_status_and_ttn_only(admin_client, session, make_variant):
    order, v = placed(session, make_variant)
    post = change_post(order, status="confirmed", ttn="20450000000002", customer_name="Хтось інший", total="1.00")
    assert admin_client.post(change_url(order), post).status_code == 302
    order.refresh_from_db()
    v.refresh_from_db()
    assert (order.status, order.ttn, v.stock) == ("confirmed", "20450000000002", 7)
    assert order.customer_name == CUSTOMER["customer_name"] and order.total == 3 * v.price


def test_status_is_readonly_once_cancelled(admin_client, session, make_variant):
    order, _ = placed(session, make_variant)
    response = admin_client.get(change_url(order))
    assert {"status", "ttn"} <= set(response.context["adminform"].form.fields)

    cancel_order(order)
    response = admin_client.get(change_url(order))
    assert set(response.context["adminform"].form.fields) == {"ttn"}
    admin_client.post(change_url(order), change_post(order, status="new", ttn="20450000000003"))
    order.refresh_from_db()
    assert (order.status, order.ttn) == ("cancelled", "20450000000003")


def test_orders_cannot_be_added(admin_client):
    assert admin_client.get(f"{LIST_URL}add/").status_code == 403
    assert admin_client.post(f"{LIST_URL}add/", {"customer_name": "X"}).status_code == 403
    assert Order.objects.count() == 0


def test_setup_roles_idempotent():
    call_command("setup_roles")
    call_command("setup_roles")
    g = Group.objects.get(name="Менеджер")
    assert {p.codename for p in g.permissions.all()} == {
        *(f"{a}_{m}" for a in ("add", "change", "delete", "view") for m in ("category", "product", "productimage", "variant")),
        "view_order", "change_order", "view_orderitem"}


def test_setup_roles_resets_extra_permissions():
    call_command("setup_roles")
    group = Group.objects.get(name="Менеджер")
    group.permissions.add(Permission.objects.get(content_type__app_label="orders", codename="delete_order"))
    call_command("setup_roles")
    assert not group.permissions.filter(codename="delete_order").exists()
    assert Group.objects.filter(name="Менеджер").count() == 1


def test_manager_can_see_orders_not_users(client, django_user_model):
    call_command("setup_roles")
    u = django_user_model.objects.create_user("m", password="pw-test-123", is_staff=True)
    u.groups.add(Group.objects.get(name="Менеджер"))
    client.force_login(u)
    assert client.get("/admin/orders/order/").status_code == 200
    assert client.get("/admin/auth/user/").status_code == 403


def test_manager_edits_orders_but_cannot_add_or_delete(client, django_user_model, session, make_variant):
    call_command("setup_roles")
    u = django_user_model.objects.create_user("m", password="pw-test-123", is_staff=True)
    u.groups.add(Group.objects.get(name="Менеджер"))
    client.force_login(u)
    order, _ = placed(session, make_variant)
    assert client.get(change_url(order)).status_code == 200
    assert client.post(change_url(order), change_post(order, ttn="20450000000004")).status_code == 302
    assert Order.objects.get(pk=order.pk).ttn == "20450000000004"
    assert client.get(f"{LIST_URL}add/").status_code == 403
    assert client.post(f"{LIST_URL}{order.pk}/delete/", {"post": "yes"}).status_code == 403
    assert Order.objects.filter(pk=order.pk).exists()


def test_orders_cannot_be_deleted_even_by_a_superuser(admin_client, session, make_variant):
    """Cancelling is the supported path (it restocks); deleting would skip that."""
    order, variant = placed(session, make_variant, stock=10, qty=3)
    delete_url = f"{LIST_URL}{order.pk}/delete/"
    assert admin_client.get(delete_url).status_code == 403
    assert admin_client.post(delete_url, {"post": "yes"}).status_code == 403
    admin_client.post(LIST_URL, {"action": "delete_selected", "_selected_action": [order.pk], "post": "yes"})
    assert Order.objects.filter(pk=order.pk).exists()
    assert "delete_selected" not in dict(admin_client.get(LIST_URL).context["action_form"].fields["action"].choices)
