import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import argparse, os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from sqlalchemy import text
from common.db import engine
import pytz


BERLIN = pytz.timezone("Europe/Berlin")


def _tomorrow_str():
    return (datetime.now(BERLIN).date() + timedelta(days=1)).isoformat()


def _load_day_appointments(day: str) -> pd.DataFrame:
    q = """
    SELECT a.appointment_id, a.patient_id, a.physio_id,
           a.appt_start, a.appt_end, a.booked_at, a.status, a.price_estimate,
           p.first_name, p.last_name, p.phone, p.consent_form_received,
           ph.full_name AS physio_name
    FROM appointments a
    JOIN patients p ON p.patient_id = a.patient_id
    JOIN physios ph ON ph.physio_id = a.physio_id
    WHERE DATE(a.appt_start) = :d
    ORDER BY a.appt_start;
    """
    with engine.begin() as conn:
        df = pd.read_sql(text(q), conn, params={"d": day})
    return df


def _is_new_patient(day: str) -> pd.DataFrame:
    q = """
    SELECT patient_id,
           MIN(DATE(appt_start)) AS first_seen
    FROM appointments
    WHERE DATE(appt_start) < :d
    GROUP BY patient_id;
    """
    with engine.begin() as conn:
        seen = pd.read_sql(text(q), conn, params={"d": day})
    seen["is_new_before_day"] = False
    return seen


def _patient_noshow_rate(day: str, window_days: int = 90) -> pd.DataFrame:
    q = """
    SELECT patient_id,
           SUM(CASE WHEN status='no_show' THEN 1 ELSE 0 END) AS noshows,
           COUNT(*) AS total
    FROM appointments
    WHERE DATE(appt_start) < :d
      AND DATE(appt_start) >= DATE(:d, :delta)
    GROUP BY patient_id;
    """
    delta = f"-{window_days} day"
    with engine.begin() as conn:
        rates = pd.read_sql(text(q), conn, params={"d": day, "delta": delta})
    if rates.empty:
        return pd.DataFrame(columns=["patient_id", "noshow_rate_90d"])
    rates["noshow_rate_90d"] = rates["noshows"] / rates["total"].replace(0, np.nan)
    rates["noshow_rate_90d"] = rates["noshow_rate_90d"].fillna(0.0)
    return rates[["patient_id", "noshow_rate_90d"]]


def _load_model_scores(day: str) -> pd.DataFrame:
    repo = Path(__file__).resolve().parents[1]
    candidates = [
        repo / "03_cancellation_model" / "cancellation_scores.csv",
        repo / "data" / "daily" / day / "cancellation_scores.csv",
    ]
    for p in candidates:
        if p.exists():
            df = pd.read_csv(p)
            cols = [c.lower() for c in df.columns]
            df.columns = cols
            if "risk_score" not in df.columns and "risk_bucket" in df.columns:
                mapping = {"low": 0.2, "medium": 0.5, "high": 0.8}
                df["risk_score"] = (
                    df["risk_bucket"].str.lower().map(mapping).fillna(0.5)
                )
            return df[["appointment_id", "risk_score"]]
    return pd.DataFrame(columns=["appointment_id", "risk_score"])


def _heuristic_risk(row, patient_rate: float) -> float:
    score = 100.0 * float(patient_rate)
    if row["is_new_patient"]:
        score += 15.0
    hour = row["appt_dt"].hour
    if hour < 10 or hour >= 17:
        score += 10.0
    if row["appt_dt"].weekday() == 0:
        score += 5.0
    return max(0.0, min(score, 100.0)) / 100.0


def _bucket(x: float) -> str:
    if x >= 0.7:
        return "high"
    if x >= 0.4:
        return "medium"
    return "low"


def build(day: str) -> Path:
    repo = Path(__file__).resolve().parents[1]
    outdir = repo / "02_reception_automation"
    outdir.mkdir(parents=True, exist_ok=True)
    out_csv = outdir / f"priorities_{day}.csv"

    appts = _load_day_appointments(day)
    if appts.empty:
        appts.to_csv(out_csv, index=False)
        print(f"No appointments for {day}. Wrote empty file {out_csv}")
        return out_csv

    appts["patient_name"] = (
        appts["first_name"].fillna("") + " " + appts["last_name"].fillna("")
    )
    appts["appt_dt"] = pd.to_datetime(appts["appt_start"])

    seen = _is_new_patient(day)
    appts = appts.merge(
        seen[["patient_id", "is_new_before_day"]], on="patient_id", how="left"
    )
    appts["is_new_patient"] = appts["is_new_before_day"].isna()
    appts.drop(columns=["is_new_before_day"], inplace=True)

    rates = _patient_noshow_rate(day)
    appts = appts.merge(rates, on="patient_id", how="left").fillna(
        {"noshow_rate_90d": 0.0}
    )

    appts["missing_phone"] = appts["phone"].astype(str).str.len().fillna(0) < 6
    appts["missing_consent"] = appts["consent_form_received"].fillna(0).astype(int) == 0

    scores = _load_model_scores(day)
    appts = appts.merge(scores, on="appointment_id", how="left")

    def risk_row(r):
        if pd.notna(r.get("risk_score")):
            return float(r["risk_score"])
        return _heuristic_risk(r, float(r["noshow_rate_90d"]))

    appts["risk_score"] = appts.apply(risk_row, axis=1)
    appts["risk_bucket"] = appts["risk_score"].apply(_bucket)

    appts["priority_score"] = (
        100 * appts["is_new_patient"].astype(int)
        + 80 * appts["risk_score"].astype(float)
        + 40 * appts["missing_phone"].astype(int)
        + 30 * appts["missing_consent"].astype(int)
        + 10
        * ((appts["appt_dt"].dt.hour < 10) | (appts["appt_dt"].dt.hour >= 17)).astype(
            int
        )
    )

    def reasons(r):
        parts = []
        if r["is_new_patient"]:
            parts.append("new patient")
        if r["missing_phone"]:
            parts.append("missing phone")
        if r["missing_consent"]:
            parts.append("missing consent")
        parts.append(f"risk {r['risk_bucket']}")
        return ", ".join(parts)

    appts["priority_reason"] = appts.apply(reasons, axis=1)

    cols = [
        "appointment_id",
        "patient_id",
        "patient_name",
        "phone",
        "consent_form_received",
        "physio_name",
        "appt_start",
        "appt_end",
        "booked_at",
        "is_new_patient",
        "noshow_rate_90d",
        "risk_score",
        "risk_bucket",
        "missing_phone",
        "missing_consent",
        "priority_score",
        "priority_reason",
    ]
    appts = appts[cols].sort_values("priority_score", ascending=False)

    appts.to_csv(out_csv, index=False)
    print(f"Wrote priorities to {out_csv}")
    return out_csv


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", help="YYYY-MM-DD (default = tomorrow)")
    args = parser.parse_args()
    day = args.day or _tomorrow_str()
    build(day)
