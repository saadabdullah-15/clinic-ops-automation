# Clinic Ops Automation

Small but useful operational tools for a physiotherapy clinic.  
Includes KPI dashboards, reception workflow automation, and a cancellation risk model.

---

## Contents

- [Features](#features)  
- [Progress by Day](#progress-by-day)  
- [Project Structure](#project-structure)  
- [Quick Start](#quick-start)  
- [Refresh Flow](#refresh-flow-daily)  
- [Optional Auto Refresh on Windows](#optional-auto-refresh-on-windows)  
- [Environment Variables](#environment-variables)  
- [Tech Stack](#tech-stack)  
- [Reception Automation Usage](#reception-automation-usage)  
- [Screenshots](#screenshots)

---

## Features

### 01_kpi_dashboard (Day 1 to 3)

- ETL pipeline to load mock patient, appointment, and payment data  
- Realtime KPIs in Streamlit: bookings, cancellations, show rate, revenue  
- Daily refresh job from `data/daily/`  
- Sidebar controls: date picker, last refresh info, refresh cache button  
- Extra KPIs: revenue estimate vs paid, utilization percent per physio

### 02_reception_automation (Day 4 to 5)

- Build priorities CSV with flags: new patient, missing phone or consent, risk score  
- Generate local outbox reminder “emails”  
- Tiny Flask API to serve `/priorities` as JSON for the reception screen

### 03_cancellation_model (Day 6 to 7, planned)

- Baseline model to predict no show or cancellation risk  
- Export `cancellation_scores.csv`

---

## Progress by Day

- ✅ Day 1: Repo setup, environment, mock data generator, schema, dashboard skeleton  
- ✅ Day 2 to 3: Realtime KPI plumbing, refresh job, sidebar controls, utilization and revenue KPIs  
- ✅ Day 4 to 5: Reception automation, priorities CSV, outbox reminders, Flask API  
- 🚧 Day 6 to 7 next: Cancellation model, train baseline, export risk scores, integrate into priorities

---

## Project Structure

```
clinic-ops-automation/
├── 01_kpi_dashboard/
│   ├── app.py               # Streamlit dashboard
│   ├── schema.sql           # DB schema incl. etl_runs
│   └── etl/
│       ├── load.py          # Initial load from raw data
│       └── refresh_daily.py # Refresh job from daily snapshots
├── 02_reception_automation/
│   ├── __init__.py
│   ├── build_priorities.py  # Build priorities CSV for tomorrow
│   ├── send_reminders.py    # Generate local reminder "emails"
│   └── server.py            # Tiny Flask API for priorities
├── 03_cancellation_model/
├── common/
│   ├── db.py                # DB connection helper
│   ├── generate_mock_data.py
│   └── make_daily_from_raw.py
├── data/
│   ├── raw/                 # Full mock CSVs
│   └── daily/               # Daily snapshots (YYYY-MM-DD/appointments.csv, payments.csv)
├── assets/
├── scripts/
│   └── run_refresh.bat      # Windows scheduled refresh job
├── .env.example
├── .gitignore
└── requirements.txt
```

---

## Quick Start

```bash
# 1) Generate mock data (creates CSVs under data/raw/)
python -m common.generate_mock_data

# 2) Load schema and raw data into SQLite (creates clinic.db)
python -m 01_kpi_dashboard.etl.load

# 3) Create a daily snapshot from raw data
python -m common.make_daily_from_raw --day YYYY-MM-DD

# 4) Refresh DB for that day
python -m 01_kpi_dashboard.etl.refresh_daily --day YYYY-MM-DD

# 5) Launch the Streamlit dashboard
streamlit run 01_kpi_dashboard/app.py
```

> Tip: Create and activate a virtual environment, then `pip install -r requirements.txt`.

---

## Refresh Flow (Daily)

Minimal three commands used day to day:

```bash
python -m common.make_daily_from_raw --day YYYY-MM-DD
python -m 01_kpi_dashboard.etl.refresh_daily --day YYYY-MM-DD
streamlit run 01_kpi_dashboard/app.py
```

---

## Optional Auto Refresh on Windows

Create `scripts/run_refresh.bat`:

```bat
@echo off
set ROOT=%~dp0..
call "%ROOT%\.venv\Scriptsctivate"
python -m 01_kpi_dashboard.etl.refresh_daily
```

Register a scheduled task that runs every 15 minutes:

```bat
schtasks /Create /SC MINUTE /MO 15 /TN "ClinicRefresh" /TR ""C:\Users\YourName\path\to\repo\scripts\run_refresh.bat"" /F
```

Run it manually for testing:

```bat
schtasks /Run /TN "ClinicRefresh"
```

---

## Environment Variables

Copy `.env.example` to `.env` and edit as needed:

```
DATABASE_URL=sqlite:///clinic.db
EMAIL_OUTBOX_DIR=outbox
```

---

## Tech Stack

- **Python**: pandas, numpy, SQLAlchemy, scikit-learn, Streamlit, Flask, python-dotenv  
- **Database**: SQLite by default. You can switch to Postgres by updating `DATABASE_URL`.  
- **Task scheduling**: Windows Task Scheduler for optional auto refresh

---

## Reception Automation Usage

Build priorities for a day:

```bash
python -m 02_reception_automation.build_priorities --day 2025-09-05
```

Send reminder emails to local outbox:

```bash
python -m 02_reception_automation.send_reminders --day 2025-09-05

# Preview without writing to outbox
python -m 02_reception_automation.send_reminders --day 2025-09-05 --dry-run
```

Run the tiny API:

```bash
python -m 02_reception_automation.server
# Then request:
# GET http://127.0.0.1:8008/priorities?day=2025-09-05
```

---

## Screenshots

- 📊 KPI Dashboard  
- 📋 Priorities JSON API  
- 📧 Outbox Reminder Example

> Add images under `assets/` and reference them here when available.
