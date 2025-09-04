import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st
from sqlalchemy import text
from common.db import engine
from datetime import datetime, date, timedelta
import pytz


st.set_page_config(page_title="Clinic KPIs", layout="wide")

# today in Berlin
berlin = pytz.timezone("Europe/Berlin")
today = datetime.now(berlin).date()

# -------------------------------
# Sidebar controls
# -------------------------------
st.sidebar.title("Controls")
picked_day = st.sidebar.date_input(
    "Day",
    today,
    min_value=today.replace(year=today.year - 1),
    max_value=today,
)

# show last refresh info if table exists
last_info = ""
try:
    with engine.begin() as conn:
        df = pd.read_sql(
            text(
                """SELECT target_date, MAX(ran_at) AS last_run
                   FROM etl_runs WHERE job='refresh_daily'
                   GROUP BY target_date
                   ORDER BY target_date DESC LIMIT 1"""
            ),
            conn,
        )
    if not df.empty:
        last_info = (
            f"Last refresh: {df.loc[0,'target_date']} at {df.loc[0,'last_run']} UTC"
        )
except Exception:
    last_info = "No refresh history yet."

st.sidebar.caption(last_info)

if st.sidebar.button("Refresh KPIs now"):
    st.cache_data.clear()
    st.success(
        "Cache cleared. Use your terminal to run: python -m 01_kpi_dashboard.etl.refresh_daily"
    )


# -------------------------------
# KPI queries
# -------------------------------
@st.cache_data(ttl=60)
def kpis_for_day(day):
    q = """
    WITH todays AS (
      SELECT * FROM appointments
      WHERE DATE(appt_start) = :d
    ),
    completed AS (
      SELECT * FROM todays WHERE status='completed'
    ),
    noshow AS (
      SELECT * FROM todays WHERE status='no_show'
    ),
    canceled AS (
      SELECT * FROM todays WHERE status='canceled'
    )
    SELECT
      (SELECT COUNT(*) FROM todays) AS bookings,
      (SELECT COUNT(*) FROM canceled) AS cancellations,
      (SELECT CASE WHEN (SELECT COUNT(*) FROM completed)+ (SELECT COUNT(*) FROM noshow) = 0
              THEN 0.0
              ELSE 1.0 * (SELECT COUNT(*) FROM completed) /
                   ((SELECT COUNT(*) FROM completed) + (SELECT COUNT(*) FROM noshow))
           END) AS show_rate,
      (SELECT COALESCE(SUM(price_estimate),0) FROM todays) AS revenue_estimate,
      (SELECT COALESCE(SUM(amount),0) FROM payments
         JOIN appointments a ON a.appointment_id = payments.appointment_id
         WHERE DATE(a.appt_start) = :d) AS revenue_paid
    ;
    """
    with engine.begin() as conn:
        row = conn.execute(text(q), {"d": str(day)}).mappings().first()
        util_q = """
        WITH todays AS (
          SELECT physio_id, appt_start, appt_end FROM appointments
          WHERE DATE(appt_start) = :d
        )
        SELECT p.full_name,
               SUM(strftime('%s', appt_end) - strftime('%s', appt_start)) / 3600.0 AS hours_scheduled
        FROM todays t JOIN physios p ON p.physio_id = t.physio_id
        GROUP BY p.full_name
        ORDER BY p.full_name;
        """
        util = pd.read_sql(text(util_q), conn, params={"d": str(day)})
    return row, util


row, util = kpis_for_day(picked_day)

# -------------------------------
# KPI cards
# -------------------------------
st.title("Clinic KPIs")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Bookings", int(row["bookings"]))
c2.metric("Cancellations", int(row["cancellations"]))
c3.metric("Show rate", f"{row['show_rate']*100:.1f}%")
c4.metric("Revenue est.", f"€{row['revenue_estimate']:.2f}")
c5.metric("Revenue (paid)", f"€{row['revenue_paid']:.2f}")

st.subheader("Utilization per physio (hours scheduled)")
st.dataframe(util)

# -------------------------------
# Last 14 days trend
# -------------------------------
st.subheader("Last 14 days trend")


@st.cache_data(ttl=60)
def last_14_days():
    q = """
    SELECT DATE(appt_start) AS d,
           COUNT(*) AS bookings,
           SUM(CASE WHEN status='canceled' THEN 1 ELSE 0 END) AS cancellations,
           SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed,
           SUM(CASE WHEN status='no_show' THEN 1 ELSE 0 END) AS no_show
    FROM appointments
    WHERE appt_start >= DATE('now','-14 day')
    GROUP BY DATE(appt_start)
    ORDER BY DATE(appt_start);
    """
    with engine.begin() as conn:
        return pd.read_sql(text(q), conn)


trend = last_14_days()
st.line_chart(
    trend.set_index("d")[["bookings", "cancellations", "completed", "no_show"]]
)

# -------------------------------
# Tomorrow at a glance
# -------------------------------
st.subheader("Tomorrow at a glance")

tomorrow = today + timedelta(days=1)
priorities_file = (
    Path(__file__).resolve().parents[1]
    / ".."
    / "02_reception_automation"
    / f"priorities_{tomorrow.isoformat()}.csv"
)

if priorities_file.exists():
    df = pd.read_csv(priorities_file)
    if not df.empty:
        high_risk = (df["risk_bucket"] == "high").sum()
        missing_phone = df["missing_phone"].sum()
        missing_consent = df["missing_consent"].sum()
        st.write(
            f"📌 Appointments: {len(df)} | ⚠️ High risk: {high_risk} | ☎ Missing phone: {missing_phone} | 📄 Missing consent: {missing_consent}"
        )
        st.dataframe(
            df[
                [
                    "patient_name",
                    "physio_name",
                    "appt_start",
                    "priority_reason",
                    "priority_score",
                ]
            ].head(10)
        )
    else:
        st.info("No appointments for tomorrow.")
else:
    st.warning(
        "Run build_priorities to generate tomorrow's list: python -m 02_reception_automation.build_priorities"
    )
