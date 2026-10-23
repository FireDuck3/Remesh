"""Shared constants for tests (customer data, raw checkout form payload)."""

CUSTOMER = dict(
    customer_name="Іван Петренко",
    phone="+380985936815",
    np_city_ref="",
    np_city_name="Вінниця",
    np_warehouse_ref="",
    np_warehouse_name="Відділення №1",
    comment="",
)

# Raw checkout form data (Tasks 9, 12): same as CUSTOMER, but the phone is as a human types it.
FORM = {**CUSTOMER, "phone": "098 593 68 15"}
