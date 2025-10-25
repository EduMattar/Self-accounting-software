from __future__ import annotations

import csv
from pathlib import Path
from tkinter import (
    BOTH,
    LEFT,
    RIGHT,
    Button,
    Frame,
    Label,
    StringVar,
    Tk,
    filedialog,
    messagebox,
    simpledialog,
)
from tkinter import ttk
from typing import Dict, Iterable, List

from .accounts import AccountCatalog
from .journal import JournalBuilder
from .ledger import UniversalLedger, compute_unique_hash
from .mappings import PayeeMappingManager
from .models import CategorizedTransaction, TransactionRecord
from .parsers import StatementParser
from .utils import format_decimal, next_transaction_id, normalize_currency, to_positive_decimal

APP_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = APP_ROOT / "config"
DATA_DIR = APP_ROOT / "data"
OUTPUT_DIR = APP_ROOT / "output"


class AccountSelectionDialog(simpledialog.Dialog):
    def __init__(self, parent, payee: str, accounts: List[tuple[str, str]]):
        self.payee = payee
        self.accounts = accounts
        self.result: Dict[str, str] | None = None
        super().__init__(parent, title=f"Map accounts for {payee}")

    def body(self, master):
        Label(master, text=f"Select accounts for: {self.payee}").grid(row=0, column=0, columnspan=2, pady=(0, 10))

        Label(master, text="Debit account:").grid(row=1, column=0, sticky="w")
        Label(master, text="Credit account:").grid(row=2, column=0, sticky="w")

        self.debit_var = StringVar(master)
        self.credit_var = StringVar(master)

        values = [label for _, label in self.accounts]
        debit_combo = ttk.Combobox(
            master,
            textvariable=self.debit_var,
            width=40,
            values=values,
            state="readonly",
        )
        credit_combo = ttk.Combobox(
            master,
            textvariable=self.credit_var,
            width=40,
            values=values,
            state="readonly",
        )
        debit_combo.grid(row=1, column=1, padx=5, pady=2)
        credit_combo.grid(row=2, column=1, padx=5, pady=2)
        return debit_combo

    def validate(self):
        debit_label = self.debit_var.get()
        credit_label = self.credit_var.get()
        if not debit_label or not credit_label:
            messagebox.showerror("Missing data", "Please choose both debit and credit accounts.")
            return False
        return True

    def apply(self):
        debit_label = self.debit_var.get()
        credit_label = self.credit_var.get()
        reverse_lookup = {label: number for number, label in self.accounts}
        self.result = {
            "debit_account": reverse_lookup[debit_label],
            "credit_account": reverse_lookup[credit_label],
        }


class CategorizationApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Bank Statement Categorizer")

        self.catalog = AccountCatalog(CONFIG_DIR / "accounts.json")
        self.mappings = PayeeMappingManager(CONFIG_DIR / "payee_mappings.json")
        self.parser = StatementParser()
        self.ledger = UniversalLedger(DATA_DIR / "universal_transactions.csv")
        self.journal_builder = JournalBuilder(self.catalog)

        container = Frame(root, padx=20, pady=20)
        container.pack(fill=BOTH, expand=True)

        Label(container, text="Import bank statements and categorize transactions.").pack()

        button_frame = Frame(container, pady=10)
        button_frame.pack()

        Button(button_frame, text="Import statement", command=self.import_statement).pack(side=LEFT, padx=5)
        Button(button_frame, text="Quit", command=root.quit).pack(side=RIGHT, padx=5)

    def import_statement(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not file_path:
            return

        path = Path(file_path)
        try:
            parse_result = self.parser.parse(path)
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("Parsing error", str(exc))
            return

        records = parse_result.records
        if not records:
            messagebox.showinfo("No transactions", "The selected statement has no transactions to import.")
            return

        try:
            self._ensure_currency(records, parse_result.missing_currencies)
            self._ensure_bank_account(records, parse_result.missing_bank_accounts)
        except ValueError as exc:
            messagebox.showerror("Missing information", str(exc))
            return

        categorized = self._categorize_records(records)
        if not categorized:
            messagebox.showinfo("No new transactions", "All transactions already existed in the ledger.")
            return

        categorized_csv_path = OUTPUT_DIR / "categorized" / f"{path.stem}_categorized.csv"
        self._write_categorized_csv(categorized, categorized_csv_path)

        new_entries = self.ledger.append(categorized)
        all_entries = self.ledger.load_all()
        self.journal_builder.build(all_entries, OUTPUT_DIR / "journal.xlsx")

        messagebox.showinfo(
            "Import complete",
            (
                f"Processed {len(records)} transactions from {path.name}.\n"
                f"Added {len(new_entries)} new entries to the ledger.\n"
                f"Categorized CSV saved to {categorized_csv_path}."
            ),
        )

    def _ensure_currency(self, records: List[TransactionRecord], needs_prompt: bool) -> None:
        if not needs_prompt:
            for record in records:
                if record.currency:
                    record.currency = normalize_currency(record.currency)
            return

        default_currency = simpledialog.askstring(
            "Currency",
            "Currency column was missing. Enter the currency code for all transactions:",
        )
        if not default_currency:
            raise ValueError("Currency is required when the statement does not provide it.")
        normalized = normalize_currency(default_currency)
        for record in records:
            record.currency = normalized

    def _ensure_bank_account(self, records: List[TransactionRecord], needs_prompt: bool) -> None:
        if needs_prompt:
            bank_account = simpledialog.askstring(
                "Bank account",
                "Statement does not specify the originating bank account.\nEnter the account number for these transactions:",
            )
            if not bank_account:
                raise ValueError("Bank account number is required.")
            for record in records:
                record.bank_account = bank_account

    def _categorize_records(self, records: List[TransactionRecord]) -> List[CategorizedTransaction]:
        payees = sorted({record.payee for record in records})
        account_choices = self.catalog.as_choice_pairs()
        if not account_choices:
            messagebox.showerror(
                "Missing accounts",
                "No accounts found in config/accounts.json. Add at least one account before importing statements.",
            )
            return []
        missing_payees = [payee for payee in payees if self.mappings.get(payee) is None]

        for payee in missing_payees:
            dialog = AccountSelectionDialog(self.root, payee, account_choices)
            if dialog.result is None:
                messagebox.showwarning("Cancelled", "Categorization cancelled. No changes were made.")
                return []
            self.mappings.set(payee, dialog.result["debit_account"], dialog.result["credit_account"])

        sequence_tracker = self.ledger.next_sequence_numbers()
        existing_hashes = set(self.ledger.load_hashes().keys())
        categorized: List[CategorizedTransaction] = []
        for record in records:
            mapping = self.mappings.get(record.payee)
            if mapping is None:
                continue
            amount = to_positive_decimal(record.amount)
            currency = normalize_currency(record.currency) if record.currency else ""
            unique_hash = compute_unique_hash(
                record,
                mapping["debit_account"],
                mapping["credit_account"],
                amount_override=amount,
            )
            if unique_hash in existing_hashes:
                continue
            transaction_id = next_transaction_id(mapping["credit_account"], record.booking_date, sequence_tracker)
            existing_hashes.add(unique_hash)
            categorized.append(
                CategorizedTransaction(
                    source_file=record.source_file,
                    source_line=record.source_line,
                    booking_date=record.booking_date,
                    description=record.description,
                    amount=amount,
                    currency=currency,
                    payee=record.payee,
                    bank_account=record.bank_account,
                    debit_account=mapping["debit_account"],
                    credit_account=mapping["credit_account"],
                    transaction_id=transaction_id,
                    unique_hash=unique_hash,
                )
            )
        return categorized

    def _write_categorized_csv(self, transactions: Iterable[CategorizedTransaction], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                [
                    "Transaction ID",
                    "Date",
                    "Payee",
                    "Description",
                    "Amount",
                    "Currency",
                    "Debit account",
                    "Credit account",
                    "Bank account",
                ]
            )
            for tx in transactions:
                writer.writerow(
                    [
                        tx.transaction_id,
                        tx.booking_date.isoformat(),
                        tx.payee,
                        tx.description,
                        format_decimal(tx.amount),
                        tx.currency,
                        tx.debit_account,
                        tx.credit_account,
                        tx.bank_account or "",
                    ]
                )


def main() -> None:
    root = Tk()
    app = CategorizationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
