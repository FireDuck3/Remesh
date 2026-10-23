import pytest

from orders.phone import normalize_phone


@pytest.mark.parametrize(
    "raw", ["0985936815", "+380985936815", "380985936815", "+38 (098) 593-68-15", "098 593 68 15"]
)
def test_normalize_valid(raw):
    assert normalize_phone(raw) == "+380985936815"


@pytest.mark.parametrize("raw", ["", "12345", "+44985936815", "09859368150", "abc"])
def test_normalize_invalid(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)
