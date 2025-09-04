# Clinic Ops Automation

Small, useful ops tools for a physiotherapy clinic:
- 📊 Realtime KPI dashboard (Streamlit)
- 📋 Reception workflow automation (priorities + reminders + API)
- 🔮 Cancellation risk model (risk scores feed the priorities)
- ✅ Schema constraints and validation to protect data quality

![Demo](assets/demo.gif)
*If the GIF does not load on GitHub, open `assets/demo.gif` directly.*

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

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
- [License](#license)

---

## Features

### 01_kpi_dashboard - realtime KPIs
ETL + SQLite + Streamlit for daily clinic health: bookings, show rate, cancellations, revenue (estimate vs paid), and utilization per physio. Supports daily drops under `data/daily/` with an idempotent refresh that replaces a single day and logs runs to `etl_runs`.

### 02_reception_automation - reception copilot
Builds a next-day callback list with flags (new patient, missing phone or consent) and a priority score combining model risk, data completeness, and timing. Generates local emails in `outbox/` and serves `/priorities` via Flask.

### 03_cancellation_model - risk scoring
Predictive baseline (logistic regression or random forest) using appointment context and patient history. Outputs `cancellation_scores.csv` per day and a combined file. Writes ROC AUC, average precision, and precision at k to `03_cancellation_model/metrics.json`.

### 04_schema_validation - database rigor
Migration to a stricter schema (constraints, indices, triggers). Fast validator that checks invalid statuses, orphan records, overlaps, and payment sanity. Use it to gate scheduled refreshes.

---

## Architecture

```mermaid
flowchart LR
  %% --- Subgraphs ---
  subgraph Data
    direction LR
    RAW["CSV: data/raw/*"]:::file
    DAILY["Daily drops: data/daily/YYYY-MM-DD/*"]:::file
  end

  subgraph Model
    direction LR
    MTRAIN["train.py"]:::svc
    MSCORE["score.py"]:::svc
    MSCORES["cancellation_scores.csv"]:::file
  end

  subgraph Database
    DB[(SQLite: clinic.db)]:::db
  end

  subgraph Reception
    direction LR
    PRI["priorities_YYYY-MM-DD.csv"]:::file
    OUTBOX["outbox/*.txt"]:::file
    API["/priorities?day=YYYY-MM-DD"]:::svc
  end

  subgraph KPI
    ST["Streamlit Dashboard"]:::svc
  end

  %% --- Flows ---
  RAW -->|etl/load.py| DB
  DAILY -->|etl/refresh_daily.py| DB

  DB -->|SQL| ST

  DB -->|build_priorities.py| PRI
  PRI -->|send_reminders.py| OUTBOX
  PRI -->|server.py| API

  MTRAIN --> MSCORES
  MSCORE --> MSCORES
  MSCORES --> DAILY

  %% --- Styling ---
  classDef db fill:#d8f0ff,stroke:#0b64c0;
  classDef svc fill:#eef7e9,stroke:#3b7c2a;
  classDef file fill:#f8f8f8,stroke:#999;

```

---

## Quick Start

```bash
# 1) Generate mock data and load the initial DB
python common/generate_mock_data.py
python 01_kpi_dashboard/etl/load.py

# 2) Create a daily snapshot and refresh that day
python common/make_daily_from_raw.py --day YYYY-MM-DD
python 01_kpi_dashboard/etl/refresh_daily.py --day YYYY-MM-DD

# 3) Launch the dashboard
python -m streamlit run 01_kpi_dashboard/app.py
```

---

## Module Usage

### KPIs - run in 3 commands
```bash
python common/generate_mock_data.py
python 01_kpi_dashboard/etl/load.py
python -m streamlit run 01_kpi_dashboard/app.py
```

### Reception automation - run in 3 commands
```bash
python 02_reception_automation/build_priorities.py --day 2025-09-05
python 02_reception_automation/send_reminders.py --day 2025-09-05
python 02_reception_automation/server.py
# open: http://127.0.0.1:8008/priorities?day=2025-09-05
```

### Cancellation model - run in 3 commands
```bash
python 03_cancellation_model/train.py --valid-days 7
python 03_cancellation_model/score.py --day 2025-09-05
python 02_reception_automation/build_priorities.py --day 2025-09-05
```

### Schema and validation
```bash
# migrate to stricter schema
python 01_kpi_dashboard/etl/migrate_v2_sqlite.py

# validate before refresh
python 04_schema_validation/validate_data.py
```

Windows scheduled refresh example:
```bat
@echo off
set ROOT=%~dp0..
call "%ROOT%\.venv\Scripts\activate"
python "%ROOT%\04_schema_validation\validate_data.py" || exit /b 1
python "%ROOT%\01_kpi_dashboard\etl\refresh_daily.py"
```

---

## Configuration

Create `.env` from `.env.example`:
```env
DATABASE_URL=sqlite:///clinic.db
EMAIL_OUTBOX_DIR=outbox
```

Switch to Postgres:
```bash
pip install psycopg2-binary
# then set
# DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname
```

---

## API

`GET /priorities?day=YYYY-MM-DD`

**Response 200**
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

**Fields**
| Field | Type | Notes |
|------|------|-------|
| `day` | string (date) | Requested day |
| `count` | integer | Number of items |
| `appointment_id` | integer | Unique appointment id |
| `patient_id` | integer | Unique patient id |
| `patient_name` | string | Full name |
| `phone` | string | May be empty |
| `consent_form_received` | integer {0,1} | 1 means consent on file |
| `physio_name` | string | Treating physio |
| `appt_start` | ISO datetime | Appointment start time |
| `is_new_patient` | boolean | True if first visit before this day |
| `risk_bucket` | enum {low, medium, high} | Derived from risk score |
| `missing_phone` | boolean | Data quality flag |
| `missing_consent` | boolean | Data quality flag |
| `priority_score` | number | Higher means earlier follow-up |
| `priority_reason` | string | Human readable reasons |

**Errors**
- 400 invalid or missing day parameter
- 200 with `count: 0` when no priorities exist for the day

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
- On Windows prefer `python script.py` over `python -m package.module` for numbered folders.

---

## License
MIT
