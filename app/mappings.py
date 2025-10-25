from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional


class PayeeMappingManager:
    """Stores and retrieves mappings between payees and ledger accounts."""

    def __init__(self, storage_path: Path):
        self._path = storage_path
        self._mappings: Dict[str, Dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            # normalize keys to ensure consistent casing/spacing
            self._mappings = {key.strip(): value for key, value in data.items()}
        else:
            self._mappings = {}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as fh:
            json.dump(self._mappings, fh, indent=2, sort_keys=True)

    def get(self, payee: str) -> Optional[Dict[str, str]]:
        return self._mappings.get(payee.strip())

    def set(self, payee: str, debit_account: str, credit_account: str) -> None:
        self._mappings[payee.strip()] = {
            "debit_account": str(debit_account),
            "credit_account": str(credit_account),
        }
        self.save()

    def all_payees(self) -> Dict[str, Dict[str, str]]:
        return dict(self._mappings)
