import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import argparse
import json
import pandas as pd
from joblib import load
from features import build_scoring_frame


def load_threshold():
    metrics_file = Path(__file__).resolve().parent / "metrics.json"
    if metrics_file.exists():
        with open(metrics_file, "r", encoding="utf-8") as f:
            metrics = json.load(f)
            return metrics.get("high_risk_threshold", 0.7)
    return 0.7  # fallback default


def bucket(x: float, threshold: float = 0.7) -> str:
    if x >= threshold:
        return "high"
    elif x >= 0.4:
        return "medium"
    else:
        return "low"


def write_outputs(day: str, scores: pd.DataFrame):
    repo = Path(__file__).resolve().parents[1]

    # daily file for reception loader
    daily = repo / "data" / "daily" / day
    daily.mkdir(parents=True, exist_ok=True)
    scores[["appointment_id", "risk_score", "risk_bucket"]].to_csv(
        daily / "cancellation_scores.csv", index=False
    )

    # combined file
    dst = Path(__file__).resolve().parent / "cancellation_scores.csv"
    if dst.exists():
        old = pd.read_csv(dst)
        old = old[old["day"] != day]
        combined = pd.concat([old, scores], ignore_index=True)
    else:
        combined = scores.copy()
    combined.to_csv(dst, index=False)

    print(f"Wrote {len(scores)} scores to:")
    print(f"  - {daily / 'cancellation_scores.csv'}")
    print(f"  - {dst}")


def main(day: str, model_path: str):
    pipe = load(Path(__file__).resolve().parent / model_path)
    threshold = load_threshold()

    df, feat_cols = build_scoring_frame(day)
    if df.empty:
        print(f"No appointments found for {day}. Nothing to score.")
        return

    probs = pipe.predict_proba(df[feat_cols])[:, 1]
    out = pd.DataFrame(
        {
            "day": day,
            "appointment_id": df["appointment_id"].astype(int),
            "risk_score": probs,
        }
    )
    out["risk_bucket"] = out["risk_score"].map(lambda x: bucket(x, threshold))
    write_outputs(day, out)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--day", required=True, help="YYYY-MM-DD")
    p.add_argument(
        "--model",
        default="model.joblib",
        help="model filename inside 03_cancellation_model",
    )
    args = p.parse_args()
    main(args.day, args.model)
