# --- ensure 'common' is importable no matter where we run from ---
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text
from common.db import engine

DDL = """
PRAGMA foreign_keys = ON;

-- patients_v2
CREATE TABLE IF NOT EXISTS patients_v2 (
  patient_id INTEGER PRIMARY KEY,
  first_name TEXT NOT NULL,
  last_name  TEXT NOT NULL,
  phone      TEXT,
  consent_form_received INTEGER NOT NULL DEFAULT 0 CHECK (consent_form_received IN (0,1)),
  created_at TEXT NOT NULL
);

-- physios_v2
CREATE TABLE IF NOT EXISTS physios_v2 (
  physio_id INTEGER PRIMARY KEY,
  full_name TEXT NOT NULL
);

-- appointments_v2 with stricter checks and generated date for indexing
CREATE TABLE IF NOT EXISTS appointments_v2 (
  appointment_id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL REFERENCES patients_v2(patient_id) ON DELETE CASCADE,
  physio_id  INTEGER NOT NULL REFERENCES physios_v2(physio_id)  ON DELETE CASCADE,
  appt_start TEXT NOT NULL,
  appt_end   TEXT NOT NULL,
  booked_at  TEXT NOT NULL,
  status     TEXT NOT NULL CHECK (status IN ('booked','completed','canceled','no_show')),
  price_estimate REAL NOT NULL CHECK (price_estimate >= 0.0),
  appt_date TEXT GENERATED ALWAYS AS (date(appt_start)) STORED,
  CHECK (strftime('%s', appt_end) > strftime('%s', appt_start)),
  CHECK (strftime('%s', appt_start) >= strftime('%s', booked_at))
);

-- payments_v2 (one payment per appointment in this demo, nonnegative amount)
CREATE TABLE IF NOT EXISTS payments_v2 (
  payment_id INTEGER PRIMARY KEY,
  appointment_id INTEGER NOT NULL UNIQUE REFERENCES appointments_v2(appointment_id) ON DELETE CASCADE,
  amount REAL NOT NULL CHECK (amount >= 0.0),
  paid_at TEXT NOT NULL,
  method TEXT NOT NULL,
  paid_date TEXT GENERATED ALWAYS AS (date(paid_at)) STORED
);

-- indices
CREATE INDEX IF NOT EXISTS idx_appt_date ON appointments_v2(appt_date);
CREATE INDEX IF NOT EXISTS idx_appt_physio_date ON appointments_v2(physio_id, appt_date);
CREATE INDEX IF NOT EXISTS idx_payments_paid_date ON payments_v2(paid_date);

-- prevent payments unless the appointment is completed
CREATE TRIGGER IF NOT EXISTS trg_payments_only_completed
BEFORE INSERT ON payments_v2
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN (SELECT status FROM appointments_v2 WHERE appointment_id = NEW.appointment_id) != 'completed'
    THEN RAISE(ABORT, 'Cannot insert payment for non-completed appointment')
  END;
END;
"""

COPY = """
INSERT INTO patients_v2 (patient_id, first_name, last_name, phone, consent_form_received, created_at)
SELECT patient_id, first_name, last_name, phone, COALESCE(consent_form_received,0), created_at FROM patients;

INSERT INTO physios_v2 (physio_id, full_name)
SELECT physio_id, full_name FROM physios;

INSERT INTO appointments_v2 (appointment_id, patient_id, physio_id, appt_start, appt_end, booked_at, status, price_estimate)
SELECT appointment_id, patient_id, physio_id, appt_start, appt_end, booked_at, status, price_estimate
FROM appointments;

INSERT INTO payments_v2 (payment_id, appointment_id, amount, paid_at, method)
SELECT payment_id, appointment_id, amount, paid_at, method
FROM payments;
"""

SWAP = """
DROP TABLE payments;
DROP TABLE appointments;
DROP TABLE physios;
DROP TABLE patients;

ALTER TABLE patients_v2 RENAME TO patients;
ALTER TABLE physios_v2 RENAME TO physios;
ALTER TABLE appointments_v2 RENAME TO appointments;
ALTER TABLE payments_v2 RENAME TO payments;
"""


def run():
    # Use raw sqlite3 connection underneath SQLAlchemy so we can call executescript
    with engine.begin() as conn:
        raw = conn.connection  # DB-API connection (sqlite3.Connection)
        # Run multi-statement scripts atomically in this transaction
        raw.executescript("PRAGMA foreign_keys = ON;")
        raw.executescript(DDL)
        raw.executescript(COPY)  # will raise if any row violates new checks
        raw.executescript(SWAP)
    print("✅ Migration to v2 schema completed.")


if __name__ == "__main__":
    run()
