"""Ukrainian phone number normalisation."""

import re


def normalize_phone(raw: str) -> str:
    """Return ``+380XXXXXXXXX`` for a Ukrainian number typed in any common way.

    Everything but digits is dropped. Accepted: 12 digits starting with ``380`` or 10 digits starting
    with ``0``. Anything else raises ``ValueError``.
    """
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 12 and digits.startswith("380"):
        return f"+{digits}"
    if len(digits) == 10 and digits.startswith("0"):
        return f"+38{digits}"
    raise ValueError(f"Невірний номер телефону: {raw!r}")
