from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import Account


class AccountCatalog:
    """Loads and provides access to the chart of accounts."""

    def __init__(self, catalog_path: Path):
        self._path = catalog_path
        self._accounts: Dict[str, Account] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            raise FileNotFoundError(
                f"Account catalog not found at {self._path}. Create the file before running the app."
            )
        with self._path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        accounts: Dict[str, Account] = {}
        for entry in data:
            number = str(entry["number"]).strip()
            name = entry["name"].strip()
            account_type = entry.get("type", "").strip()
            accounts[number] = Account(number=number, name=name, type=account_type)
        self._accounts = accounts

    def list_accounts(self) -> List[Account]:
        return sorted(self._accounts.values(), key=lambda acc: acc.number)

    def get(self, account_number: str) -> Optional[Account]:
        return self._accounts.get(str(account_number))

    def labels(self) -> Iterable[str]:
        for account in self.list_accounts():
            yield account.display_label()

    def as_choice_pairs(self) -> List[tuple[str, str]]:
        return [(account.number, account.display_label()) for account in self.list_accounts()]
