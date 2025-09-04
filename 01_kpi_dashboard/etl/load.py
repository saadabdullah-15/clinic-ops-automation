import pandas as pd
from pathlib import Path
from sqlalchemy import text
from common.db import engine, run_sql_file

root = Path(__file__).resolve().parents[2]
raw = root / "data" / "raw"
schema_path = root / "01_kpi_dashboard" / "schema.sql"


def load_table(csv_path, table):
    df = pd.read_csv(csv_path)
    df.to_sql(table, engine, if_exists="append", index=False)


if __name__ == "__main__":
    # create schema
    run_sql_file(str(schema_path))

    # idempotent load: wipe then load for Day 1 simplicity
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM payments"))
        conn.execute(text("DELETE FROM appointments"))
        conn.execute(text("DELETE FROM physios"))
        conn.execute(text("DELETE FROM patients"))

    load_table(raw / "patients.csv", "patients")
    load_table(raw / "physios.csv", "physios")
    load_table(raw / "appointments.csv", "appointments")
    load_table(raw / "payments.csv", "payments")

    print("Loaded CSVs into DB.")
