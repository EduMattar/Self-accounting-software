from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from .models import CategorizedTransaction, TransactionRecord
from .utils import format_decimal


@dataclass
class LedgerEntry:
    transaction_id: str
    booking_date: date
    description: str
    payee: str
    counterparty_account: str
    amount: Decimal
    currency: str
    debit_account: str
    credit_account: str
    bank_account: str
    source_file: str
    source_line: int
    unique_hash: str


class UniversalLedger:
    """Handles the persistent CSV ledger that stores all normalized transactions."""

    headers = [
        "transaction_id",
        "date",
        "description",
        "payee",
        "counterparty_account",
        "amount",
        "currency",
        "debit_account",
        "credit_account",
        "bank_account",
        "source_file",
        "source_line",
        "unique_hash",
    ]

    def __init__(self, ledger_path: Path):
        self._path = ledger_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            with self._path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(self.headers)
        else:
            self._ensure_headers()

    def _ensure_headers(self) -> None:
        with self._path.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            try:
                existing_header = next(reader)
            except StopIteration:
                existing_header = []

        if not existing_header:
            with self._path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(self.headers)
            return

        if existing_header == self.headers:
            return

        needs_upgrade = "counterparty_account" not in existing_header
        if not needs_upgrade:
            return

        with self._path.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)

        with self._path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(self.headers)
            for row in rows:
                writer.writerow(
                    [
                        row.get("transaction_id", ""),
                        row.get("date", ""),
                        row.get("description", ""),
                        row.get("payee", ""),
                        row.get("counterparty_account", ""),
                        row.get("amount", ""),
                        row.get("currency", ""),
                        row.get("debit_account", ""),
                        row.get("credit_account", ""),
                        row.get("bank_account", ""),
                        row.get("source_file", ""),
                        row.get("source_line", ""),
                        row.get("unique_hash", ""),
                    ]
                )

    def load_hashes(self) -> Dict[str, LedgerEntry]:
        entries: Dict[str, LedgerEntry] = {}
        with self._path.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                entries[row["unique_hash"]] = LedgerEntry(
                    transaction_id=row["transaction_id"],
                    booking_date=date.fromisoformat(row["date"]),
                    description=row["description"],
                    payee=row["payee"],
                    counterparty_account=row.get("counterparty_account", ""),
                    amount=Decimal(row["amount"]),
                    currency=row["currency"],
                    debit_account=row["debit_account"],
                    credit_account=row["credit_account"],
                    bank_account=row["bank_account"],
                    source_file=row["source_file"],
                    source_line=int(row["source_line"]),
                    unique_hash=row["unique_hash"],
                )
        return entries

    def append(self, transactions: Iterable[CategorizedTransaction]) -> List[LedgerEntry]:
        existing_entries = self.load_hashes()
        new_entries: List[LedgerEntry] = []
        with self._path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            for tx in transactions:
                if tx.unique_hash in existing_entries:
                    continue
                entry = LedgerEntry(
                    transaction_id=tx.transaction_id,
                    booking_date=tx.booking_date,
                    description=tx.description,
                    payee=tx.payee,
                    counterparty_account=tx.counterparty_account or "",
                    amount=tx.amount,
                    currency=tx.currency or "",
                    debit_account=tx.debit_account,
                    credit_account=tx.credit_account,
                    bank_account=tx.bank_account or "",
                    source_file=str(tx.source_file),
                    source_line=tx.source_line,
                    unique_hash=tx.unique_hash,
                )
                writer.writerow(
                    [
                        entry.transaction_id,
                        entry.booking_date.isoformat(),
                        entry.description,
                        entry.payee,
                        entry.counterparty_account,
                        format_decimal(entry.amount),
                        entry.currency,
                        entry.debit_account,
                        entry.credit_account,
                        entry.bank_account,
                        entry.source_file,
                        entry.source_line,
                        entry.unique_hash,
                    ]
                )
                new_entries.append(entry)
        return new_entries

    def next_sequence_numbers(self) -> Dict[Tuple[str, Tuple[int, int]], int]:
        """Returns the highest sequence number per (account, month, year)."""
        sequences: Dict[Tuple[str, Tuple[int, int]], int] = defaultdict(int)
        with self._path.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                account_prefix = row["transaction_id"][:2]
                month = int(row["transaction_id"][2:4])
                year = int(row["transaction_id"][4:6])
                seq = int(row["transaction_id"][6:])
                key = (account_prefix, (month, year))
                sequences[key] = max(sequences[key], seq)
        return sequences

    def load_all(self) -> List[LedgerEntry]:
        with self._path.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            return [
                LedgerEntry(
                    transaction_id=row["transaction_id"],
                    booking_date=date.fromisoformat(row["date"]),
                    description=row["description"],
                    payee=row["payee"],
                    counterparty_account=row.get("counterparty_account", ""),
                    amount=Decimal(row["amount"]),
                    currency=row["currency"],
                    debit_account=row["debit_account"],
                    credit_account=row["credit_account"],
                    bank_account=row["bank_account"],
                    source_file=row["source_file"],
                    source_line=int(row["source_line"]),
                    unique_hash=row["unique_hash"],
                )
                for row in reader
            ]


def compute_unique_hash(
    record: TransactionRecord,
    debit_account: str,
    credit_account: str,
    amount_override: Decimal | None = None,
) -> str:
    amount_value = amount_override if amount_override is not None else record.amount
    payload = "|".join(
        [
            record.booking_date.isoformat(),
            record.payee.strip(),
            record.description.strip(),
            (record.counterparty_account or "").strip(),
            f"{amount_value.normalize()}",
            (record.currency or "").upper(),
            debit_account,
            credit_account,
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()
