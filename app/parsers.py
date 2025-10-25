from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

from .models import TransactionRecord


@dataclass
class ParseResult:
    records: List[TransactionRecord]
    missing_currencies: bool
    missing_bank_accounts: bool


class StatementParser:
    """Parses CSV statements from supported banks and normalizes them."""

    COLUMN_ALIASES: Dict[str, List[str]] = {
        "date": [
            "date",
            "transaction date",
            "booking date",
            "value date",
            "datum",
        ],
        "description": [
            "description",
            "details",
            "narrative",
            "text",
            "memo",
            "payment reference",
            "reference",
            "description 1",
        ],
        "amount": [
            "amount",
            "transaction amount",
            "value",
            "amt",
        ],
        "currency": [
            "currency",
            "curr",
            "currency code",
        ],
        "debit": [
            "debit",
            "withdrawal",
            "outflow",
            "debit amount",
        ],
        "credit": [
            "credit",
            "deposit",
            "inflow",
            "credit amount",
        ],
        "payee": [
            "payee",
            "counterparty",
            "beneficiary",
            "partner name",
            "account name",
            "merchant",
        ],
        "bank_account": [
            "account",
            "account number",
            "iban",
            "my account",
        ],
    }

    DATE_FORMATS = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%Y.%m.%d",
    ]

    def parse(self, path: Path) -> ParseResult:
        if not path.exists():
            raise FileNotFoundError(f"Statement file not found: {path}")

        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            sample = fh.read(4096)
            fh.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            fh.seek(0)
            reader = csv.DictReader(fh, dialect=dialect)
            if reader.fieldnames is None:
                raise ValueError("CSV file is missing headers.")
            headers = {name.lower().strip(): name for name in reader.fieldnames}

            column_map = {key: self._find_column(headers, aliases) for key, aliases in self.COLUMN_ALIASES.items()}

            records: List[TransactionRecord] = []
            missing_currency = False
            missing_bank_account = False

            for line_number, row in enumerate(reader, start=2):
                if not any(value.strip() for value in row.values() if isinstance(value, str)):
                    continue

                date_value = self._parse_date(row, column_map)
                description = self._read_cell(row, column_map["description"]) or ""
                payee = self._read_cell(row, column_map["payee"]) or description
                amount = self._parse_amount(row, column_map)
                currency = self._read_cell(row, column_map["currency"])
                bank_account = self._read_cell(row, column_map["bank_account"])

                if currency is None:
                    missing_currency = True
                if bank_account is None:
                    missing_bank_account = True

                records.append(
                    TransactionRecord(
                        source_file=path,
                        source_line=line_number,
                        booking_date=date_value,
                        description=description,
                        amount=amount,
                        currency=currency,
                        payee=payee,
                        bank_account=bank_account,
                    )
                )

        return ParseResult(records=records, missing_currencies=missing_currency, missing_bank_accounts=missing_bank_account)

    def _find_column(self, headers: Dict[str, str], aliases: List[str]) -> Optional[str]:
        for alias in aliases:
            if alias in headers:
                return headers[alias]
        return None

    def _read_cell(self, row: Dict[str, str], column: Optional[str]) -> Optional[str]:
        if column is None:
            return None
        value = row.get(column)
        if value is None:
            return None
        value = value.strip()
        return value or None

    def _parse_date(self, row: Dict[str, str], column_map: Dict[str, Optional[str]]):
        column = column_map.get("date")
        if column is None:
            raise ValueError("Unable to determine the date column in the statement.")
        raw_value = row[column].strip()
        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(raw_value, fmt).date()
            except ValueError:
                continue
        # Try ISO date time strings
        try:
            return datetime.fromisoformat(raw_value).date()
        except ValueError as exc:
            raise ValueError(f"Unsupported date format: {raw_value}") from exc

    def _parse_amount(self, row: Dict[str, str], column_map: Dict[str, Optional[str]]) -> Decimal:
        amount_column = column_map.get("amount")
        if amount_column:
            raw = row[amount_column]
            return self._to_decimal(raw)

        debit_column = column_map.get("debit")
        credit_column = column_map.get("credit")
        if debit_column or credit_column:
            debit_value = self._to_decimal(row.get(debit_column, "0")) if debit_column else Decimal("0")
            credit_value = self._to_decimal(row.get(credit_column, "0")) if credit_column else Decimal("0")
            return debit_value - credit_value

        raise ValueError("Unable to determine amount information in the statement.")

    def _to_decimal(self, value: Optional[str]) -> Decimal:
        if value is None:
            return Decimal("0")
        cleaned = value.strip().replace("€", "").replace("$", "")
        cleaned = cleaned.replace("GBP", "").replace("BRL", "").replace("R$", "")
        cleaned = cleaned.replace("USD", "").replace("EUR", "").replace("£", "")
        cleaned = cleaned.replace("+", "").replace("−", "-")
        cleaned = cleaned.replace(" ", "")
        if cleaned in {"", "-"}:
            return Decimal("0")
        negative = False
        if cleaned.startswith("(") and cleaned.endswith(")"):
            negative = True
            cleaned = cleaned[1:-1]
        if cleaned.startswith("-"):
            negative = True
            cleaned = cleaned[1:]
        if cleaned == "":
            return Decimal("0")
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        try:
            value = Decimal(cleaned)
            return -value if negative else value
        except Exception as exc:
            raise ValueError(f"Unable to parse amount: {value}") from exc
