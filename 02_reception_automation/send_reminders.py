import argparse
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()
OUTBOX = Path(os.getenv("EMAIL_OUTBOX_DIR", "outbox"))

TEMPLATE = """To: {patient_name} <{fake_email}>
Subject: Appointment reminder for {appt_date} at {appt_time}

Hi {patient_name},

This is a friendly reminder of your physiotherapy appointment with {physio_name}
on {appt_date} at {appt_time}.

If you need to reschedule, please reply or call us so we can offer the slot to another patient in need.

Thank you,
Clinic Reception
"""


def fake_email_for(row) -> str:
    base = f"{str(row['patient_name']).strip().lower().replace(' ','_')}.{int(row['patient_id'])}"
    return f"{base}@example.local"


def main(day: str, dry_run: bool):
    repo = Path(__file__).resolve().parents[2]
    csv_path = repo / "02_reception_automation" / f"priorities_{day}.csv"
    assert (
        csv_path.exists()
    ), f"Priorities file not found: {csv_path}. Run build_priorities first."

    # 🔒 Robust guard for empty CSVs or missing columns
    df = (
        pd.read_csv(csv_path, parse_dates=["appt_start"])
        if csv_path.stat().st_size > 0
        else pd.DataFrame()
    )
    if (
        df.empty
        or "missing_phone" not in df.columns
        or "missing_consent" not in df.columns
    ):
        print(
            "No eligible rows (empty priorities or missing columns). Nothing to send."
        )
        return

    send_df = df[(~df["missing_phone"]) & (~df["missing_consent"])].copy()

    OUTBOX.mkdir(parents=True, exist_ok=True)
    written = 0
    previews = []

    for _, r in send_df.iterrows():
        appt_date = r["appt_start"].date().isoformat()
        appt_time = r["appt_start"].strftime("%H:%M")
        content = TEMPLATE.format(
            patient_name=r["patient_name"],
            fake_email=fake_email_for(r),
            appt_date=appt_date,
            appt_time=appt_time,
            physio_name=r["physio_name"],
        )
        fname = f"{appt_date}_{int(r['appointment_id'])}_reminder.txt"
        fpath = OUTBOX / fname
        previews.append((fname, content.splitlines()[1]))
        if not dry_run:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            written += 1

    if dry_run:
        print("Dry run, no files written.")
    print(f"Prepared {len(send_df)} reminders, wrote {written} files to {OUTBOX}")
    if previews[:5]:
        print("Sample:")
        for fn, subj in previews[:5]:
            print(f"  {fn} | {subj}")


if __name__ == "__main__":
    from datetime import datetime, timedelta
    import pytz

    BERLIN = pytz.timezone("Europe/Berlin")
    tomorrow = (datetime.now(BERLIN).date() + timedelta(days=1)).isoformat()

    p = argparse.ArgumentParser()
    p.add_argument("--day", default=tomorrow, help="YYYY-MM-DD")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    main(args.day, args.dry_run)
