# Clinic Ops Automation

Goal: show evidence that I can build small, useful ops tools for a physio clinic:
- 01-kpi-dashboard: simple ETL + Streamlit KPIs (bookings, show rate, cancellations, revenue estimate, utilization per physio)
- 02-reception-automation: daily CSV checks, priority list, reminder "emails" to a local outbox, small Flask JSON endpoint
- 03-cancellation-model: baseline model to score no-show/cancellation risk and export `cancellation_scores.csv`

## Quick start
```bash
python common/generate_mock_data.py         # creates CSVs under data/raw
python 01-kpi-dashboard/etl/load.py         # creates clinic.db and loads CSVs
streamlit run 01-kpi-dashboard/app.py       # open dashboard
