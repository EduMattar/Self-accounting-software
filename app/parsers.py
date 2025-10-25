from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

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
            rows = list(reader)

        header_names = list(headers.values())
        column_map = {key: self._find_column(headers, aliases) for key, aliases in self.COLUMN_ALIASES.items()}
        self._auto_detect_columns(rows, header_names, column_map)

        records: List[TransactionRecord] = []
        missing_currency = False
        missing_bank_account = False

        for line_number, row in enumerate(rows, start=2):
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

    def _auto_detect_columns(
        self,
        rows: Sequence[Dict[str, str]],
        header_names: Iterable[str],
        column_map: Dict[str, Optional[str]],
    ) -> None:
        """Fill in missing column matches using heuristics over the data sample."""

        available = set(header_names)
        assigned = {column for column in column_map.values() if column}

        if column_map.get("date") is None:
            detected_date = self._detect_date_column(rows, available - assigned)
            if detected_date:
                column_map["date"] = detected_date
                assigned.add(detected_date)

        if column_map.get("amount") is None and not (
            column_map.get("debit") and column_map.get("credit")
        ):
            amount, debit, credit = self._detect_amount_columns(rows, available - assigned)
            if amount:
                column_map["amount"] = amount
                assigned.add(amount)
            if debit:
                column_map["debit"] = debit
                assigned.add(debit)
            if credit:
                column_map["credit"] = credit
                assigned.add(credit)

        if column_map.get("description") is None:
            description_column = self._detect_text_column(rows, available - assigned)
            if description_column:
                column_map["description"] = description_column
                assigned.add(description_column)

        payee_column = column_map.get("payee")
        if payee_column:
            if self._column_has_single_value(rows, payee_column):
                payee_column = None
        if payee_column is None:
            detected_payee = self._detect_payee_column(rows, available, assigned)
            if detected_payee:
                column_map["payee"] = detected_payee
                assigned.add(detected_payee)
            elif column_map.get("description"):
                column_map["payee"] = column_map["description"]
        elif column_map.get("payee") and column_map.get("payee") not in assigned:
            assigned.add(column_map["payee"])

        if column_map.get("currency") is None:
            currency_column = self._detect_currency_column(rows, available - assigned)
            if currency_column:
                column_map["currency"] = currency_column
                assigned.add(currency_column)

        if column_map.get("bank_account") is None:
            bank_column = self._detect_bank_account_column(rows, available - assigned)
            if bank_column:
                column_map["bank_account"] = bank_column

    def _column_has_single_value(self, rows: Sequence[Dict[str, str]], column: str) -> bool:
        unique = set()
        for row in rows:
            value = row.get(column)
            if value is None:
                continue
            text = value.strip()
            if not text:
                continue
            unique.add(text.lower())
            if len(unique) > 1:
                return False
        return True

    def _detect_payee_column(
        self,
        rows: Sequence[Dict[str, str]],
        available: Iterable[str],
        assigned: set[str],
    ) -> Optional[str]:
        best_column: Optional[str] = None
        best_score = 0.0
        for column in available:
            if column in assigned:
                continue
            unique_values = []
            letter_count = 0
            seen = set()
            for row in rows:
                raw_value = row.get(column)
                if raw_value is None:
                    continue
                value = raw_value.strip()
                if not value:
                    continue
                key = value.lower()
                if key in seen:
                    continue
                seen.add(key)
                unique_values.append(value)
                if any(char.isalpha() for char in value):
                    letter_count += 1
            if len(unique_values) < 2:
                continue
            text_ratio = letter_count / len(unique_values)
            if text_ratio < 0.3:
                continue
            score = len(unique_values) + text_ratio
            if score > best_score:
                best_score = score
                best_column = column
        return best_column

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
        parsed = self._try_parse_date_value(raw_value)
        if parsed is None:
            raise ValueError(f"Unsupported date format: {raw_value}")
        return parsed

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
        decimal_value = self._try_parse_decimal(value)
        if decimal_value is None:
            raise ValueError(f"Unable to parse amount: {value}")
        return decimal_value

    def _detect_date_column(
        self, rows: Sequence[Dict[str, str]], available_columns: Iterable[str]
    ) -> Optional[str]:
        best_column: Optional[str] = None
        best_score = 0
        for column in available_columns:
            score = 0
            for raw in self._iter_column_values(rows, column, limit=200):
                if self._try_parse_date_value(raw) is not None:
                    score += 1
            if score > best_score:
                best_score = score
                best_column = column
        if best_score >= 3:
            return best_column
        return None

    def _detect_amount_columns(
        self, rows: Sequence[Dict[str, str]], available_columns: Iterable[str]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        numeric_candidates: Dict[str, Dict[str, float]] = {}
        column_values_cache: Dict[str, List[Optional[Decimal]]] = {}
        for column in available_columns:
            decimals: List[Optional[Decimal]] = []
            numeric_count = 0
            positive = 0
            negative = 0
            nonzero = 0
            for raw in self._iter_column_values(rows, column, limit=400):
                decimal = self._try_parse_decimal(raw)
                decimals.append(decimal)
                if decimal is None:
                    continue
                numeric_count += 1
                if decimal > 0:
                    positive += 1
                    nonzero += 1
                elif decimal < 0:
                    negative += 1
                    nonzero += 1
                elif decimal == 0:
                    pass
            total_samples = len(decimals)
            if total_samples == 0:
                continue
            numeric_ratio = numeric_count / total_samples
            if numeric_ratio >= 0.6 and nonzero > 0:
                numeric_candidates[column] = {
                    "numeric_ratio": numeric_ratio,
                    "positive": positive,
                    "negative": negative,
                    "nonzero": nonzero,
                }
                column_values_cache[column] = decimals

        amount_column = None
        for column, stats in numeric_candidates.items():
            if stats["positive"] > 0 and stats["negative"] > 0:
                amount_column = column
                break

        if amount_column:
            return amount_column, None, None

        if len(numeric_candidates) < 2:
            return None, None, None

        best_pair: Optional[Tuple[str, str]] = None
        lowest_overlap = float("inf")
        sample_size_for_best = 0
        candidate_columns = list(numeric_candidates.keys())
        for i in range(len(candidate_columns)):
            for j in range(i + 1, len(candidate_columns)):
                left = candidate_columns[i]
                right = candidate_columns[j]
                overlap = 0
                paired_samples = zip(
                    column_values_cache[left],
                    column_values_cache[right],
                )
                sample_count = 0
                for left_value, right_value in paired_samples:
                    sample_count += 1
                    left_nonzero = left_value is not None and left_value != 0
                    right_nonzero = right_value is not None and right_value != 0
                    if left_nonzero and right_nonzero:
                        overlap += 1
                if overlap < lowest_overlap:
                    lowest_overlap = overlap
                    best_pair = (left, right)
                    sample_size_for_best = sample_count

        if best_pair and lowest_overlap <= max(1, sample_size_for_best * 0.1):
            debit, credit = best_pair
            # Prefer to treat the column with more positive values as credit (inflow)
            left_stats = numeric_candidates[debit]
            right_stats = numeric_candidates[credit]
            if left_stats["positive"] < right_stats["positive"]:
                debit, credit = credit, debit
            return None, debit, credit

        return None, None, None

    def _detect_text_column(
        self, rows: Sequence[Dict[str, str]], available_columns: Iterable[str]
    ) -> Optional[str]:
        best_column = None
        best_length = 0
        for column in available_columns:
            total_length = 0
            non_empty = 0
            for value in self._iter_column_values(rows, column, limit=200):
                if not value:
                    continue
                total_length += len(value)
                non_empty += 1
            if non_empty == 0:
                continue
            avg_length = total_length / non_empty
            if avg_length > best_length:
                best_length = avg_length
                best_column = column
        return best_column

    def _detect_currency_column(
        self, rows: Sequence[Dict[str, str]], available_columns: Iterable[str]
    ) -> Optional[str]:
        currency_candidates = {"eur", "usd", "gbp", "brl", "chf", "cad"}
        for column in available_columns:
            values = list(self._iter_column_values(rows, column, limit=100))
            normalized = {value.strip().lower() for value in values if value}
            if not normalized:
                continue
            if normalized.issubset(currency_candidates) or all(len(value) <= 3 for value in normalized):
                return column
        return None

    def _detect_bank_account_column(
        self, rows: Sequence[Dict[str, str]], available_columns: Iterable[str]
    ) -> Optional[str]:
        for column in available_columns:
            unique_values = set()
            for value in self._iter_column_values(rows, column, limit=200):
                if value:
                    unique_values.add(value)
            if 1 < len(unique_values) <= 10:
                return column
        return None

    def _iter_column_values(
        self, rows: Sequence[Dict[str, str]], column: str, limit: int = 200
    ) -> Iterable[Optional[str]]:
        for index, row in enumerate(rows):
            if index >= limit:
                break
            value = row.get(column)
            yield value.strip() if isinstance(value, str) else value

    def _try_parse_date_value(self, raw_value: Optional[str]):
        if raw_value is None:
            return None
        value = raw_value.strip()
        if not value:
            return None
        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None

    def _try_parse_decimal(self, value: Optional[str]) -> Optional[Decimal]:
        if value is None:
            return None
        cleaned = str(value).strip()
        if cleaned == "":
            return Decimal("0")
        cleaned = (
            cleaned.replace("€", "")
            .replace("$", "")
            .replace("GBP", "")
            .replace("BRL", "")
            .replace("R$", "")
            .replace("USD", "")
            .replace("EUR", "")
            .replace("£", "")
            .replace("'", "")
        )
        cleaned = cleaned.replace("+", "").replace("−", "-")
        cleaned = cleaned.replace(" ", "")
        negative = False
        if cleaned.startswith("(") and cleaned.endswith(")"):
            negative = True
            cleaned = cleaned[1:-1]
        if cleaned.startswith("-"):
            negative = True
            cleaned = cleaned[1:]
        cleaned = cleaned.replace("\u00a0", "")
        if cleaned in {"", "-"}:
            return Decimal("0")
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        try:
            decimal_value = Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return None
        if negative:
            decimal_value = -decimal_value
        return decimal_value
