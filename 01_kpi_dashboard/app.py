import pandas as pd
import streamlit as st
from sqlalchemy import text
from common.db import engine
from datetime import datetime
import pytz

st.set_page_config(page_title="Clinic KPIs", layout="wide")

# today in Berlin
berlin = pytz.timezone("Europe/Berlin")
today = datetime.now(berlin).date()


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
    ),
    duration AS (
      SELECT physio_id,
             SUM(strftime('%s', appt_end) - strftime('%s', appt_start)) / 60.0 AS minutes
      FROM todays GROUP BY physio_id
    )
    SELECT
      (SELECT COUNT(*) FROM todays) AS bookings,
      (SELECT COUNT(*) FROM canceled) AS cancellations,
      (SELECT CASE WHEN (SELECT COUNT(*) FROM completed)+ (SELECT COUNT(*) FROM noshow) = 0
              THEN 0.0
              ELSE 1.0 * (SELECT COUNT(*) FROM completed) /
                   ((SELECT COUNT(*) FROM completed) + (SELECT COUNT(*) FROM noshow))
           END) AS show_rate,
      (SELECT COALESCE(SUM(amount),0) FROM payments
         JOIN appointments a ON a.appointment_id = payments.appointment_id
         WHERE DATE(a.appt_start) = :d) AS revenue
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


row, util = kpis_for_day(today)

st.title("Clinic KPIs")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Today bookings", int(row["bookings"]))
c2.metric("Cancellations", int(row["cancellations"]))
c3.metric("Show rate", f"{row['show_rate']*100:.1f}%")
c4.metric("Revenue (paid)", f"€{row['revenue']:.2f}")

st.subheader("Utilization per physio (hours scheduled today)")
st.dataframe(util)

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
