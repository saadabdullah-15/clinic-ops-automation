from flask import Flask, jsonify, request
from pathlib import Path
import pandas as pd
from . import build_priorities as bp
import pytz
from datetime import datetime, timedelta

app = Flask(__name__)


def default_tomorrow():
    berlin = pytz.timezone("Europe/Berlin")
    return (datetime.now(berlin).date() + timedelta(days=1)).isoformat()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/priorities")
def priorities():
    day = request.args.get("day") or default_tomorrow()
    repo = Path(__file__).resolve().parents[2]
    pcsv = repo / "02_reception_automation" / f"priorities_{day}.csv"

    # build if missing
    if not pcsv.exists():
        bp.build(day)

    # if still missing or empty, return safe fallback
    if not pcsv.exists() or pcsv.stat().st_size == 0:
        return jsonify({"day": day, "count": 0, "items": []})

    df = pd.read_csv(pcsv)

    # If the CSV exists but has no rows, return empty
    if df.empty:
        return jsonify({"day": day, "count": 0, "items": []})

    # Make sure required columns exist
    required_cols = [
        "appointment_id",
        "patient_id",
        "patient_name",
        "phone",
        "consent_form_received",
        "physio_name",
        "appt_start",
        "is_new_patient",
        "risk_bucket",
        "missing_phone",
        "missing_consent",
        "priority_score",
        "priority_reason",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        return jsonify(
            {
                "day": day,
                "count": 0,
                "items": [],
                "warning": f"Priorities file missing expected columns: {missing}",
            }
        )

    # select and sort
    show = df[required_cols].sort_values("priority_score", ascending=False)
    items = show.to_dict(orient="records")
    return jsonify({"day": day, "count": len(items), "items": items})


if __name__ == "__main__":
    # run with: python -m 02_reception_automation.server
    app.run(host="127.0.0.1", port=8008, debug=True)
