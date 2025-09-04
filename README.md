# Clinic Ops Automation

Small, useful ops tools for a physiotherapy clinic:
- 📊 Streamlit KPI dashboard
- 📋 Reception workflow automation (priorities + reminders + API)
- 🔮 Cancellation risk model (scores feed the priorities)

---

## Table of Contents
- [Features](#features)
- [Progress by Day](#progress-by-day)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Daily Refresh Flow](#daily-refresh-flow)
- [Windows Auto-Refresh (optional)](#windows-auto-refresh-optional)
- [Environment Variables](#environment-variables)
- [Tech Stack](#tech-stack)
- [Reception Automation Usage](#reception-automation-usage)
- [Cancellation Model Usage](#cancellation-model-usage)
- [Schema Constraints & Validation](#day-8-schema-constraints--validation)
- [Screenshots](#screenshots)

---

## Features

### 01_kpi_dashboard (Day 1–3)
- ETL to load mock patients/appointments/payments
- Live KPIs in Streamlit: bookings, cancellations, show rate, revenue
- Daily refresh from `data/daily/`
- Sidebar: date picker, last refresh info, clear cache button
- Extra: revenue **estimate vs paid**, utilization % per physio

### 02_reception_automation (Day 4–5)
- Build priorities CSV (flags: new patient, missing phone/consent, risk bucket)
- Generate local **outbox** reminder “emails”
- Tiny Flask API exposing `/priorities` as JSON

### 03_cancellation_model (Day 6–7)
- Train on historical appointments, export `cancellation_scores.csv`
- Integrated in priorities (low/medium/high buckets)
- Optional/stretch: **RandomForest**, feature importances, dynamic **high_risk_threshold**

### 04_schema_validation (Day 8)
- Migration to stricter SQLite schema
- Fast data validator to check inputs before refresh
- Integrated into scheduled refresh jobs (can abort on errors)

---

## Progress by Day
- ✅ **Day 1:** repo, env, mock data, schema, dashboard skeleton  
- ✅ **Day 2–3:** realtime plumbing, refresh job, sidebar, utilization & revenue  
- ✅ **Day 4–5:** priorities builder, outbox reminders, Flask API  
- ✅ **Day 6–7:** model trained & integrated (RandomForest + importances + threshold)  
- ✅ **Day 8:** stricter schema migration + validator integrated  

---

## Project Structure
```
clinic-ops-automation/
├── 01_kpi_dashboard/
│   ├── app.py                  # Streamlit dashboard
│   ├── schema.sql              # DB schema incl. etl_runs
│   └── etl/
│       ├── load.py             # Initial load from raw data
│       ├── refresh_daily.py    # Refresh from daily snapshots
│       └── migrate_v2_sqlite.py# Day 8 migration to stricter schema
├── 02_reception_automation/
│   ├── __init__.py
│   ├── build_priorities.py     # Build priorities CSV
│   ├── send_reminders.py       # Generate local reminder "emails"
│   └── server.py               # Tiny Flask API for priorities
├── 03_cancellation_model/
│   ├── __init__.py
│   ├── features.py             # Feature engineering
│   ├── train.py                # Train model + metrics
│   └── score.py                # Score a given day
├── 04_schema_validation/
│   └── validate_data.py        # Day 8 fast validation
├── common/
│   ├── db.py                   # DB connection helper
│   ├── generate_mock_data.py
│   └── make_daily_from_raw.py
├── data/
│   ├── raw/                    # Full mock CSVs
│   └── daily/                  # YYYY-MM-DD/appointments.csv, payments.csv
├── scripts/
│   └── run_refresh.bat         # Windows scheduled job (with validation gate)
├── assets/
├── .env.example
├── .gitignore
└── requirements.txt
```

---

## Prerequisites
- Python 3.10+  
- Windows PowerShell or macOS/Linux shell  
- `pip install -r requirements.txt`

> Tip (Windows):  
> ```powershell
> py -m venv .venv
> .\.venv\Scripts\Activate.ps1
> pip install -r requirements.txt
> ```

---

## Quick Start
```bash
# 1) Generate mock data (writes CSVs to data/raw/)
python -m common.generate_mock_data

# 2) Load schema + raw data into SQLite (creates clinic.db)
python -m 01_kpi_dashboard.etl.load

# 3) Create a daily snapshot from raw
python -m common.make_daily_from_raw --day YYYY-MM-DD

# 4) Refresh DB for that day
python -m 01_kpi_dashboard.etl.refresh_daily --day YYYY-MM-DD

# 5) Launch the dashboard
streamlit run 01_kpi_dashboard/app.py
```

---

## Daily Refresh Flow
Most days you only need:
```bash
python -m common.make_daily_from_raw --day YYYY-MM-DD
python -m 01_kpi_dashboard.etl.refresh_daily --day YYYY-MM-DD
streamlit run 01_kpi_dashboard/app.py
```

---

## Windows Auto-Refresh (optional)
`scripts/run_refresh.bat`:
```bat
@echo off
set ROOT=%~dp0..
call "%ROOT%\.venv\Scriptsctivate"
python "%ROOT%_schema_validationalidate_data.py"
if %ERRORLEVEL% NEQ 0 (
  echo Validation failed, aborting refresh.
  exit /b 1
)
python -m 01_kpi_dashboard.etl.refresh_daily
```

Register the task (every 15 min):
```bat
schtasks /Create /SC MINUTE /MO 15 /TN "ClinicRefresh" /TR ""C:\path\to\repo\scripts\run_refresh.bat"" /F
```

Run once to test:
```bat
schtasks /Run /TN "ClinicRefresh"
```

---

## Environment Variables
Copy `.env.example` → `.env` and update as needed:
```env
DATABASE_URL=sqlite:///clinic.db
EMAIL_OUTBOX_DIR=outbox
```

---

## Tech Stack
- Python: pandas, numpy, SQLAlchemy, scikit-learn, Streamlit, Flask, python-dotenv  
- DB: SQLite by default (switch via `DATABASE_URL`)  
- Scheduler: Windows Task Scheduler (optional)

---

## Reception Automation Usage
Build priorities for a day:
```bash
python -m 02_reception_automation.build_priorities --day 2025-09-05
```

Send reminders to local outbox:
```bash
python -m 02_reception_automation.send_reminders --day 2025-09-05
# preview only:
python -m 02_reception_automation.send_reminders --day 2025-09-05 --dry-run
```

Run the tiny API:
```bash
python -m 02_reception_automation.server
```
→ Open [http://127.0.0.1:8008/priorities?day=2025-09-05](http://127.0.0.1:8008/priorities?day=2025-09-05)

---

## Cancellation Model Usage
Train:
```bash
python 03_cancellation_model/train.py --valid-days 7
```

Score a day:
```bash
python 03_cancellation_model/score.py --day 2025-09-05
```

Rebuild priorities so risk is live:
```bash
python -m 02_reception_automation.build_priorities --day 2025-09-05
```

**Outputs:**
- `03_cancellation_model/model.joblib` — trained model  
- `03_cancellation_model/metrics.json` — metrics, feature importances, high_risk_threshold  
- `data/daily/<DATE>/cancellation_scores.csv` — model scores for that day  
- `03_cancellation_model/cancellation_scores.csv` — combined history  

---

## Schema Constraints & Validation
Migrate to stricter schema (SQLite):
```bash
python 01_kpi_dashboard/etl/migrate_v2_sqlite.py
```

Run fast validation (fails on hard errors):
```bash
# preferred (if you added __init__.py):
python -m 04_schema_validation.validate_data

# or run directly:
python 04_schema_validation/validate_data.py
```

Suggested order before refresh:
```bash
python -m 04_schema_validation.validate_data
python -m 01_kpi_dashboard.etl.refresh_daily --day YYYY-MM-DD
```

---

## Screenshots
- 📊 KPI Dashboard  
- 📋 Priorities JSON API  
- 📧 Outbox Reminder Example  

(Add images in `assets/` and reference here)
