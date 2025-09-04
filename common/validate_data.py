# --- ensure 'common' is importable no matter where we run from ---
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
import json, sys
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from sqlalchemy import text
from common.db import engine


def qdf(sql, params=None):
    with engine.begin() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def fail(name, detail, out):
    out["failures"].append({"check": name, "detail": detail})


def warn(name, detail, out):
    out["warnings"].append({"check": name, "detail": detail})


def check_sql_zero(name, sql, out):
    df = qdf(sql)
    cnt = int(df.iloc[0, 0]) if not df.empty else 0
    if cnt != 0:
        fail(name, f"count={cnt}", out)


def check_overlaps(out):
    # overlapping appointments per physio per day
    sql = """
    SELECT physio_id, appt_start, appt_end, date(appt_start) AS d
    FROM appointments
    ORDER BY physio_id, appt_start
    """
    df = qdf(sql)
    if df.empty:
        return
    df["appt_start"] = pd.to_datetime(df["appt_start"])
    df["appt_end"] = pd.to_datetime(df["appt_end"])
    bad = 0
    for (pid, d), g in df.groupby(["physio_id", "d"]):
        g = g.sort_values("appt_start")
        prev_end = None
        for _, r in g.iterrows():
            if prev_end is not None and r["appt_start"] < prev_end:
                bad += 1
            prev_end = (
                max(prev_end, r["appt_end"]) if prev_end is not None else r["appt_end"]
            )
    if bad:
        warn(
            "appt_overlaps",
            f"detected {bad} overlaps (investigate schedule rules)",
            out,
        )


def check_payments_vs_status(out):
    # payment exists for canceled or no_show (should be zero due to trigger, but verify)
    sql = """
    SELECT COUNT(*) AS n
    FROM payments p
    JOIN appointments a ON a.appointment_id = p.appointment_id
    WHERE a.status != 'completed'
    """
    df = qdf(sql)
    n = int(df.loc[0, "n"])
    if n:
        fail("payment_for_non_completed", f"{n} rows", out)

    # completed without payment within 1 day after end (warning, not fail)
    sql2 = """
    SELECT COUNT(*) AS n
    FROM appointments a
    LEFT JOIN payments p ON p.appointment_id = a.appointment_id
    WHERE a.status='completed' AND p.appointment_id IS NULL
      AND datetime(a.appt_end) <= datetime('now','-1 day')
    """
    df2 = qdf(sql2)
    n2 = int(df2.loc[0, "n"])
    if n2:
        warn("completed_without_payment", f"{n2} rows older than 1 day", out)


def run():
    out = {"timestamp": datetime.utcnow().isoformat(), "failures": [], "warnings": []}

    # basic integrity
    check_sql_zero(
        "null_patient_names",
        "SELECT COUNT(*) FROM patients WHERE first_name IS NULL OR last_name IS NULL",
        out,
    )
    check_sql_zero(
        "bad_consent_values",
        "SELECT COUNT(*) FROM patients WHERE consent_form_received NOT IN (0,1)",
        out,
    )
    check_sql_zero(
        "invalid_status_values",
        "SELECT COUNT(*) FROM appointments WHERE status NOT IN ('booked','completed','canceled','no_show')",
        out,
    )
    check_sql_zero(
        "end_before_start",
        "SELECT COUNT(*) FROM appointments WHERE strftime('%s', appt_end) <= strftime('%s', appt_start)",
        out,
    )
    check_sql_zero(
        "booked_after_start",
        "SELECT COUNT(*) FROM appointments WHERE strftime('%s', booked_at) > strftime('%s', appt_start)",
        out,
    )

    # referential
    check_sql_zero(
        "orphans_in_appointments_patients",
        "SELECT COUNT(*) FROM appointments a LEFT JOIN patients p ON p.patient_id=a.patient_id WHERE p.patient_id IS NULL",
        out,
    )
    check_sql_zero(
        "orphans_in_appointments_physios",
        "SELECT COUNT(*) FROM appointments a LEFT JOIN physios ph ON ph.physio_id=a.physio_id WHERE ph.physio_id IS NULL",
        out,
    )
    check_sql_zero(
        "orphans_in_payments",
        "SELECT COUNT(*) FROM payments p LEFT JOIN appointments a ON a.appointment_id=p.appointment_id WHERE a.appointment_id IS NULL",
        out,
    )

    # phone and consent for tomorrow’s list
    tomorrow = (datetime.now() + timedelta(days=1)).date().isoformat()
    sql_flags = """
    SELECT
      SUM(CASE WHEN p.phone IS NULL OR LENGTH(TRIM(p.phone)) < 6 THEN 1 ELSE 0 END) AS missing_phone,
      SUM(CASE WHEN p.consent_form_received = 0 THEN 1 ELSE 0 END) AS missing_consent
    FROM appointments a
    JOIN patients p ON p.patient_id = a.patient_id
    WHERE date(a.appt_start) = :d
    """
    df_flags = qdf(sql_flags, {"d": tomorrow})
    if not df_flags.empty:
        mp = int(df_flags.loc[0, "missing_phone"] or 0)
        mc = int(df_flags.loc[0, "missing_consent"] or 0)
        if mp or mc:
            warn(
                "tomorrow_flags",
                f"missing_phone={mp}, missing_consent=${mc} for {tomorrow}",
                out,
            )

    # overlaps and payments sanity
    check_overlaps(out)
    check_payments_vs_status(out)

    # write report
    rpt_dir = Path("artifacts/validation_reports")
    rpt_dir.mkdir(parents=True, exist_ok=True)
    rpt_file = (
        rpt_dir / f"validation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(rpt_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    # show summary
    print(json.dumps(out, indent=2))
    return 1 if out["failures"] else 0


if __name__ == "__main__":
    sys.exit(run())
