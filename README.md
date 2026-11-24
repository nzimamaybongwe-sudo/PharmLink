# PharmLink — Integrated Hospital & Pharmacy Management Platform

PharmLink is a modular Flask web application designed to manage hospital operations, patient consultations, prescriptions, batch-level medicine inventory (FEFO), dispensing, QR prescription verification, and pharmacy referral coordination in Eswatini.

---

## Technology Stack

- **Backend:** Python 3, Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF
- **Frontend:** HTML5, CSS3, Bootstrap 5, Bootstrap Icons, Chart.js, Vanilla JavaScript
- **Database:** MySQL / MariaDB via WAMP Server (`pharmlink_db`)
- **QR / Barcodes:** `qrcode`, `python-barcode`, `Pillow`

---

## Setup Instructions (Windows + WAMP)

### 1. Start WAMP Server & Create Database
1. Start **WAMP Server** (ensure the WAMP tray icon is green and MySQL/MariaDB is running on port `3306`).
2. Open **phpMyAdmin** (or MySQL CLI) and create the database:
   ```sql
   CREATE DATABASE pharmlink_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

### 2. Configure Environment Variables
1. Copy `.env.example` to `.env`:
   ```powershell
   copy .env.example .env
   ```
2. Edit `.env` and set a strong `SECRET_KEY` and your WAMP MySQL credentials (`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME=pharmlink_db`).

### 3. Install Python Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Initialize Migrations & Seed Pilot Data
```powershell
flask db init
flask db migrate -m "Initial PharmLink schema"
flask db upgrade
python seed.py
```

### 5. Run the Flask Application
```powershell
python run.py
```
Open your browser at `http://localhost:5000`.

---

## Pilot Test Accounts (Dummy Data from `seed.py`)

Password for all seeded accounts: `PharmLink@123`

| Role | Email |
|---|---|
| Platform Administrator | `platform@pharmlink.sz` |
| Hospital Administrator | `admin@mbabanepilot.sz` |
| Doctor | `doctor@mbabanepilot.sz` |
| Internal Pharmacist | `pharmacist@mbabanepilot.sz` |
| Inventory Officer | `inventory@mbabanepilot.sz` |
| Finance Officer | `finance@mbabanepilot.sz` |

---

## Running Automated Tests
The test suite uses an in-memory SQLite database (`TestingConfig`) so it runs independently without modifying `pharmlink_db`:
```powershell
python -m unittest discover -s tests -v
```
