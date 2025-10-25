# Self Accounting Desktop Helper

A small Tkinter-based desktop helper that normalizes CSV statements from multiple banks, maps merchants to your chart of accounts, and produces a consolidated ledger together with ready-to-paste journal entries in Excel.

## Features

- Import CSV statements from different banks (mixed delimiters and column names supported).
- Detect unique payees/merchants and prompt once for the matching debit/credit accounts.
- Persist mappings for future statements in `config/payee_mappings.json`.
- Append the transactions to a universal ledger (`data/universal_transactions.csv`) with statement aware numbering (`xxmmyynnn`).
- Generate categorized CSV exports for each processed statement.
- Build an Excel workbook with journal entries separated by currency.

## Project layout

```
app/                Python source files
config/accounts.json  Sample chart of accounts (edit to match your needs)
config/payee_mappings.json  Auto-filled merchant → account mappings
output/             Generated files (categorized CSVs + journal.xlsx)
data/               Universal ledger storage
```

## Getting started

1. Create and activate a Python 3.11+ environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Adjust `config/accounts.json` to reflect your account numbers. The program expects **numeric** identifiers so that the transaction ID format `xxmmyynnn` can be produced.
4. Launch the desktop app:

   ```bash
   python -m app
   ```

## Usage workflow

1. Click **Import statement** and select a CSV from Finder.
2. If the statement omits the currency or your bank account number, provide the value once when prompted.
3. For new payees, choose the debit and credit accounts. The app saves this mapping for the next import.
4. Review the success dialog. The following files are updated/generated:
   - `data/universal_transactions.csv`: master ledger with unique transaction IDs.
   - `output/categorized/<name>_categorized.csv`: statement annotated with debit/credit accounts.
   - `output/journal.xlsx`: journal entries grouped per currency, ready for copy-paste into your Excel workbook.

## Customizing for your banks

The CSV parser accepts multiple header variants for dates, descriptions, payees, amounts, and account identifiers. If your bank uses uncommon column names, extend the alias lists in `app/parsers.py` or preprocess your statement in Excel before importing.

## Resetting mappings or ledger

- Delete `config/payee_mappings.json` to forget saved merchant assignments.
- Delete `data/universal_transactions.csv` to rebuild the ledger from scratch (the file is recreated automatically on the next import).

## Limitations

- Only CSV statements are supported at the moment.
- The generated transaction IDs use the **credit** account number as the prefix. Ensure your bank and FX accounts have distinct numeric identifiers.
- Journal entries are written with two decimal places; adjust `app/utils.py` if your reporting requires more precision.
