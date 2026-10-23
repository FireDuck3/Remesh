from django import forms

from .phone import normalize_phone


class CheckoutForm(forms.Form):
    """What the buyer fills in at checkout. Payment is always cash on delivery, so it is not a field.

    The length limits keep the manager's Telegram message (4096 characters at most) comfortably short; the
    two ``*_ref`` fields are filled by ``static/js/checkout.js`` when the buyer picks a Nova Poshta suggestion.
    """

    customer_name = forms.CharField(
        label="Ім'я та прізвище",
        max_length=100,
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    phone = forms.CharField(
        label="Телефон",
        widget=forms.TextInput(
            attrs={"type": "tel", "inputmode": "tel", "autocomplete": "tel", "placeholder": "+380 98 593 68 15"}
        ),
    )
    np_city_name = forms.CharField(label="Місто", max_length=120)
    np_city_ref = forms.CharField(max_length=100, required=False, widget=forms.HiddenInput)
    np_warehouse_name = forms.CharField(label="Відділення або поштомат Нової пошти", max_length=200)
    np_warehouse_ref = forms.CharField(max_length=100, required=False, widget=forms.HiddenInput)
    comment = forms.CharField(
        label="Коментар до замовлення",
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def clean_phone(self):
        try:
            return normalize_phone(self.cleaned_data["phone"])
        except ValueError:
            raise forms.ValidationError("Введіть номер у форматі +380XXXXXXXXX") from None
