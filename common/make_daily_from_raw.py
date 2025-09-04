import argparse, pandas as pd
from pathlib import Path


def main(day: str):
    root = Path(__file__).resolve().parents[1]
    raw = root / "data" / "raw"
    outdir = root / "data" / "daily" / day
    outdir.mkdir(parents=True, exist_ok=True)

    # appointments
    appts = pd.read_csv(raw / "appointments.csv")
    appts["d"] = pd.to_datetime(appts["appt_start"]).dt.date.astype(str)
    day_appts = appts[appts["d"] == day].drop(columns=["d"])
    day_appts.to_csv(outdir / "appointments.csv", index=False)

    # payments (only those for today's appointments)
    pays = pd.read_csv(raw / "payments.csv")
    keep_ids = set(day_appts["appointment_id"].tolist())
    day_pays = pays[pays["appointment_id"].isin(keep_ids)]
    day_pays.to_csv(outdir / "payments.csv", index=False)

    print(f"✅ Wrote daily snapshot to {outdir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    main(args.day)
