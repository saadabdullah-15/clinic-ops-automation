# Clinic Ops Automation

This project demonstrates small but useful operational tools for a physiotherapy clinic.  
It covers KPI dashboards, reception automation, and cancellation risk modeling.

---

## Features (Day 1–3)

- **01_kpi_dashboard**  
  - ETL pipeline to load mock patient/appointment/payment data  
  - Realtime KPIs in Streamlit (bookings, cancellations, show rate, revenue)  
  - Daily refresh job (from `data/daily/`)  
  - Sidebar controls: date picker, last refresh info, refresh cache button  
  - Extra KPIs: revenue **estimate vs paid**, utilization % per physio  

- **02_reception_automation** *(coming next)*  
  - CSV checks, reminders, local outbox, small Flask API  

- **03_cancellation_model** *(coming later)*  
  - Baseline model to predict no-show/cancellation risk  
  - Export `cancellation_scores.csv`  

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
# 1. Generate mock data (creates CSVs under data/raw/)
python -m common.generate_mock_data

# 2. Load schema + raw data into SQLite (clinic.db)
python -m 01_kpi_dashboard.etl.load

# 3. Create a daily snapshot from raw data
python -m common.make_daily_from_raw --day YYYY-MM-DD

# 4. Refresh DB for that day
python -m 01_kpi_dashboard.etl.refresh_daily --day YYYY-MM-DD

# 5. Launch Streamlit dashboard
streamlit run 01_kpi_dashboard/app.py
```

---

## Refresh Flow (Daily)

Minimal 3 commands you’ll use day to day:

```bash
python -m common.make_daily_from_raw --day YYYY-MM-DD
python -m 01_kpi_dashboard.etl.refresh_daily --day YYYY-MM-DD
streamlit run 01_kpi_dashboard/app.py
```

---

## Optional: Auto-refresh on Windows

**Create `scripts/run_refresh.bat`:**

```bat
@echo off
set ROOT=%~dp0..
call "%ROOT%\.venv\Scripts\activate"
python -m 01_kpi_dashboard.etl.refresh_daily
```

**Register scheduled task (every 15 minutes):**

```bash
schtasks /Create /SC MINUTE /MO 15 /TN "ClinicRefresh" /TR "\"C:\Users\YourName\path\to\repo\scripts\run_refresh.bat\"" /F
```

**Run manually for testing:**

```bash
schtasks /Run /TN "ClinicRefresh"
```

---

## Environment Variables

Copy `.env.example` to `.env` and edit as needed:

```env
DATABASE_URL=sqlite:///clinic.db
EMAIL_OUTBOX_DIR=outbox
```

---

## Tech Stack

- **Python:** pandas, numpy, SQLAlchemy, scikit-learn, streamlit, Flask, python-dotenv  
- **Database:** SQLite (default, can switch to Postgres)  
- **Task scheduling:** Windows Task Scheduler (optional for auto-refresh)  

---

## Next Steps (Day 4–5)

- Reception workflow automation: flags, priorities, reminder outbox, `/priorities` endpoint  
- Continue developing the cancellation model  
