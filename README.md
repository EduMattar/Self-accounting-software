# Self Accounting Desktop Helper

A small Tkinter-based desktop helper that normalizes CSV statements from multiple banks, maps merchants to your chart of accounts, and produces a consolidated ledger together with ready-to-paste journal entries in Excel.

## Features

- Import CSV statements from different banks (mixed delimiters and column names supported).
- Auto-detect date, amount, currency, and account columns even when headers use unfamiliar labels.
- Detect unique payees/merchants (combining counterparty account numbers when available) and prompt once for the matching debit/credit accounts.
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

### Quick command checklist

Paste these commands into a fresh terminal session to clone the project, prepare the virtual environment, and open the GUI. Replace `<your-account>` with the GitHub owner of your fork if needed. If you already cloned the repository, start from the `cd Self-accounting-software` line.

```bash
# 1) Grab the latest code
git clone https://github.com/<your-account>/Self-accounting-software.git
cd Self-accounting-software

# 2) (macOS + Homebrew Python) install Tk support once
brew install python-tk@3.13

# 3) Create & activate an isolated environment
python3 -m venv .venv
source .venv/bin/activate

# 4) Install Python dependencies inside the venv
pip install -r requirements.txt

# 5) Pull any new commits, then start the app
git pull --ff-only
python -m app
```

For everyday use, you only need to revisit the last three steps: reactivate `.venv` (if your prompt no longer shows it), run `git pull --ff-only` to grab the latest commits, and then launch with `python -m app`.

### Background details

1. Ensure your Python installation includes **Tk** support (required for the GUI).
   - macOS users: the official installer from [python.org](https://www.python.org/downloads/macos/) bundles Tk. If you use Homebrew, install the matching python-tk formula (for example, run `brew install python-tk@3.13`).
   - Linux users: install your distro's `tk`/`python3-tk` package.
2. Create and activate a Python 3.11+ environment.
3. Install dependencies with `pip install -r requirements.txt`.
4. Adjust `config/accounts.json` if you need to rename or extend accounts. The bundled list matches the chart you provided and keeps **numeric** identifiers so that the transaction ID format `xxmmyynnn` can be produced.
5. Launch the desktop app with `python -m app`.

   On macOS you can double-click `launch_app.command` in Finder after marking it as executable (`chmod +x launch_app.command`).

   The script activates `.venv`, pulls the latest code with `git pull --ff-only`, and opens the GUI. If the environment has not been created yet, it shows a dialog explaining which setup step is missing.

### Create a macOS app icon/launcher

If you prefer a Dock icon instead of the shell script, compile the supplied AppleScript into a `.app` bundle:

1. Edit `macos/launch_app.applescript` and replace `/path/to/Self-accounting-software` with the absolute path to your clone.
2. From Terminal, run:

   ```bash
   osacompile -o "Self Accounting Helper.app" macos/launch_app.applescript
   ```

3. Move the generated `Self Accounting Helper.app` anywhere you like (Applications folder, Desktop, or the Dock). Double-clicking it pulls the latest commits, activates your virtual environment, and launches `python -m app` automatically.

Recompile the app after updating the AppleScript path or if you relocate the repository.

### Always launch the freshest GitHub version

Whenever you run the app from Terminal, pull the latest changes first:

```bash
git pull --ff-only
python -m app
```

If you keep local edits, commit or stash them before pulling. The Finder launcher (`launch_app.command`) and the AppleScript app bundle already execute `git pull --ff-only` for you before opening the GUI.

## Usage workflow

1. Click **Import statement** and select a CSV from Finder.
2. If the statement omits the currency or your bank account number, provide the value once when prompted.
3. For new payees, choose the debit and credit accounts. The app saves this mapping for the next import.
4. Review the success dialog. The following files are updated/generated:
   - `data/universal_transactions.csv`: master ledger with unique transaction IDs.
   - `output/categorized/<name>_categorized.csv`: statement annotated with debit/credit accounts.
   - `output/journal.xlsx`: journal entries grouped per currency, ready for copy-paste into your Excel workbook.

## Customizing for your banks

The CSV parser recognises many header aliases and also inspects the first rows of each statement to infer date, amount, debit/credit, currency, and bank-account columns when names are unfamiliar. If your bank uses completely opaque headers, extend the alias lists in `app/parsers.py` or preprocess your statement in Excel before importing.

## Resetting mappings or ledger

- Delete `config/payee_mappings.json` to forget saved merchant assignments.
- Delete `data/universal_transactions.csv` to rebuild the ledger from scratch (the file is recreated automatically on the next import).

## Limitations

- Only CSV statements are supported at the moment.
- The generated transaction IDs use the **credit** account number as the prefix. Ensure your bank and FX accounts have distinct numeric identifiers.
- Journal entries are written with two decimal places; adjust `app/utils.py` if your reporting requires more precision.
