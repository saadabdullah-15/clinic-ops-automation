import sys
from pathlib import Path

# add repo root to sys.path so "common" can be imported
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd
import numpy as np
from sqlalchemy import text
from common.db import engine

POS_STATUSES = {"no_show", "canceled"}  # label = 1
NEG_STATUSES = {"completed"}  # label = 0


def _load_all_appointments():
    q = """
    SELECT
      a.appointment_id, a.patient_id, a.physio_id,
      a.appt_start, a.appt_end, a.booked_at, a.status,
      a.price_estimate
    FROM appointments a
    ORDER BY a.appt_start
    """
    with engine.begin() as conn:
        df = pd.read_sql(
            text(q), conn, parse_dates=["appt_start", "appt_end", "booked_at"]
        )
    return df


def _basic_features(df: pd.DataFrame) -> pd.DataFrame:
    X = df.copy()
    X["days_since_booking"] = (
        (X["appt_start"] - X["booked_at"]).dt.days.clip(lower=0).fillna(0)
    )
    X["hour"] = X["appt_start"].dt.hour
    X["weekday"] = X["appt_start"].dt.dayofweek  # 0=Mon

    # cumulative patient history
    X = X.sort_values(["patient_id", "appt_start"]).reset_index(drop=True)
    is_pos = X["status"].isin(POS_STATUSES).astype(int)

    X["prior_total"] = X.groupby("patient_id").cumcount()
    X["prior_pos"] = (
        is_pos.groupby(X["patient_id"]).cumsum().shift(1).fillna(0).astype(int)
    )
    X["noshow_rate_prior"] = np.where(
        X["prior_total"] > 0, X["prior_pos"] / X["prior_total"], 0.0
    )
    X["is_new_patient"] = (X["prior_total"] == 0).astype(int)

    # optional synthetic weather proxy
    weather_proxy = pd.DataFrame(
        [
            {"weekday": 0, "hour": 8, "is_rainy": 1},
            {"weekday": 0, "hour": 9, "is_rainy": 0},
            # Add more rows as needed
        ]
    )
    X = X.merge(weather_proxy, on=["weekday", "hour"], how="left")
    X["is_rainy"] = X["is_rainy"].fillna(0)

    # label
    y = X["status"].map(
        lambda s: 1 if s in POS_STATUSES else (0 if s in NEG_STATUSES else np.nan)
    )
    X["label"] = y

    feat_cols = [
        "days_since_booking",
        "hour",
        "weekday",
        "is_new_patient",
        "noshow_rate_prior",
        "price_estimate",
        "is_rainy",  # added
    ]
    keep_cols = [
        "appointment_id",
        "patient_id",
        "physio_id",
        "appt_start",
        "status",
        "label",
    ] + feat_cols
    return X[keep_cols], feat_cols


def build_training_frame():
    df = _load_all_appointments()
    X, feat_cols = _basic_features(df)
    train_df = X[X["label"].isin([0, 1])].copy()
    return train_df, feat_cols


def build_scoring_frame(day: str):
    df = _load_all_appointments()
    X, feat_cols = _basic_features(df)
    score_df = X[X["appt_start"].dt.date.astype(str) == day].copy()
    return score_df, feat_cols
