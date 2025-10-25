from __future__ import annotations

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, Tuple


def normalize_currency(value: str) -> str:
    return value.strip().upper()


def ensure_two_digit_account(account_number: str) -> str:
    digits = re.sub(r"\D", "", str(account_number))
    if not digits:
        return "00"
    if len(digits) >= 2:
        return digits[-2:]
    return digits.zfill(2)


def next_transaction_id(
    account_number: str,
    booking_date: date,
    sequence_tracker: Dict[Tuple[str, Tuple[int, int]], int],
) -> str:
    prefix = ensure_two_digit_account(account_number)
    month = booking_date.month
    year = booking_date.year % 100
    key = (prefix, (month, year))
    current = sequence_tracker.get(key, 0) + 1
    sequence_tracker[key] = current
    return f"{prefix}{month:02d}{year:02d}{current:03d}"


def to_positive_decimal(value: Decimal) -> Decimal:
    return value.copy_abs()


def format_decimal(value: Decimal, places: int = 2) -> str:
    quant = Decimal(1).scaleb(-places)
    return format(value.quantize(quant, rounding=ROUND_HALF_UP), "f")
