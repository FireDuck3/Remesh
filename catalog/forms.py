from django import forms
from django.db.models import F, IntegerField, Value
from django.db.models.functions import Greatest

from .models import Variant


def refresh_stock(variant):
    """After a save with a stock expression the attribute still holds the expression; read the number back."""
    if variant.pk and not isinstance(variant.stock, int):
        variant.refresh_from_db(fields=["stock"])


class VariantForm(forms.ModelForm):
    """Variant form for the admin (the product page's inline and the variants list).

    Stock moves while a manager has a page open: buyers keep ordering. So the form remembers the stock it
    was rendered with (``show_hidden_initial``) and saves only what the manager changed, as a difference
    applied to the current database value, never as an absolute number from a stale page.
    """

    class Meta:
        model = Variant
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["stock"].show_hidden_initial = True

    def _rendered_stock(self):
        """The stock this form was rendered with, or None when the POST does not carry it."""
        bound = self["stock"]
        try:
            return self.fields["stock"].to_python(self.data.get(bound.html_initial_name))
        except forms.ValidationError:
            return None

    def _stock_for_save(self):
        """What to write into ``stock`` of an existing variant: an expression on the row's current value."""
        if "stock" not in self.changed_data:
            return F("stock")  # untouched: whatever the database holds now stays
        rendered = self._rendered_stock()
        if rendered is None:
            return self.cleaned_data["stock"]  # not our page: plain "set"
        delta = self.cleaned_data["stock"] - rendered
        return Greatest(F("stock") + delta, Value(0), output_field=IntegerField())

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.pk:
            instance.stock = self._stock_for_save()
        if commit:
            instance.save()
            refresh_stock(instance)
            self._save_m2m()
        return instance
