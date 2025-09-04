PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS patients (
  patient_id INTEGER PRIMARY KEY,
  first_name TEXT NOT NULL,
  last_name  TEXT NOT NULL,
  phone      TEXT,
  consent_form_received INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS physios (
  physio_id INTEGER PRIMARY KEY,
  full_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS appointments (
  appointment_id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  physio_id  INTEGER NOT NULL REFERENCES physios(physio_id),
  appt_start TEXT NOT NULL,
  appt_end   TEXT NOT NULL,
  booked_at  TEXT NOT NULL,
  status     TEXT NOT NULL CHECK (status IN ('booked','completed','canceled','no_show')),
  price_estimate REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
  payment_id INTEGER PRIMARY KEY,
  appointment_id INTEGER NOT NULL REFERENCES appointments(appointment_id),
  amount REAL NOT NULL,
  paid_at TEXT NOT NULL,
  method TEXT NOT NULL
);
