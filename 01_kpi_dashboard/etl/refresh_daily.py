import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import argparse, pandas as pd
from datetime import datetime
from sqlalchemy import text
from common.db import engine


def latest_day_dir(daily_root: Path) -> Path:
    """Pick the latest daily folder (sorted by name)"""
    dirs = [p for p in daily_root.glob("*") if p.is_dir()]
    if not dirs:
        raise FileNotFoundError("No daily folders found under data/daily/")
    return sorted(dirs)[-1]


def refresh_for_day(day: str, daily_dir: Path):
    """Refresh DB for a given day from daily snapshot"""
    appt_csv = daily_dir / "appointments.csv"
    pay_csv = daily_dir / "payments.csv"

    appts = pd.read_csv(appt_csv)
    pays = (
        pd.read_csv(pay_csv)
        if pay_csv.exists()
        else pd.DataFrame(
            columns=["payment_id", "appointment_id", "amount", "paid_at", "method"]
        )
    )

    with engine.begin() as conn:
        # remove existing rows for that day
        conn.execute(
            text(
                "DELETE FROM payments WHERE appointment_id IN "
                "(SELECT appointment_id FROM appointments WHERE DATE(appt_start)=:d)"
            ),
            {"d": day},
        )
        conn.execute(
            text("DELETE FROM appointments WHERE DATE(appt_start)=:d"), {"d": day}
        )

        # insert fresh data
        appts.to_sql("appointments", conn.connection, if_exists="append", index=False)
        if not pays.empty:
            pays.to_sql("payments", conn.connection, if_exists="append", index=False)

        # log the run
        conn.execute(
            text("INSERT INTO etl_runs(job, target_date, ran_at) VALUES(:j,:td,:t)"),
            {"j": "refresh_daily", "td": day, "t": datetime.utcnow().isoformat()},
        )

    print(f"✅ Refreshed day {day} from {daily_dir}")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    daily_root = root / "data" / "daily"

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--day", help="YYYY-MM-DD (default = latest folder under data/daily)"
    )
    args = parser.parse_args()

    if args.day:
        day = args.day
        ddir = daily_root / day
        assert ddir.exists(), f"{ddir} not found"
    else:
        ddir = latest_day_dir(daily_root)
        day = ddir.name  # folder name is the date

    refresh_for_day(day, ddir)
