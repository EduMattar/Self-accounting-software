from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional


@dataclass
class TransactionRecord:
    """Represents a raw transaction read from a statement file."""

    source_file: Path
    source_line: int
    booking_date: date
    description: str
    amount: Decimal
    currency: Optional[str]
    payee: str
    bank_account: Optional[str]


@dataclass
class CategorizedTransaction(TransactionRecord):
    """Represents a transaction after assigning debit/credit accounts."""

    debit_account: str
    credit_account: str
    transaction_id: str
    unique_hash: str


@dataclass
class Account:
    number: str
    name: str
    type: str = ""

    def display_label(self) -> str:
        if self.type:
            return f"{self.number} - {self.name} ({self.type})"
        return f"{self.number} - {self.name}"
