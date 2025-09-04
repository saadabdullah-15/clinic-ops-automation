import json
from pathlib import Path
import pandas as pd
from sqlalchemy import text
from common.db import engine


def kpis(day):
    with engine.begin() as conn:
        q = """
        SELECT DATE(appt_start) d,
               COUNT(*) bookings,
               SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) completed,
               SUM(CASE WHEN status='canceled' THEN 1 ELSE 0 END) canceled,
               SUM(CASE WHEN status='no_show' THEN 1 ELSE 0 END) no_show,
               SUM(price_estimate) est_rev
        FROM appointments WHERE DATE(appt_start)=:d
        """
        row = conn.execute(text(q), {"d": day}).mappings().first()
        p = """
        SELECT COALESCE(SUM(amount),0) paid
        FROM payments p JOIN appointments a ON a.appointment_id=p.appointment_id
        WHERE DATE(a.appt_start)=:d
        """
        paid = conn.execute(text(p), {"d": day}).scalar() or 0
    row = dict(row or {})
    row["paid_rev"] = float(paid)
    return row


def tomorrow_flags(day):
    with engine.begin() as conn:
        q = """
        SELECT
          SUM(CASE WHEN p.phone IS NULL OR LENGTH(TRIM(p.phone))<6 THEN 1 ELSE 0 END) AS missing_phone,
          SUM(CASE WHEN p.consent_form_received=0 THEN 1 ELSE 0 END) AS missing_consent
        FROM appointments a JOIN patients p ON p.patient_id=a.patient_id
        WHERE DATE(a.appt_start)=:d
        """
        row = conn.execute(text(q), {"d": day}).mappings().first()
    return dict(row or {})


def risk_breakdown(day):
    pri = Path("02_reception_automation") / f"priorities_{day}.csv"
    if not pri.exists():
        return {}
    df = pd.read_csv(pri)
    if "risk_bucket" not in df.columns:
        return {"note": "no risk_bucket column in priorities file"}
    brk = df["risk_bucket"].value_counts().to_dict()
    return {
        "risk_counts": brk,
        "top5": df[["appointment_id", "patient_name", "risk_bucket", "priority_score"]]
        .head(5)
        .to_dict(orient="records"),
    }


def model_metrics():
    m = Path("03_cancellation_model/metrics.json")
    if not m.exists():
        return {}
    return json.loads(m.read_text(encoding="utf-8"))


def main(today, tomorrow):
    out = {
        "today": kpis(today),
        "tomorrow_flags": tomorrow_flags(tomorrow),
        "tomorrow_risk": risk_breakdown(tomorrow),
        "model": model_metrics(),
    }
    Path("assets").mkdir(exist_ok=True)
    (Path("assets") / "summary.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    import argparse
    from datetime import date, timedelta

    d = date.today()
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", default=str(d))
    parser.add_argument("--tomorrow", default=str(d + timedelta(days=1)))
    a = parser.parse_args()
    main(a.today, a.tomorrow)
