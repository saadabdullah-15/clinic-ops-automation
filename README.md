# Clinic Ops Automation

Small, useful ops tools for a physiotherapy clinic:
- 📊 Realtime KPI dashboard (Streamlit)
- 📋 Reception workflow automation (priorities + reminders + API)
- 🔮 Cancellation risk model (risk scores feed the priorities)
- ✅ Schema constraints and validation to protect data quality

![Demo](assets/demo.gif)

---

## What this proves
- I can build a small ETL and SQLite schema with constraints and triggers.
- I can ship a realtime Streamlit dashboard that refreshes from daily drops.
- I can integrate a simple ML model into an operations workflow and expose a JSON API.
- I can add a fast validation gate that blocks bad data before refresh.

---

## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Module Usage](#module-usage)
- [Configuration](#configuration)
- [API](#api)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Notes](#notes)

---

## Features

### 01_kpi_dashboard — realtime KPIs
ETL + SQLite + Streamlit for daily clinic health: bookings, show rate, cancellations, revenue (estimate vs paid), and utilization per physio. Supports daily drops under `data/daily/` with an idempotent refresh that replaces one day and logs runs to `etl_runs`.

### 02_reception_automation — reception copilot
Builds a next-day callback list with flags (new patient, missing phone or consent) and a priority score combining model risk, data completeness, and timing. Generates local “emails” in `outbox/` and serves `/priorities` via Flask.

### 03_cancellation_model — risk scoring
Predictive baseline (logistic or random forest) using appointment context and patient history. Outputs `cancellation_scores.csv` per day and a combined file. Writes ROC AUC, average precision, and precision@k to `03_cancellation_model/metrics.json`.

### 04_schema_validation — database rigor
Migration to a stricter schema (constraints, indices, triggers). Fast validator that checks invalid statuses, orphan records, overlaps, and payment sanity. Use it to gate scheduled refreshes.

---

## Architecture

```mermaid
flowchart LR
  subgraph Data
    RAW[CSV: data/raw/*]:::file
    DAILY[Daily drops: data/daily/YYYY-MM-DD/*]:::file
  end

  subgraph DB
    DB[(SQLite: clinic.db)]:::db
  end

  subgraph KPI
    ST[Streamlit Dashboard]:::svc
  end

  subgraph Reception
    PRI[priorities_YYYY-MM-DD.csv]:::file
    OUTBOX[outbox/*.txt]:::file
    API[/priorities?day=YYYY-MM-DD]:::svc
  end

  subgraph Model
    MTRAIN[train.py]:::svc
    MSCORE[score.py]:::svc
    MSCORES[cancellation_scores.csv]:::file
  end

  RAW -->|etl/load.py| DB
  DAILY -->|etl/refresh_daily.py| DB
  DB -->|SQL| ST

  DB -->|build_priorities.py| PRI
  PRI -->|send_reminders.py| OUTBOX
  PRI -->|server.py| API

  MTRAIN --> MSCORES
  MSCORE --> MSCORES
  MSCORES --> DAILY

  classDef db fill:#d8f0ff,stroke:#0b64c0;
  classDef svc fill:#eef7e9,stroke:#3b7c2a;
  classDef file fill:#f8f8f8,stroke:#999;
```

---

## Quick Start

```bash
# 1) Generate mock data and load initial DB
python -m common.generate_mock_data
python -m 01_kpi_dashboard.etl.load

# 2) Create a daily snapshot and refresh that day
python -m common.make_daily_from_raw --day YYYY-MM-DD
python -m 01_kpi_dashboard.etl.refresh_daily --day YYYY-MM-DD

# 3) Launch dashboard
python -m streamlit run 01_kpi_dashboard/app.py
```

---

## Module Usage

### KPIs
```bash
python -m common.generate_mock_data
python -m 01_kpi_dashboard.etl.load
python -m streamlit run 01_kpi_dashboard/app.py
```

### Reception automation
```bash
# Build priorities for a day
python -m 02_reception_automation.build_priorities --day 2025-09-05

# Send reminders to local outbox
python -m 02_reception_automation.send_reminders --day 2025-09-05
python -m 02_reception_automation.send_reminders --day 2025-09-05 --dry-run  # preview

# Serve priorities as JSON
python -m 02_reception_automation.server
# http://127.0.0.1:8008/priorities?day=2025-09-05
```

### Cancellation model
```bash
# Train and write metrics.json and model.joblib
python 03_cancellation_model/train.py --valid-days 7

# Score a target day and export cancellation_scores.csv
python 03_cancellation_model/score.py --day 2025-09-05

# Rebuild priorities to include real risk scores
python -m 02_reception_automation.build_priorities --day 2025-09-05
```

### Schema and validation
```bash
# Migrate to stricter schema
python 01_kpi_dashboard/etl/migrate_v2_sqlite.py

# Validate before refresh
python -m 04_schema_validation.validate_data
```

Windows scheduled refresh example:
```bat
@echo off
set ROOT=%~dp0..
call "%ROOT%\.venv\Scripts\activate"
python -m 04_schema_validation.validate_data || exit /b 1
python -m 01_kpi_dashboard.etl.refresh_daily
```

---

## Configuration

Create `.env` from `.env.example`:
```env
DATABASE_URL=sqlite:///clinic.db
EMAIL_OUTBOX_DIR=outbox
```
Switch to Postgres by setting `DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname`.

---

## API

`GET /priorities?day=YYYY-MM-DD` returns:

```json
{
  "day": "2025-09-05",
  "count": 12,
  "items": [
    {
      "appointment_id": 123,
      "patient_id": 77,
      "patient_name": "Pat Smith",
      "phone": "+49-170-1234567",
      "consent_form_received": 1,
      "physio_name": "Marta K",
      "appt_start": "2025-09-05T10:00:00+02:00",
      "is_new_patient": true,
      "risk_bucket": "high",
      "missing_phone": false,
      "missing_consent": false,
      "priority_score": 168.0,
      "priority_reason": "new patient, risk high"
    }
  ]
}
```

---

## Project Structure
```
clinic-ops-automation/
├── 01_kpi_dashboard/
│   ├── app.py
│   ├── schema.sql
│   └── etl/
│       ├── load.py
│       ├── refresh_daily.py
│       └── migrate_v2_sqlite.py
├── 02_reception_automation/
│   ├── __init__.py
│   ├── build_priorities.py
│   ├── send_reminders.py
│   └── server.py
├── 03_cancellation_model/
│   ├── __init__.py
│   ├── features.py
│   ├── train.py
│   └── score.py
├── 04_schema_validation/
│   └── validate_data.py
├── common/
│   ├── db.py
│   ├── generate_mock_data.py
│   └── make_daily_from_raw.py
├── scripts/
│   ├── run_refresh.bat
│   └── report.py
├── data/
│   ├── raw/
│   └── daily/
├── assets/
│   ├── summary.json
│   └── demo.gif
├── .env.example
├── .gitignore
└── requirements.txt
```

---

## Tech Stack
- Python: pandas, numpy, SQLAlchemy, scikit-learn, Streamlit, Flask, python-dotenv
- DB: SQLite by default, swappable via `DATABASE_URL`
- Scheduler: Windows Task Scheduler example

---

## Notes
- All data in this repo is synthetic. The outbox creates local text files, not real emails.
- Metrics are written to `03_cancellation_model/metrics.json`. Use `scripts/report.py` to print a snapshot.
- For imports on Windows use `python -m ...` form to avoid module path issues.
