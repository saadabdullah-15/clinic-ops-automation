import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import argparse
import json
import numpy as np
import pandas as pd
from joblib import dump
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score, average_precision_score

from features import build_training_frame


def precision_at_k(y_true, y_score, k=None, frac=None):
    n = len(y_true)
    if k is None and frac is None:
        frac = 0.2
    if frac is not None:
        k = max(1, int(np.ceil(frac * n)))
    k = min(k, n)
    order = np.argsort(-y_score)
    topk = order[:k]
    return float(np.sum(y_true[topk])) / k


def compute_dynamic_threshold(y_true, y_score, coverage=0.5):
    """Compute smallest threshold covering `coverage` fraction of positives"""
    order = np.argsort(-y_score)
    cum_pos = np.cumsum(y_true[order])
    total_pos = cum_pos[-1]
    half_pos = total_pos * coverage
    k = np.argmax(cum_pos >= half_pos) + 1
    threshold = y_score[order][k - 1]
    return float(threshold)


def main(valid_days: int, model_out: str):
    df, feat_cols = build_training_frame()
    df = df.sort_values("appt_start")

    # time-based split
    last_day = df["appt_start"].dt.date.max()
    cutoff = last_day - pd.Timedelta(days=valid_days - 1)
    train = df[df["appt_start"].dt.date < cutoff].copy()
    valid = df[df["appt_start"].dt.date >= cutoff].copy()

    num_cols = [
        "days_since_booking",
        "hour",
        "noshow_rate_prior",
        "price_estimate",
        "is_rainy",
    ]
    cat_cols = ["weekday", "is_new_patient"]

    pre = ColumnTransformer(
        [
            ("num", StandardScaler(), num_cols),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                cat_cols,
            ),
        ]
    )

    clf = RandomForestClassifier(
        n_estimators=200, class_weight="balanced_subsample", random_state=42, n_jobs=-1
    )
    pipe = Pipeline([("pre", pre), ("clf", clf)])

    Xtr, ytr = train[feat_cols], train["label"].astype(int).values
    Xva, yva = valid[feat_cols], valid["label"].astype(int).values

    pipe.fit(Xtr, ytr)
    proba = pipe.predict_proba(Xva)[:, 1]

    # dynamic high-risk threshold
    high_risk_threshold = compute_dynamic_threshold(yva, proba, coverage=0.5)

    # feature importances
    importances = pipe.named_steps["clf"].feature_importances_

    metrics = {
        "n_train": int(len(train)),
        "n_valid": int(len(valid)),
        "pos_rate_valid": float(np.mean(yva)),
        "roc_auc": (
            float(roc_auc_score(yva, proba)) if len(np.unique(yva)) > 1 else None
        ),
        "avg_precision": float(average_precision_score(yva, proba)),
        "p_at_10": precision_at_k(yva, proba, k=10) if len(yva) >= 10 else None,
        "p_at_20pct": precision_at_k(yva, proba, frac=0.2),
        "cutoff_date": str(cutoff),
        "last_day": str(last_day),
        "features": feat_cols,
        "model": "random_forest_balanced",
        "high_risk_threshold": high_risk_threshold,
        "feature_importances": dict(zip(feat_cols, importances.tolist())),
    }

    outdir = Path(__file__).resolve().parent
    dump(pipe, outdir / model_out)
    with open(outdir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--valid-days", type=int, default=7)
    p.add_argument("--model-out", default="model.joblib")
    args = p.parse_args()
    main(args.valid_days, args.model_out)
